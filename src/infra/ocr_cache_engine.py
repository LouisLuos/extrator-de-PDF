"""
Camada de Infraestrutura: Motor de Leitura de PDF, OCR (ROI e Página Inteira) e Cache em Disco.

Responsabilidade (Clean Architecture):
- Isolar detalhes técnicos de baixo nível (PyMuPDF, OpenCV, NumPy, Tesseract e JSON Cache).
- Fornecer funções limpas para que os Casos de Uso (Use Cases) não precisem conhecer
  bibliotecas de imagem ou estrutura de pastas de cache.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import pymupdf
import pytesseract
from pytesseract import Output

from config.settings import BASE_DIR, DPI, TESSERACT_EXE

if TESSERACT_EXE and os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_CACHE_NAO_PERECIVEL = BASE_DIR / "cache_ocr_nao_perecivel"
DIR_CACHE_PERECIVEL.mkdir(parents=True, exist_ok=True)


def processar_pagina_ocr_completo(
    pagina: pymupdf.Page,
    pdf_hash: str,
    num_pag: int,
    dir_cache: Path = DIR_CACHE_PERECIVEL,
) -> Tuple[Dict[str, Any], str]:
    """
    Executa OCR na página inteira (300 DPI) e gerencia cache JSON local (`_full.json`)
    no diretório da categoria informada (`cache_ocr_perecivel` ou `cache_ocr_nao_perecivel`).
    """
    dir_cache.mkdir(parents=True, exist_ok=True)
    arquivo_cache = dir_cache / f"{pdf_hash}_p{num_pag:04d}_full.json"

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


def extrair_texto_pagina_acelerado(args: Tuple[bytes, int, str]) -> Tuple[int, str]:
    """
    Processa uma página de PDF de forma ultrarrápida (usado pela Interface Web):
    1. Verifica caches em disco (0ms) nas pastas de cache existentes.
    2. Usa texto vetorial nativo se existir (0ms).
    3. Executa OCR apenas nas regiões essenciais (Cabeçalho 45% + Rodapé 30%), acelerando em 3x a 4x.
    """
    pdf_bytes, num_pag, pdf_hash = args
    cache_file = DIR_CACHE_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_fast.json"

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return num_pag, json.load(f)["texto"]
        except Exception:
            pass

    # Checa caches legados completos ou de cabeçalho se existirem na máquina
    diretorios_cache = [
        DIR_CACHE_PERECIVEL,
        DIR_CACHE_NAO_PERECIVEL,
        BASE_DIR / "cache_ocr",
    ]
    for dir_c in diretorios_cache:
        full_cache = dir_c / f"{pdf_hash}_p{num_pag:04d}_full.json"
        if full_cache.exists():
            try:
                with open(full_cache, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    txt = " ".join(t for t in d.get("text", []) if t.strip())
                    return num_pag, txt
            except Exception:
                pass
        h_cache = dir_c / f"{pdf_hash}_p{num_pag:04d}_header.json"
        if h_cache.exists():
            try:
                with open(h_cache, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    txt = " ".join(t for t in d.get("text", []) if t.strip())
                    return num_pag, txt
            except Exception:
                pass

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[num_pag - 1]

    # 1. Camada vetorial nativa (sem necessidade de OCR)
    txt_vetor = page.get_text()
    if len(txt_vetor.strip()) > 80:
        doc.close()
        return num_pag, txt_vetor

    # 2. OCR inteligente em ROI (Cabeçalho 45% + Rodapé 30%)
    try:
        pix = page.get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        h, w = img_gray.shape

        crop_h = img_gray[0 : int(h * 0.45), 0:w]
        crop_f = img_gray[int(h * 0.70) : h, 0:w]

        txt_h = pytesseract.image_to_string(crop_h, lang="por", config="--psm 6")
        txt_f = pytesseract.image_to_string(crop_f, lang="por", config="--psm 6")
        txt_total = f"{txt_h} {txt_f}"
    except Exception:
        txt_total = txt_vetor

    doc.close()

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"texto": txt_total}, f, ensure_ascii=False)
    except Exception:
        pass

    return num_pag, txt_total


def extrair_paginas_pdf_em_paralelo(
    caminho_pdf: Path, max_threads: int = 4
) -> List[Tuple[int, str]]:
    """Abre um arquivo PDF, calcula seu hash e extrai o texto de todas as páginas em paralelo."""
    doc = pymupdf.open(caminho_pdf)
    pdf_bytes = caminho_pdf.read_bytes()
    pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:10]
    total_pags = len(doc)
    doc.close()

    tarefas = [(pdf_bytes, i, pdf_hash) for i in range(1, total_pags + 1)]
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        paginas_processadas = list(executor.map(extrair_texto_pagina_acelerado, tarefas))

    paginas_processadas.sort(key=lambda x: x[0])
    return paginas_processadas
