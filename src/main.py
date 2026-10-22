"""
Ponto de entrada (Entrypoint) do pipeline de extração de alimentos em PDFs prisionais.

Responsabilidades deste módulo:
- Orquestrar a leitura da pasta de PDFs.
- Gerenciar paginação contínua global.
- Chamar os extratores especializados (cabeçalho OCR e produtos tabulares).
- Exportar o consolidado final formatado para Excel.
"""

import hashlib
import os
import re
import sys
from pathlib import Path

# Garantir que o diretório src/ esteja no sys.path para imports absolutos
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Garantir encoding UTF-8 no console do Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import pymupdf

from config.settings import ARQUIVO_SAIDA_XLSX, DIR_CACHE, DIR_PDFS, DIR_PLANILHAS
from extractors.header_extractor import processar_cabecalho_ocr
from extractors.product_extractor import extrair_produtos_da_pagina
from utils.excel_exporter import ajustar_larguras_excel


def obter_chave_ordenacao(nome: str):
    """Extrai número inteiro do nome do arquivo para ordenação natural (12502 antes de 12510)."""
    stem = os.path.splitext(nome)[0]
    digitos = re.findall(r"\d+", stem)
    return int(digitos[0]) if digitos else stem


def salvar_excel_seguro(df: pd.DataFrame, caminho_destino: Path):
    """Salva o DataFrame em Excel com formatação elegante e fallback para PermissionError."""
    caminho_destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(caminho_destino, index=False)
        ajustar_larguras_excel(caminho_destino)
        print(f"✅ Planilha gerada com sucesso: {caminho_destino.name} ({len(df)} registros)")
    except PermissionError:
        backup_nome = caminho_destino.with_name(f"{caminho_destino.stem}_novo.xlsx")
        df.to_excel(backup_nome, index=False)
        ajustar_larguras_excel(backup_nome)
        print(f"⚠️ Arquivo aberto no Excel. Salvo como: {backup_nome.name} ({len(df)} registros)")


def processar_lote_pdfs(arquivos_caminhos: list, nome_lote: str) -> pd.DataFrame:
    """Processa uma lista de arquivos PDF gerando registros com paginação contínua."""
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos_caminhos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            for num_pag, pagina in enumerate(doc, start=1):
                data, mes, lugar = processar_cabecalho_ocr(pagina, pdf_hash, num_pag)
                produtos = extrair_produtos_da_pagina(pagina)

                print(
                    f"[{idx:03d}/{len(arquivos_caminhos):03d}] {nome_arquivo} (pág {pagina_continua_global}): "
                    f"{len(produtos):2d} alimentos | Data: {data or 'N/A'} | Local: {lugar[:35]}"
                )

                for prod in produtos:
                    registros.append({
                        "pasta_origem": nome_lote,
                        "arquivo": nome_arquivo,
                        "pagina": pagina_continua_global,
                        "lugar": lugar,
                        "produto": prod,
                        "data": data,
                        "mes": mes,
                    })

                pagina_continua_global += 1

            doc.close()
        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        colunas = ["arquivo", "pagina", "lugar", "produto", "data", "mes"]
        df = df[colunas]
    return df


def executar_pipeline() -> None:
    """
    Executa a automação para cada uma das subpastas dentro de PDFs/
    e gera:
    1. Uma planilha dedicada para cada subpasta em planilhas_saida/
    2. Uma planilha consolidada geral com todos os meses.
    """
    if not DIR_PDFS.exists():
        print(f"Diretório não encontrado: {DIR_PDFS}")
        return

    DIR_PLANILHAS.mkdir(parents=True, exist_ok=True)

    # Identificar subpastas de PDFs
    subpastas = sorted([p for p in DIR_PDFS.iterdir() if p.is_dir()])
    
    if not subpastas:
        # Se os PDFs estiverem diretamente na raiz de PDFs/
        subpastas = [DIR_PDFS]

    print(f"\n🚀 Iniciando processamento de {len(subpastas)} pastas de PDFs...\n")

    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO PASTA: {nome_subpasta}")
        print("=" * 70)

        arquivos_caminhos = list(subpasta.glob("*.pdf"))
        arquivos_caminhos = sorted(arquivos_caminhos, key=lambda p: obter_chave_ordenacao(p.name))

        if not arquivos_caminhos:
            print(f"Nenhum PDF encontrado em: {nome_subpasta}")
            continue

        # Processar o lote desta subpasta
        df_lote = processar_lote_pdfs(arquivos_caminhos, nome_subpasta)

        if not df_lote.empty:
            # Nome da planilha limpo para cada subpasta garantindo extensão .xlsx
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_saida_lote = DIR_PLANILHAS / f"saida_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_saida_lote)
            todos_dfs.append(df_lote)

    # Gerar planilha unificada com tudo
    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL")
        print("=" * 70)
        salvar_excel_seguro(df_total, ARQUIVO_SAIDA_XLSX)
        print(f"\n🎉 Processamento 100% finalizado! Todas as planilhas salvas em: {DIR_PLANILHAS.name}/\n")


if __name__ == "__main__":
    executar_pipeline()
