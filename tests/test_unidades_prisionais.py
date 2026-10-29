"""
Testes Unitários: Resolução e Normalização Canônica das Unidades Prisionais de PE (SERES-PE).
Garante que todas as 23 unidades sejam identificadas sem ruídos fiscais (LF, CNPJ, ISENTO).
"""

import pytest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.domain.guia_service import identificar_unidade_prisional, UNIDADES_CANONICAS
from utils.text_cleaner import limpar_nome_lugar


class TestUnidadesPrisionais:
    """Valida a resolução de presídios em cenários ideais e ruidosos."""

    @pytest.mark.parametrize("sigla_esperada,nome_oficial", [
        ("PFDB", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO"),
        ("PJALLB", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS"),
        ("PPLL", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO"),
        ("PVSA", "PVSA - PRESÍDIO DE VITÓRIA DE SANTO ANTÃO"),
        ("PDEPG", "PDEPG - PENITENCIÁRIA DR. ÊNIO PESSOA GUERRA"),
        ("PSAL", "PSAL - PRESÍDIO DE SALGUEIRO"),
        ("PDEG", "PDEG - PENITENCIÁRIA DR. EVALDO GOMES"),
        ("CPFR", "CPFR - COLÔNIA PENAL FEMININA DO RECIFE"),
        ("PDRRL", "PDRRL - PRESÍDIO RORINILDO DA ROCHA LEÃO"),
        ("CRA", "CRA - CENTRO DE RESSOCIALIZAÇÃO DO AGRESTE"),
        ("PJPS", "PJPS - PENITENCIÁRIA JUIZ PLÁCIDO DE SOUZA"),
        ("PSCC", "PSCC - PRESÍDIO DE SANTA CRUZ DO CAPIBARIBE"),
        ("PABA", "PABA - PRESÍDIO ADVOGADO BRITO ALVES"),
        ("CPFB", "CPFB - COLÔNIA PENAL FEMININA DE BUÍQUE"),
        ("PDAD", "PDAD - PRESÍDIO DESEMBARGADOR AUGUSTO DUQUE"),
        ("PTAC", "PTAC - PENITENCIÁRIA DE TACAIMBÓ"),
        ("CSP", "CSP - CENTRO DE SAÚDE PENAL"),
        ("COTEL", "COTEL - CENTRO DE OBSERVAÇÃO E TRIAGEM"),
        ("PFAL", "PFAL - COLÔNIA PENAL FEMININA DE ABREU E LIMA"),
        ("PAISJ", "PAISJ - PENITENCIÁRIA AGROINDUSTRIAL SÃO JOÃO"),
        ("PI", "PI - PRESÍDIO DE IGARASSU"),
        ("PIT", "PIT - PRESÍDIO DE ITAQUITINGA"),
        ("PIT II", "PIT II - PRESÍDIO DE ITAQUITINGA II"),
    ])
    def test_catalogo_23_unidades_presentes(self, sigla_esperada, nome_oficial):
        """Verifica se todas as 23 unidades canônicas estão cadastradas."""
        encontrado = any(u[0] == sigla_esperada and u[1] == nome_oficial for u in UNIDADES_CANONICAS)
        assert encontrado, f"Unidade {sigla_esperada} não encontrada no catálogo canônico."

    @pytest.mark.parametrize("texto_ruidoso,esperado", [
        ("Nome: PVSA PRESIDIO DE VITORIA DE SANTOI.F: 0629085800", "PVSA - PRESÍDIO DE VITÓRIA DE SANTO ANTÃO"),
        ("Nome: PFDB PRESÍDIO FREI DAMIAO DE LF: — 06290858002753", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO"),
        ("Nome: CPFR - COLONIA PENAL FEMININA DO RECIFE I.F: ISENTO", "CPFR - COLÔNIA PENAL FEMININA DO RECIFE"),
        ("Nome: COTEL - CENTRO DE OBSERVACAO E TRIAGEM FONE: 813084", "COTEL - CENTRO DE OBSERVAÇÃO E TRIAGEM"),
        ("Nome: PIT II - PRESÍDIO DE ITAQUITINGA Il LF: ISENTO", "PIT II - PRESÍDIO DE ITAQUITINGA II"),
        ("Nome: PIT - PRESÍDIO DE ITAQUITINGA LF: ISENTO", "PIT - PRESÍDIO DE ITAQUITINGA"),
        ("Nomo! PSAL - PRESIDIO DE SALGUEIRO LF: 06290858002400", "PSAL - PRESÍDIO DE SALGUEIRO"),
        ("Noma: PDEG - PENITENCIARIA DR. EVALDO GOMES CEP: 56300000", "PDEG - PENITENCIÁRIA DR. EVALDO GOMES"),
    ])
    def test_identificacao_com_ruidos_de_ocr(self, texto_ruidoso, esperado):
        """Garante que ruídos de scanner (LF, IF, pontuação) sejam expurgados na identificação."""
        resultado = identificar_unidade_prisional(texto_ruidoso)
        assert resultado == esperado

    def test_limpeza_de_numeros_soltos(self):
        """Valida que números de páginas ou CNPJ colados sejam removidos pelo text_cleaner."""
        bruto = "PRESIDIO DE IGARASSU 06290858000548 1234"
        limpo = limpar_nome_lugar(bruto)
        assert not any(c.isdigit() for c in limpo)
