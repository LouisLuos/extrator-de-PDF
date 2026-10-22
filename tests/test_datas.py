"""
Testes Unitários: Extração e Validação de Datas de Emissão e Competência.
Garante que datas de entrega e meses sejam extraídos com 100% de validade.
"""

import pytest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extrator_perecivel import extrair_data_robusta
from extractors.header_extractor import extrair_data_ocr


class TestExtracaoDatas:
    """Valida o parser de datas e meses em cabeçalhos do CEASA."""

    @pytest.mark.parametrize("texto,data_esp,mes_esp", [
        ("Data: 13/01/2026 às 09:34:25", "13/01/2026", "01"),
        ("Data 27/02/2026 as 11:20", "27/02/2026", "02"),
        ("Data/Hora: 30/12/2025 às 15:34:25", "30/12/2025", "12"),
        ("Data: 05-01-2026", "05/01/2026", "01"),
        ("Data: 24.03.2026", "24/03/2026", "03"),
    ])
    def test_formatos_padrao_de_data(self, texto, data_esp, mes_esp):
        """Testa formatos normais de cabeçalho."""
        data, mes = extrair_data_robusta(texto, "teste.pdf")
        assert data == data_esp
        assert mes == mes_esp

    def test_correcao_ruido_ocr_dia_invalido(self):
        """Garante que '37/02/2026' seja corrigido para '27/02/2026'."""
        texto = "Data 37/02/2026 Número 13116"
        data, mes = extrair_data_robusta(texto, "13116.pdf")
        assert data == "27/02/2026"
        assert mes == "02"

    def test_fallback_arquivos_com_cabecalho_degradado(self):
        """Valida fallback determinístico para guias históricas específicas de 30/01."""
        texto = "Texto muito manchado sem data legivel"
        data, mes = extrair_data_robusta(texto, "12850.pdf")
        assert data == "30/01/2026"
        assert mes == "01"
