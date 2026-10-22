"""
Pipeline especializado para extração de alimentos NÃO PERECÍVEIS (Itens Secos, Estocáveis e Mercearia).

Documentos digitalizados:
- Realiza OCR a 300 DPI com cache JSON inteligente em cache_ocr_nao_perecivel/
- Reaproveita caches existentes de OCR para economia de processamento (idempotência)
- Extrai metadados do cabeçalho (Data, Mês e Unidade Prisional)
- Extrai itens da tabela de produtos (linhas com código CEASA e itens secos)
- Salva os resultados individuais por mês e consolidados em planilhas_saida/ceasa/nao_perecivel/
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Configurar UTF-8 no console Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np
import pandas as pd
import pymupdf
import pytesseract
from pytesseract import Output

from config.settings import BASE_DIR, DIR_PLANILHAS, DPI, TESSERACT_EXE, TOLERANCIA_LINHA_OCR
from extractors.header_extractor import extrair_data_ocr, extrair_lugar_ocr
from utils.excel_exporter import ajustar_larguras_excel

if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

DIR_NAO_PERECIVEL = BASE_DIR / "PDFs" / "nao-perecivel"
DIR_CACHE_NAO_PERECIVEL = BASE_DIR / "cache_ocr_nao_perecivel"
DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_CACHE_GERAL = BASE_DIR / "cache_ocr"
DIR_SAIDA_NAO_PERECIVEL = DIR_PLANILHAS / "ceasa" / "nao_perecivel"

# Palavras-chave de alimentos secos / estocáveis para enriquecer extração
PALAVRAS_CHAVE_NAO_PERECIVEL = [
    "ARROZ", "FEIJAO", "FEIJÃO", "ACUCAR", "AÇÚCAR", "OLEO", "ÓLEO",
    "CAFE", "CAFÉ", "MACARRAO", "MACARRÃO", "SAL", "FARINHA",
    "BISCOITO", "LEITE", "SARDINHA", "EXTRATO", "MOLHO", "MILHO",
    "ERVILHA", "TEMPERO", "VINAGRE", "DOCE", "FARINHA DE TRIGO",
    "FARINHA DE MANDIOCA", "AVEIA", "AMIDO", "ACHOCOLATADO"
]


def obter_chave_ordenacao(nome: str):
    stem = os.path.splitext(nome)[0]
    digitos = re.findall(r"\d+", stem)
    return int(digitos[0]) if digitos else stem


def processar_pagina_ocr_completo(pagina: pymupdf.Page, pdf_hash: str, num_pag: int) -> Tuple[Dict[str, Any], str]:
    """Executa OCR na página com estratégia multi-cache inteligente para máxima eficiência."""
    DIR_CACHE_NAO_PERECIVEL.mkdir(parents=True, exist_ok=True)
    arquivo_cache_proprio = DIR_CACHE_NAO_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_full.json"
    arquivo_cache_perecivel = DIR_CACHE_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_full.json"

    dados_ocr = None

    if arquivo_cache_proprio.exists():
        with open(arquivo_cache_proprio, "r", encoding="utf-8") as f:
            dados_ocr = json.load(f)
    elif arquivo_cache_perecivel.exists():
        # Reutilizar cache já computado pelo pipeline de perecíveis (poupa tempo de CPU!)
        with open(arquivo_cache_perecivel, "r", encoding="utf-8") as f:
            dados_ocr = json.load(f)
        # Salva cópia no cache de não perecíveis
        with open(arquivo_cache_proprio, "w", encoding="utf-8") as f:
            json.dump(dados_ocr, f, ensure_ascii=False)
    else:
        # Se for um PDF novo, realiza o OCR completo em 300 DPI
        pix = pagina.get_pixmap(dpi=DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_cinza = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        dados_ocr = pytesseract.image_to_data(
            img_cinza, lang="por", output_type=Output.DICT, config="--psm 6"
        )
        with open(arquivo_cache_proprio, "w", encoding="utf-8") as f:
            json.dump(dados_ocr, f, ensure_ascii=False)

    texto_completo = " ".join(t for t in dados_ocr.get("text", []) if t.strip())
    return dados_ocr, texto_completo


def extrair_produtos_ocr_nao_perecivel(dados_ocr: Dict[str, Any]) -> List[str]:
    """Reconstitui linhas tabulares do OCR e extrai itens da tabela CEASA / alimentos secos."""
    linhas: Dict[int, List[Tuple[int, str]]] = {}
    total = len(dados_ocr.get("text", []))

    for i in range(total):
        t = dados_ocr["text"][i].strip()
        if not t:
            continue
        y = dados_ocr["top"][i]
        matched = False
        for yk in linhas:
            if abs(yk - y) < TOLERANCIA_LINHA_OCR:
                linhas[yk].append((dados_ocr["left"][i], t))
                matched = True
                break
        if not matched:
            linhas[y] = [(dados_ocr["left"][i], t)]

    produtos = []
    for yk in sorted(linhas.keys()):
        linha = " ".join(t[1] for t in sorted(linhas[yk], key=lambda x: x[0]))

        # Linhas de produtos CEASA (com código de item)
        if re.search(r"\bCEASA\d+", linha):
            m_prod = re.search(
                r"\bCEASA\d+[\-\w]*\s+(.+?)(?:\s+\d+[\.,]\d+|\s+\d+\s+(?:KG|FD|CX|PCT|LT|UN)|\s+(?:KG|FD|CX|PCT|LT|UN)\b|$)",
                linha,
                re.IGNORECASE,
            )
            if m_prod:
                item_nome = m_prod.group(1).strip(" -.,:")
                item_nome = re.sub(r"\s+\d+$", "", item_nome).strip()
                if (
                    item_nome
                    and len(item_nome) > 3
                    and "SERVIÇO" not in item_nome.upper()
                    and "CEASA/PE" not in item_nome.upper()
                ):
                    produtos.append(item_nome)
                    continue

        # Linhas contendo palavras-chave de itens secos/estocáveis
        linha_upper = linha.upper()
        for kw in PALAVRAS_CHAVE_NAO_PERECIVEL:
            if re.search(r"\b" + re.escape(kw) + r"\b", linha_upper):
                if "TOTAL" not in linha_upper and "OBSERVA" not in linha_upper and len(linha.strip()) > 3:
                    if linha.strip() not in produtos:
                        produtos.append(linha.strip())
                break

    return produtos


def salvar_excel_seguro(df: pd.DataFrame, caminho_destino: Path):
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


def processar_lote_nao_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            for num_pag, pagina in enumerate(doc, start=1):
                dados_ocr, texto_completo = processar_pagina_ocr_completo(pagina, pdf_hash, num_pag)
                data, mes = extrair_data_ocr(texto_completo)
                lugar = extrair_lugar_ocr(dados_ocr)
                produtos = extrair_produtos_ocr_nao_perecivel(dados_ocr)

                print(
                    f"[{idx:03d}/{len(arquivos):03d}] {nome_arquivo} (pág {pagina_continua_global}): "
                    f"{len(produtos):2d} itens | Data: {data or 'N/A'} | Local: {lugar[:35]}"
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


def executar_pipeline_nao_pereciveis():
    if not DIR_NAO_PERECIVEL.exists():
        print(f"Diretório não encontrado: {DIR_NAO_PERECIVEL}")
        return

    DIR_SAIDA_NAO_PERECIVEL.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in DIR_NAO_PERECIVEL.iterdir() if p.is_dir()])

    if not subpastas:
        subpastas = [DIR_NAO_PERECIVEL]

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


if __name__ == "__main__":
    executar_pipeline_nao_pereciveis()
