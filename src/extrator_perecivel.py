"""
Pipeline especializado para extração de alimentos PERECÍVEIS (Carnes, Frios e Proteínas).

Documentos digitalizados (sem camada vetorial nativa):
- Realiza OCR de página inteira a 300 DPI com cache JSON em cache_ocr_perecivel/
- Extrai metadados do cabeçalho (Data, Mês e Unidade Prisional)
- Extrai itens da tabela de carnes/embutidos (linhas com código CEASA)
- Salva os resultados individuais por mês e consolidados em planilhas_saida/ceasa/perecivel/
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

DIR_PERECIVEL = BASE_DIR / "PDFs" / "perecivel"
DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_SAIDA_PERECIVEL = DIR_PLANILHAS / "ceasa" / "perecivel"


def obter_chave_ordenacao(nome: str):
    stem = os.path.splitext(nome)[0]
    digitos = re.findall(r"\d+", stem)
    return int(digitos[0]) if digitos else stem


def processar_pagina_ocr_completo(pagina: pymupdf.Page, pdf_hash: str, num_pag: int) -> Tuple[Dict[str, Any], str]:
    """Executa OCR na página inteira e gerencia cache JSON local."""
    DIR_CACHE_PERECIVEL.mkdir(parents=True, exist_ok=True)
    arquivo_cache = DIR_CACHE_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_full.json"

    if arquivo_cache.exists():
        with open(arquivo_cache, "r", encoding="utf-8") as f:
            dados_ocr = json.load(f)
    else:
        pix = pagina.get_pixmap(dpi=DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_cinza = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        dados_ocr = pytesseract.image_to_data(
            img_cinza, lang="por", output_type=Output.DICT, config="--psm 6"
        )
        with open(arquivo_cache, "w", encoding="utf-8") as f:
            json.dump(dados_ocr, f, ensure_ascii=False)

    texto_completo = " ".join(t for t in dados_ocr.get("text", []) if t.strip())
    return dados_ocr, texto_completo


def normalizar_produto_perecivel(texto_bruto: str) -> Optional[str]:
    """Mapeia o texto ruidoso do OCR de carnes para a nomenclatura padronizada oficial."""
    t = texto_bruto.upper()
    if "LINGUICA" in t or "CALABRESA" in t or "TALABRESA" in t:
        return "LINGUICA CALABRESA KG"
    if "SALSICHA" in t or "HOT DOG" in t or "HOT" in t:
        return "SALSICHA HOT DOG KG"
    if "FIGADO" in t or "MUIDO" in t or "MÍUDO" in t:
        return "MUIDO CONGELADO DE BOVINO - FIGADO KG"
    if "PEIXE" in t:
        return "FILE DE PEIXE KG"
    if "AVE" in t or "FRANGO" in t or "COXA" in t or "SOBRECOXA" in t:
        return "CARNE DE AVE CONGELADA COXA E SOBRECOXA KG"
    if "SUINO" in t or "SÚINO" in t or "LOMBO" in t:
        return "CARNE CONGELADA DE SUINO SEM OSSO - LOMBO KG"
    if "CHARQUE" in t or "ROJAO" in t or "ROJÃO" in t:
        return "CARNE DE CHARQUE DO TIPO ROJAO KG"
    if "SALGADA" in t or "CURADA" in t or "DESSECADA" in t:
        return "CARNE BOVINA SALGADA CURADA DESSECADA KG"
    if "MUSCULO" in t or "MÚSCULO" in t or ("BOVINA" in t and "SEGUNDA" in t):
        return "CARNE BOVINA DE SEGUNDA - MUSCULO KG"
    if "BOVINA" in t:
        return "CARNE BOVINA KG"
    return None


def extrair_produtos_ocr_perecivel(dados_ocr: Dict[str, Any]) -> List[str]:
    """Reconstitui linhas tabulares do OCR e normaliza nomes de carnes/embutidos."""
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

        # Ignorar linhas de totais, assinaturas e carimbos
        if any(ignore in linha.upper() for ignore in ["TOTAIS", "ASSINATURA", "NUTRIC", "ESTOQUIST"]):
            continue

        # Linhas de produtos começam com o código CEASA ou possuem termos de carnes
        if re.search(r"\bCEASA\d+", linha) or any(k in linha.upper() for k in ["CARNE", "LINGUICA", "SALSICHA", "MUIDO", "FIGADO"]):
            prod_padronizado = normalizar_produto_perecivel(linha)
            if prod_padronizado and prod_padronizado not in produtos:
                produtos.append(prod_padronizado)

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


def processar_lote_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
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
                produtos = extrair_produtos_ocr_perecivel(dados_ocr)

                print(
                    f"[{idx:03d}/{len(arquivos):03d}] {nome_arquivo} (pág {pagina_continua_global}): "
                    f"{len(produtos):2d} carnes/frios | Data: {data or 'N/A'} | Local: {lugar[:35]}"
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


def executar_pipeline_pereciveis():
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


if __name__ == "__main__":
    executar_pipeline_pereciveis()
