"""
Camada de Casos de Uso (Application / Use Cases) — Orquestrador de Lotes de Guias.

Papel desta camada (O Maestro):
- Coordenar a execução entre a Infraestrutura (OCR / Leitura de PDF / Exportação Excel)
  e o Domínio (Identificação de Presídio, Extração de Data, Segmentação de Múltiplas Guias).
- Contém os fluxos de negócio para Web, Hortifrúti, Perecíveis e Não Perecíveis.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pymupdf

from config.settings import DIR_PDFS, DIR_PLANILHAS
from core.domain.guia_service import (
    extrair_data_robusta,
    identificar_unidade_prisional,
    obter_chave_ordenacao,
    segmentar_guias_por_paginas,
)
from core.ports.ocr_port import ExtratorTextoPaginaPort
from infra.header_extractor import processar_cabecalho_ocr
from infra.ocr_cache_engine import (
    DIR_CACHE_NAO_PERECIVEL,
    DIR_CACHE_PERECIVEL,
    extrair_texto_pagina_acelerado,
    processar_pagina_ocr_completo,
)
from utils.excel_exporter import ajustar_larguras_excel, salvar_excel_seguro
from utils.text_cleaner import detectar_reposicao

DIR_HORTIFRUTE = DIR_PDFS / "hortifrute"
DIR_SAIDA_HORTIFRUTE = DIR_PLANILHAS / "ceasa" / "hortifrute"
ARQUIVO_SAIDA_HORTIFRUTE = DIR_SAIDA_HORTIFRUTE / "saida_consolidada_total.xlsx"

DIR_PERECIVEL = DIR_PDFS / "perecivel"
DIR_SAIDA_PERECIVEL = DIR_PLANILHAS / "ceasa" / "perecivel"

DIR_NAO_PERECIVEL = DIR_PDFS / "nao-perecivel"
DIR_SAIDA_NAO_PERECIVEL = DIR_PLANILHAS / "ceasa" / "nao_perecivel"


# ==============================================================================
# 1. CASO DE USO: PROCESSAMENTO ACELERADO MULTI-GUIAS (WEB / API)
# ==============================================================================

def processar_caminhos_pdf_acelerado(
    caminhos_pdf: List[Path],
    dir_saida_excel: Path,
    extrator_pagina: ExtratorTextoPaginaPort = extrair_texto_pagina_acelerado,
) -> Dict[str, Any]:
    """
    Caso de Uso: Processa uma lista de arquivos PDF, desmembra múltiplas guias
    usando o Domínio e exporta a planilha consolidada.
    """
    registros: List[Dict[str, Any]] = []
    pagina_continua_global = 1
    max_threads = min(4, os.cpu_count() or 4)

    for idx, caminho_salvo in enumerate(caminhos_pdf, start=1):
        nome_original = caminho_salvo.name
        try:
            doc = pymupdf.open(caminho_salvo)
            pdf_bytes = caminho_salvo.read_bytes()
            pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:10]
            total_pags = len(doc)
            doc.close()

            print(f"[USE CASE] ⚙️ [{idx}/{len(caminhos_pdf)}] Processando '{nome_original}' ({total_pags} pág(s))...")

            tarefas = [(pdf_bytes, i, pdf_hash) for i in range(1, total_pags + 1)]
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                paginas_processadas = list(executor.map(extrator_pagina, tarefas))

            paginas_processadas.sort(key=lambda x: x[0])

            guias = segmentar_guias_por_paginas(paginas_processadas)
            tem_multi_guias = len(guias) > 1

            for g in guias:
                texto_guia = " ".join(g["textos"])
                lugar_final = identificar_unidade_prisional(texto_guia)
                num_str = g["numero"] or ""
                data_final, mes_final = extrair_data_robusta(
                    texto_guia, f"{num_str}.pdf" if num_str else nome_original
                )
                reposicao = detectar_reposicao(texto_guia)

                nome_arquivo_formatado = (
                    f"{nome_original} [Guia {num_str}]"
                    if tem_multi_guias and num_str
                    else nome_original
                )

                print(
                    f"  └─ Guia {num_str or 's/n'}: {lugar_final[:30]} | "
                    f"Data: {data_final or 'N/A'} | Reposição: {reposicao}"
                )

                registros.append({
                    "arquivo": nome_arquivo_formatado,
                    "pagina": pagina_continua_global,
                    "lugar": lugar_final,
                    "data": data_final or "N/A",
                    "mes": mes_final or "N/A",
                    "reposicao": reposicao,
                })

                pagina_continua_global += 1

        except Exception as e:
            print(f"[USE CASE] ❌ Erro ao processar {nome_original}: {e}")

    if not registros:
        return {}

    df = pd.DataFrame(registros)
    colunas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
    df = df[colunas]

    dir_saida_excel.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_excel = f"guias_consolidadas_{timestamp}.xlsx"
    caminho_excel = dir_saida_excel / nome_arquivo_excel

    df.to_excel(caminho_excel, index=False)
    ajustar_larguras_excel(caminho_excel)

    total_guias = len(df)
    total_reposicoes = int((df["reposicao"] == "SIM").sum())
    total_regulares = int(total_guias - total_reposicoes)

    return {
        "total_guias": int(total_guias),
        "total_regulares": total_regulares,
        "total_reposicoes": total_reposicoes,
        "arquivo_excel": nome_arquivo_excel,
        "registros": df.to_dict(orient="records"),
    }


# ==============================================================================
# 2. CASO DE USO: PIPELINE EM LOTE — HORTIFRÚTI
# ==============================================================================

def processar_lote_pdfs(arquivos_caminhos: List[Path], nome_lote: str) -> pd.DataFrame:
    """Caso de Uso: Processa uma lista de arquivos PDF (Hortifrúti) gerando 1 linha por guia."""
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos_caminhos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            for num_pag, pagina in enumerate(doc, start=1):
                data, mes, lugar, texto_ocr = processar_cabecalho_ocr(pagina, pdf_hash, num_pag)
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

                registros.append({
                    "pasta_origem": nome_lote,
                    "arquivo": nome_arquivo,
                    "pagina": pagina_continua_global,
                    "lugar": lugar,
                    "data": data,
                    "mes": mes,
                    "reposicao": reposicao,
                })

                pagina_continua_global += 1

            doc.close()
        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        colunas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
        df = df[colunas]
    return df


def executar_pipeline_hortifrute() -> None:
    """Caso de Uso: Executa a automação em lote para todas as subpastas de Hortifrúti."""
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

        arquivos_caminhos = sorted(
            list(subpasta.glob("*.pdf")),
            key=lambda p: obter_chave_ordenacao(p.name),
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
        print(f"\n🎉 Processamento 100% finalizado! Salvo em: {ARQUIVO_SAIDA_HORTIFRUTE}\n")


# ==============================================================================
# 3. CASO DE USO: PIPELINE EM LOTE — PERECÍVEIS E NÃO PERECÍVEIS
# ==============================================================================

def _processar_lote_ocr_completo(arquivos: List[Path], nome_lote: str, dir_cache: Path) -> pd.DataFrame:
    """Função interna unificada (DRY) para processar lotes com OCR de página inteira."""
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
                _, texto_completo = processar_pagina_ocr_completo(pagina, pdf_hash, num_pag, dir_cache=dir_cache)
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

            registros.append({
                "pasta_origem": nome_lote,
                "arquivo": nome_arquivo,
                "pagina": pagina_continua_global,
                "lugar": lugar_final,
                "data": data_final,
                "mes": mes_final,
                "reposicao": reposicao,
            })

            pagina_continua_global += 1

        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        colunas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
        df = df[colunas]
    return df


def processar_lote_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
    return _processar_lote_ocr_completo(arquivos, nome_lote, DIR_CACHE_PERECIVEL)


def processar_lote_nao_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
    return _processar_lote_ocr_completo(arquivos, nome_lote, DIR_CACHE_NAO_PERECIVEL)


def executar_pipeline_pereciveis() -> None:
    if not DIR_PERECIVEL.exists():
        print(f"Diretório não encontrado: {DIR_PERECIVEL}")
        return

    DIR_SAIDA_PERECIVEL.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in DIR_PERECIVEL.iterdir() if p.is_dir()])

    print(f"\n🚀 Iniciando extração de alimentos PERECÍVEIS em {len(subpastas)} pastas...\n")
    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO PERECÍVEIS: {nome_subpasta}")
        print("=" * 70)

        arquivos = sorted(list(subpasta.glob("*.pdf")), key=lambda p: obter_chave_ordenacao(p.name))
        if not arquivos:
            continue

        df_lote = processar_lote_perecivel(arquivos, nome_subpasta)
        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_lote = DIR_SAIDA_PERECIVEL / f"saida_perecivel_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL DE PERECÍVEIS")
        print("=" * 70)
        caminho_consolidado = DIR_SAIDA_PERECIVEL / "saida_consolidada_perecivel_total.xlsx"
        salvar_excel_seguro(df_total, caminho_consolidado)
        print(f"\n🎉 Extração de Perecíveis 100% concluída em: {DIR_SAIDA_PERECIVEL.name}/\n")


def executar_pipeline_nao_pereciveis() -> None:
    if not DIR_NAO_PERECIVEL.exists():
        print(f"Diretório não encontrado: {DIR_NAO_PERECIVEL}")
        return

    DIR_SAIDA_NAO_PERECIVEL.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in DIR_NAO_PERECIVEL.iterdir() if p.is_dir()])

    print(f"\n🚀 Iniciando extração de alimentos NÃO PERECÍVEIS em {len(subpastas)} pastas...\n")
    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO NÃO PERECÍVEIS: {nome_subpasta}")
        print("=" * 70)

        arquivos = sorted(list(subpasta.glob("*.pdf")), key=lambda p: obter_chave_ordenacao(p.name))
        if not arquivos:
            continue

        df_lote = processar_lote_nao_perecivel(arquivos, nome_subpasta)
        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_lote = DIR_SAIDA_NAO_PERECIVEL / f"saida_nao_perecivel_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL DE NÃO PERECÍVEIS")
        print("=" * 70)
        caminho_consolidado = DIR_SAIDA_NAO_PERECIVEL / "saida_consolidada_nao_perecivel_total.xlsx"
        salvar_excel_seguro(df_total, caminho_consolidado)
        print(f"\n🎉 Extração de Não Perecíveis 100% concluída em: {DIR_SAIDA_NAO_PERECIVEL.name}/\n")
