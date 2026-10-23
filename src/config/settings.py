"""
Constantes, caminhos e parâmetros globais do pipeline de extração.
"""

from pathlib import Path
import os
import pytesseract

import shutil

# Busca automática em caminhos padrões do Windows e no PATH
POSSIVEIS_CAMINHOS_TESSERACT = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]

TESSERACT_EXE = None
for caminho in POSSIVEIS_CAMINHOS_TESSERACT:
    if os.path.exists(caminho):
        TESSERACT_EXE = caminho
        break

if not TESSERACT_EXE:
    tess_path = shutil.which("tesseract")
    if tess_path:
        TESSERACT_EXE = tess_path
    else:
        TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

# ==============================================================================
# DIRETÓRIOS & ARQUIVOS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DIR_PDFS = BASE_DIR / "PDFs"
DIR_CACHE = BASE_DIR / "cache_ocr"
DIR_PLANILHAS = BASE_DIR / "planilhas_saida"
ARQUIVO_SAIDA_XLSX = DIR_PLANILHAS / "saida_consolidada_total.xlsx"
GABARITO_XLSX = BASE_DIR.parent / "saida_hibrida.xlsx"

# ==============================================================================
# PARÂMETROS DE VISÃO COMPUTACIONAL & GEOMETRIA
# ==============================================================================
DPI = 300
CROP_HEADER_RATIO = 0.5  # Metade superior da página contém os metadados do cabeçalho
TOLERANCIA_LINHA_PDF = 3.0
TOLERANCIA_LINHA_OCR = 15

# ==============================================================================
# DOMÍNIO DE NEGÓCIO: ALIMENTOS & PALAVRAS-CHAVE
# ==============================================================================
PRODUTOS_ESPERADOS = [
    "ABOBORA", "BANANA", "BATATA DOCE", "BATATA INGLESA", "CARA",
    "CEBOLA", "CENOURA", "CHUCHU", "COENTRO", "MACAXEIRA",
    "MAMAO", "MELANCIA", "MELAO", "OVOS", "PIMENTAO", "TOMATE"
]

PRODUTOS_SEM_KG = {"OVOS", "OVO"}
VARIACOES_KG = {"KG", "K6", "K.G", "K.G.", "K G", "KS"}

HEADER_KEYWORDS = {
    "QTD", "QTDE", "DESCRICAO", "DESCRIÇÃO", "CODIGO", "CÓDIGO",
    "U.M.", "U.M", "UM", "PESO", "PRODUTO"
}

ROTULOS_DELIMITADORES_LUGAR = [
    "L.F:", "L.F.", "L.F", "FONE:", "FONE", "CNPJ:", "C.N.P.J", "CNPJ",
    "CEP:", "CEP", "U.F:", "UF:", "UF", "I.E:", "IE:", "IE", "ENDEREÇO:", "ENDERECO:"
]
