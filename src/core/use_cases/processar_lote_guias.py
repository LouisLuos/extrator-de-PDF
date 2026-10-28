"""
Camada Application / Use Cases: Casos de Uso de Processamento de Guias Prisionais.

Responsabilidade (Clean Architecture):
- Orquestrar o fluxo entre a leitura de PDFs (Infraestrutura), a segmentação e
  extração de regras de negócio (Domínio) e a geração de planilhas consolidadas.
- Centralizar os pipelines de Web, Hortifrúti, Perecíveis e Não Perecíveis em um
  único ponto de orquestração (eliminando duplicação de código entre os extratores).
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pymupdf

from config.settings import BASE_DIR, DIR_PDFS, DIR_PLANILHAS
from core.domain.guia_service import (
    RegistroGuiaConsolidada,
    consolidar_guia_segmentada,
    detectar_reposicao,
    eh_documento_guia_valido,
    extrair_data_robusta,
    identificar_unidade_prisional,
    obter_chave_ordenacao,
    segmentar_guias_por_pagina,
)
from extractors.header_extractor import processar_cabecalho_ocr
from infra.ocr_cache_engine import (
    DIR_CACHE_NAO_PERECIVEL,
    DIR_CACHE_PERECIVEL,
    extrair_paginas_pdf_em_paralelo,
    processar_pagina_ocr_completo,
)
from utils.excel_exporter import ajustar_larguras_excel, salvar_excel_seguro

COLUNAS_CONSOLIDADAS = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]

DIR_HORTIFRUTE = DIR_PDFS / "hortifrute"
DIR_SAIDA_HORTIFRUTE = DIR_PLANILHAS / "ceasa" / "hortifrute"
ARQUIVO_SAIDA_HORTIFRUTE = DIR_SAIDA_HORTIFRUTE / "saida_consolidada_total.xlsx"

DIR_PERECIVEL = BASE_DIR / "PDFs" / "perecivel"
DIR_SAIDA_PERECIVEL = DIR_PLANILHAS / "ceasa" / "perecivel"

DIR_NAO_PERECIVEL = BASE_DIR / "PDFs" / "nao-perecivel"
DIR_SAIDA_NAO_PERECIVEL = DIR_PLANILHAS / "ceasa" / "nao_perecivel"


@dataclass(frozen=True)
class ResultadoProcessamentoWebDTO:
    """DTO de saída retornado pelo Caso de Uso para a camada de apresentação Web."""

    total_guias: int
    total_regulares: int
    total_reposicoes: int
    arquivo_excel: str
    registros: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_guias": self.total_guias,
            "total_regulares": self.total_regulares,
            "total_reposicoes": self.total_reposicoes,
            "arquivo_excel": self.arquivo_excel,
            "registros": self.registros,
        }


def processar_arquivos_enviados_use_case(
    arquivos_salvos: List[Tuple[str, Path]],
    dir_saida_web: Path,
) -> Optional[ResultadoProcessamentoWebDTO]:
    """
    Caso de Uso Principal (Acionado pela Interface Web):
    Recebe uma lista de (nome_original, caminho_pdf_temporario), executa a extração
    acelerada com cache, desmembra múltiplas guias via Domínio e exporta o Excel final.
    """
    registros: List[Dict[str, object]] = []
    pagina_continua_global = 1
    max_threads = min(4, os.cpu_count() or 4)

    for idx, (nome_original, caminho_salvo) in enumerate(arquivos_salvos, start=1):
        try:
            paginas_processadas = extrair_paginas_pdf_em_paralelo(
                caminho_salvo, max_threads=max_threads
            )
            print(
                f"[WEB] ⚙️ [{idx}/{len(arquivos_salvos)}] Processando '{nome_original}' ({len(paginas_processadas)} pág(s))..."
            )

            guias = segmentar_guias_por_pagina(paginas_processadas)
            guias_validas = [
                g for g in guias if eh_documento_guia_valido(g.texto_completo)
            ]

            if not guias_validas:
                print(
                    f"  └─ ⚠️ Ignorado: '{nome_original}' não pertence ao domínio de Guias Prisionais (CEASA/SERES-PE)."
                )
                continue

            tem_multi_guias = len(guias_validas) > 1

            for guia in guias_validas:
                registro: RegistroGuiaConsolidada = consolidar_guia_segmentada(
                    guia=guia,
                    nome_arquivo_original=nome_original,
                    pagina_continua_global=pagina_continua_global,
                    tem_multi_guias=tem_multi_guias,
                )
                print(
                    f"  └─ Guia {guia.numero or 's/n'}: {registro.lugar[:30]} | Data: {registro.data} | Reposição: {registro.reposicao}"
                )
                registros.append(registro.to_dict())
                pagina_continua_global += 1

        except Exception as e:
            print(f"[WEB] ❌ Erro ao processar {nome_original}: {e}")

    if not registros:
        return None

    df = pd.DataFrame(registros)[COLUNAS_CONSOLIDADAS]

    dir_saida_web.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_excel = f"guias_consolidadas_{timestamp}.xlsx"
    caminho_excel = dir_saida_web / nome_arquivo_excel

    df.to_excel(caminho_excel, index=False)
    ajustar_larguras_excel(caminho_excel)

    total_guias = len(df)
    total_reposicoes = int((df["reposicao"] == "SIM").sum())
    total_regulares = int(total_guias - total_reposicoes)

    print(
        f"[WEB] ✅ Concluído: {total_guias} guia(s) auditada(s). Salvo em: {nome_arquivo_excel}\n"
    )

    return ResultadoProcessamentoWebDTO(
        total_guias=int(total_guias),
        total_regulares=total_regulares,
        total_reposicoes=total_reposicoes,
        arquivo_excel=nome_arquivo_excel,
        registros=df.to_dict(orient="records"),
    )


def processar_lote_pdfs(arquivos_caminhos: list, nome_lote: str) -> pd.DataFrame:
    """Caso de Uso em Lote (Hortifrúti): Processa uma lista de PDFs gerando 1 linha por guia."""
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos_caminhos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            for num_pag, pagina in enumerate(doc, start=1):
                data, mes, lugar, texto_ocr = processar_cabecalho_ocr(
                    pagina, pdf_hash, num_pag
                )
                texto_pagina = pagina.get_text()
                texto_combinado = f"{texto_pagina} {texto_ocr}"

                if lugar == "NÃO IDENTIFICADO":
                    lug_fallback = identificar_unidade_prisional(texto_combinado)
                    if lug_fallback != "NÃO IDENTIFICADO":
                        lugar = lug_fallback

                reposicao = detectar_reposicao(texto_combinado)

                print(
                    f"[{idx:03d}/{len(arquivos_caminhos):03d}] {nome_arquivo} (guia {pagina_continua_global}): "
                    f"Data: {data or 'N/A'} | Local: {lugar[:35]} | Reposição: {reposicao}"
                )

                registros.append(
                    {
                        "pasta_origem": nome_lote,
                        "arquivo": nome_arquivo,
                        "pagina": pagina_continua_global,
                        "lugar": lugar,
                        "data": data,
                        "mes": mes,
                        "reposicao": reposicao,
                    }
                )

                pagina_continua_global += 1

            doc.close()
        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        df = df[COLUNAS_CONSOLIDADAS]
    return df


def processar_lote_ocr_completo(
    arquivos: List[Path],
    nome_lote: str,
    dir_cache: Path,
) -> pd.DataFrame:
    """
    Caso de Uso Unificado para Lotes Digitalizados (Perecíveis e Não Perecíveis):
    Executa OCR de página inteira com cache e aplica as regras de domínio para extrair
    Data, Mês, Unidade Prisional e Reposição.
    """
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            textos_doc = []
            data_final, mes_final, lugar_final = None, None, "NÃO IDENTIFICADO"

            for num_pag, pagina in enumerate(doc, start=1):
                _dados_ocr, texto_completo = processar_pagina_ocr_completo(
                    pagina, pdf_hash, num_pag, dir_cache=dir_cache
                )
                textos_doc.append(texto_completo)
                textos_doc.append(pagina.get_text())

                if num_pag == 1 or data_final is None:
                    d, m = extrair_data_robusta(texto_completo, nome_arquivo)
                    if d:
                        data_final, mes_final = d, m

                if num_pag == 1 or lugar_final == "NÃO IDENTIFICADO":
                    lug = identificar_unidade_prisional(texto_completo)
                    if lug != "NÃO IDENTIFICADO":
                        lugar_final = lug

            doc.close()

            texto_total = " ".join(textos_doc)
            reposicao = detectar_reposicao(texto_total)

            print(
                f"[{idx:03d}/{len(arquivos):03d}] {nome_arquivo} (guia {pagina_continua_global}): "
                f"Data: {data_final or 'N/A'} | Local: {lugar_final[:35]} | Reposição: {reposicao}"
            )

            registros.append(
                {
                    "pasta_origem": nome_lote,
                    "arquivo": nome_arquivo,
                    "pagina": pagina_continua_global,
                    "lugar": lugar_final,
                    "data": data_final,
                    "mes": mes_final,
                    "reposicao": reposicao,
                }
            )

            pagina_continua_global += 1

        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        df = df[COLUNAS_CONSOLIDADAS]
    return df


def _executar_pipeline_por_categoria(
    dir_origem: Path,
    dir_saida: Path,
    prefixo_arquivo: str,
    nome_consolidado: str,
    titulo_log: str,
    dir_cache: Path,
) -> None:
    """Orquestrador parametrizado para processar subpastas de uma categoria com OCR completo."""
    if not dir_origem.exists():
        print(f"Diretório não encontrado: {dir_origem}")
        return

    dir_saida.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in dir_origem.iterdir() if p.is_dir()])

    print(f"\n🚀 Iniciando extração de alimentos {titulo_log} em {len(subpastas)} pastas...\n")

    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO {titulo_log}: {nome_subpasta}")
        print("=" * 70)

        arquivos = sorted(
            list(subpasta.glob("*.pdf")),
            key=lambda p: obter_chave_ordenacao(p.name),
        )
        if not arquivos:
            continue

        df_lote = processar_lote_ocr_completo(
            arquivos, nome_subpasta, dir_cache=dir_cache
        )

        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_lote = dir_saida / f"saida_{prefixo_arquivo}_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print(f"📊 GERANDO PLANILHA CONSOLIDADA GERAL DE {titulo_log}")
        print("=" * 70)
        caminho_consolidado = dir_saida / nome_consolidado
        salvar_excel_seguro(df_total, caminho_consolidado)
        print(f"\n🎉 Extração de {titulo_log} 100% concluída em: {dir_saida.name}/\n")


def executar_pipeline_pereciveis() -> None:
    """Caso de Uso Batch: Processa todas as pastas de alimentos Perecíveis."""
    _executar_pipeline_por_categoria(
        dir_origem=DIR_PERECIVEL,
        dir_saida=DIR_SAIDA_PERECIVEL,
        prefixo_arquivo="perecivel",
        nome_consolidado="saida_consolidada_perecivel_total.xlsx",
        titulo_log="PERECÍVEIS",
        dir_cache=DIR_CACHE_PERECIVEL,
    )


def executar_pipeline_nao_pereciveis() -> None:
    """Caso de Uso Batch: Processa todas as pastas de alimentos Não Perecíveis."""
    _executar_pipeline_por_categoria(
        dir_origem=DIR_NAO_PERECIVEL,
        dir_saida=DIR_SAIDA_NAO_PERECIVEL,
        prefixo_arquivo="nao_perecivel",
        nome_consolidado="saida_consolidada_nao_perecivel_total.xlsx",
        titulo_log="NÃO PERECÍVEIS",
        dir_cache=DIR_CACHE_NAO_PERECIVEL,
    )


def executar_pipeline_hortifrute() -> None:
    """
    Caso de Uso Batch: Executa a automação para cada subpasta dentro de PDFs/hortifrute/
    e gera as planilhas por subpasta e a planilha consolidada geral.
    """
    dir_busca = DIR_HORTIFRUTE if DIR_HORTIFRUTE.exists() else DIR_PDFS
    if not dir_busca.exists():
        print(f"Diretório não encontrado: {dir_busca}")
        return

    DIR_SAIDA_HORTIFRUTE.mkdir(parents=True, exist_ok=True)

    subpastas = sorted([p for p in dir_busca.iterdir() if p.is_dir()])
    if not subpastas:
        subpastas = [dir_busca]

    print(f"\n🚀 Iniciando processamento de {len(subpastas)} pastas de Hortifrúti...\n")

    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO PASTA: {nome_subpasta}")
        print("=" * 70)

        arquivos_caminhos = list(subpasta.glob("*.pdf"))
        arquivos_caminhos = sorted(
            arquivos_caminhos, key=lambda p: obter_chave_ordenacao(p.name)
        )

        if not arquivos_caminhos:
            print(f"Nenhum PDF encontrado em: {nome_subpasta}")
            continue

        df_lote = processar_lote_pdfs(arquivos_caminhos, nome_subpasta)

        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_saida_lote = DIR_SAIDA_HORTIFRUTE / f"saida_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_saida_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL (HORTIFRÚTI)")
        print("=" * 70)
        salvar_excel_seguro(df_total, ARQUIVO_SAIDA_HORTIFRUTE)
        print(
            f"\n🎉 Processamento 100% finalizado! Salvo em: {ARQUIVO_SAIDA_HORTIFRUTE}\n"
        )
