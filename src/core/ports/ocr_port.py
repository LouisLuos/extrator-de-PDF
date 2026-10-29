"""
Portas de Saída (Outbound Ports) — Contratos que o Core exige da Infraestrutura.

Na Arquitetura Hexagonal (Ports & Adapters), o Caso de Uso não precisa saber SE o texto
veio do Tesseract, do EasyOCR ou de um PDF vetorial, nem SE o relatório será salvo em Excel
ou Banco de Dados. Ele depende apenas destes contratos (Protocols).
"""

from pathlib import Path
from typing import Any, Callable, Tuple
import pandas as pd


# Tipo de contrato (Port) para funções que extraem texto de uma página PDF:
# Recebe (pdf_bytes, num_pagina, pdf_hash) e devolve (num_pagina, texto_extraido)
ExtratorTextoPaginaPort = Callable[[Tuple[bytes, int, str]], Tuple[int, str]]

# Tipo de contrato (Port) para funções que exportam um DataFrame consolidado para um destino:
ExportadorPlanilhaPort = Callable[[pd.DataFrame, Path], Any]

