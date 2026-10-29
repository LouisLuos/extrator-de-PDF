"""
Extração de metadados do cabeçalho (Data e Unidade Prisional) via Tesseract OCR com cache local.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pymupdf
import pytesseract
from pytesseract import Output

from config.settings import (
    CROP_HEADER_RATIO,
    DIR_CACHE,
    DPI,
    ROTULOS_DELIMITADORES_LUGAR,
    TOLERANCIA_LINHA_OCR,
)
from utils.text_cleaner import limpar_nome_lugar


def extrair_data_ocr(texto: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai a data de entrega e o mês da página via Regex resiliente."""
    # Procura 'Data: DD/MM/AAAA'
    m = re.search(r"\bData\s*:?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto, re.IGNORECASE)
    if not m:
        # Fallback para primeira data válida encontrada no cabeçalho
        m = re.search(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b", texto)

    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{dia:02d}/{mes:02d}/{ano}", f"{mes:02d}"

    return None, None


def extrair_lugar_ocr(dados_ocr: Dict[str, Any]) -> str:
    """Localiza o nome da unidade prisional após o campo 'Nome:'."""
    linhas: Dict[int, List[Dict[str, Any]]] = {}
    total_palavras = len(dados_ocr.get("text", []))

    for i in range(total_palavras):
        texto = dados_ocr["text"][i].strip()
        if not texto:
            continue
        y = dados_ocr["top"][i]
        matched = False
        for yk in linhas:
            if abs(yk - y) < TOLERANCIA_LINHA_OCR:
                linhas[yk].append({"texto": texto, "left": dados_ocr["left"][i]})
                matched = True
                break
        if not matched:
            linhas[y] = [{"texto": texto, "left": dados_ocr["left"][i]}]

    for _, palavras in sorted(linhas.items()):
        ordenadas = sorted(palavras, key=lambda p: p["left"])
        textos = [p["texto"] for p in ordenadas]

        for trigger in ["Nome:", "Nome", "Destinatário:", "Destinatario:"]:
            if trigger in textos:
                idx = textos.index(trigger)
                partes = []
                for t in textos[idx + 1:]:
                    if any(rotulo in t.upper() for rotulo in ROTULOS_DELIMITADORES_LUGAR):
                        break
                    partes.append(t)
                nome = " ".join(partes).strip()
                if nome:
                    return limpar_nome_lugar(nome)

    return "NÃO IDENTIFICADO"


def processar_cabecalho_ocr(pagina: pymupdf.Page, pdf_hash: str, num_pag: int) -> Tuple[Optional[str], Optional[str], str, str]:
    """Executa OCR na metade superior da página com sistema de cache JSON."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    arquivo_cache = DIR_CACHE / f"{pdf_hash}_p{num_pag:04d}_header.json"

    if arquivo_cache.exists():
        with open(arquivo_cache, "r", encoding="utf-8") as f:
            dados_ocr = json.load(f)
    else:
        rect = pagina.rect
        clip = pymupdf.Rect(0, 0, rect.width, rect.height * CROP_HEADER_RATIO)
        pix = pagina.get_pixmap(clip=clip, dpi=DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_cinza = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        dados_ocr = pytesseract.image_to_data(
            img_cinza, lang="por", output_type=Output.DICT, config="--psm 6"
        )
        with open(arquivo_cache, "w", encoding="utf-8") as f:
            json.dump(dados_ocr, f, ensure_ascii=False)

    texto_completo = " ".join(t for t in dados_ocr.get("text", []) if t.strip())
    data, mes = extrair_data_ocr(texto_completo)
    lugar = extrair_lugar_ocr(dados_ocr)
    return data, mes, lugar, texto_completo
