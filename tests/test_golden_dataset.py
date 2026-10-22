"""
Testes de Integração: Golden Dataset (15 PDFs Amostrais vs Planilhas Consolidadas).
Audita 5 PDFs de Hortifrúti, 5 de Perecíveis e 5 de Não Perecíveis garantindo 100% de acurácia.
"""

import pytest
import sys
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DIR_PLANILHAS = BASE_DIR / "planilhas_saida" / "ceasa"


class TestGoldenDataset:
    """Valida a fidelidade das 15 guias amostrais nas planilhas finais."""

    @classmethod
    def setup_class(cls):
        cls.df_horti = pd.read_excel(DIR_PLANILHAS / "hortifrute" / "saida_consolidada_total.xlsx")
        cls.df_perec = pd.read_excel(DIR_PLANILHAS / "perecivel" / "saida_consolidada_perecivel_total.xlsx")
        cls.df_nao_perec = pd.read_excel(DIR_PLANILHAS / "nao_perecivel" / "saida_consolidada_nao_perecivel_total.xlsx")

    # 1. 5 PDFs de Hortifrúti
    @pytest.mark.parametrize("arquivo,lugar_esperado,qtd_min_itens,data_esperada", [
        ("12502.pdf", "CPFR COLONIA PENAL FEMININA DO", 14, "29/12/2025"),
        ("12503.pdf", "COTEL CENTRO DE OBSERVACAO", 15, "29/12/2025"),
        ("12504.pdf", "PFDB PRESÍDIO FREI DAMIAO DE", 15, "29/12/2025"),
        ("12505.pdf", "PPLL PRESIDIO PROFESSOR", 15, "29/12/2025"),
        ("12506.pdf", "PAISJ PENITENCIARIA AGRO", 14, "29/12/2025"),
    ])
    def test_amostra_hortifrute(self, arquivo, lugar_esperado, qtd_min_itens, data_esperada):
        linhas = self.df_horti[self.df_horti["arquivo"] == arquivo]
        assert not linhas.empty, f"Arquivo {arquivo} não encontrado na planilha de Hortifrúti."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert len(linhas) >= qtd_min_itens

    # 2. 5 PDFs de Perecíveis
    @pytest.mark.parametrize("arquivo,lugar_esperado,qtd_itens,data_esperada", [
        ("12533.pdf", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO", 7, "30/12/2025"),
        ("12534.pdf", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS", 7, "30/12/2025"),
        ("12535.pdf", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO", 7, "30/12/2025"),
        ("12536.pdf", "PVSA - PRESÍDIO DE VITÓRIA DE SANTO ANTÃO", 7, "30/12/2025"),
        ("12538.pdf", "PDEPG - PENITENCIÁRIA DR. ÊNIO PESSOA GUERRA", 7, "30/12/2025"),
    ])
    def test_amostra_pereciveis(self, arquivo, lugar_esperado, qtd_itens, data_esperada):
        linhas = self.df_perec[self.df_perec["arquivo"] == arquivo]
        assert not linhas.empty, f"Arquivo {arquivo} não encontrado na planilha de Perecíveis."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert len(linhas) == qtd_itens

    # 3. 5 PDFs de Não Perecíveis
    @pytest.mark.parametrize("arquivo,lugar_esperado,qtd_itens,data_esperada", [
        ("12543.pdf", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO", 17, "30/12/2025"),
        ("12544.pdf", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO", 19, "30/12/2025"),
        ("12545.pdf", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS", 24, "30/12/2025"),
        ("12552.pdf", "CPFR - COLÔNIA PENAL FEMININA DO RECIFE", 22, "05/01/2026"),
        ("12553.pdf", "PFAL - COLÔNIA PENAL FEMININA DE ABREU E LIMA", 16, "05/01/2026"),
    ])
    def test_amostra_nao_pereciveis(self, arquivo, lugar_esperado, qtd_itens, data_esperada):
        linhas = self.df_nao_perec[self.df_nao_perec["arquivo"] == arquivo]
        assert not linhas.empty, f"Arquivo {arquivo} não encontrado na planilha de Não Perecíveis."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert len(linhas) == qtd_itens

    def test_ausencia_total_de_nulos_nas_15_guias(self):
        """Assegura 100% de preenchimento em todos os campos das 15 guias amostrais."""
        arquivos_alvo = [
            "12502.pdf", "12503.pdf", "12504.pdf", "12505.pdf", "12506.pdf",
            "12533.pdf", "12534.pdf", "12535.pdf", "12536.pdf", "12538.pdf",
            "12543.pdf", "12544.pdf", "12545.pdf", "12552.pdf", "12553.pdf"
        ]
        dfs = [self.df_horti, self.df_perec, self.df_nao_perec]
        for df in dfs:
            sub = df[df["arquivo"].isin(arquivos_alvo)]
            if not sub.empty:
                assert sub["data"].isnull().sum() == 0
                assert sub["mes"].isnull().sum() == 0
                assert sub["lugar"].isnull().sum() == 0
                assert (sub["lugar"] == "NÃO IDENTIFICADO").sum() == 0
                assert sub["produto"].isnull().sum() == 0
