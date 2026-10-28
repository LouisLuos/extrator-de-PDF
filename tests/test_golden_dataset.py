"""
Testes de Integração: Golden Dataset (15 PDFs Amostrais vs Planilhas Consolidadas).
Audita 5 PDFs de Hortifrúti, 5 de Perecíveis e 5 de Não Perecíveis garantindo 100% de acurácia.
"""

from pathlib import Path
import sys
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
DIR_PLANILHAS = BASE_DIR / "planilhas_saida" / "ceasa"

PLANILHAS_DISPONIVEIS = (
    (DIR_PLANILHAS / "hortifrute" / "saida_consolidada_total.xlsx").exists()
    and (DIR_PLANILHAS / "perecivel" / "saida_consolidada_perecivel_total.xlsx").exists()
    and (DIR_PLANILHAS / "nao_perecivel" / "saida_consolidada_nao_perecivel_total.xlsx").exists()
)


@pytest.mark.skipif(
    not PLANILHAS_DISPONIVEIS,
    reason="Planilhas consolidadas do Golden Dataset não encontradas nesta máquina (disponíveis na máquina de trabalho).",
)
class TestGoldenDataset:
    """Valida a fidelidade das 15 guias amostrais nas planilhas finais consolidadas."""

    @classmethod
    def setup_class(cls):
        cls.df_horti = pd.read_excel(DIR_PLANILHAS / "hortifrute" / "saida_consolidada_total.xlsx")
        cls.df_perec = pd.read_excel(DIR_PLANILHAS / "perecivel" / "saida_consolidada_perecivel_total.xlsx")
        cls.df_nao_perec = pd.read_excel(DIR_PLANILHAS / "nao_perecivel" / "saida_consolidada_nao_perecivel_total.xlsx")

    # 1. 5 PDFs de Hortifrúti
    @pytest.mark.parametrize(
        "arquivo,lugar_esperado,data_esperada,rep_esperada",
        [
            ("12502.pdf", "CPFR COLONIA PENAL FEMININA DO", "29/12/2025", "NAO"),
            ("12503.pdf", "COTEL CENTRO DE OBSERVACAO", "29/12/2025", "NAO"),
            ("12504.pdf", "PFDB PRESÍDIO FREI DAMIAO DE", "29/12/2025", "NAO"),
            ("12505.pdf", "PPLL PRESIDIO PROFESSOR", "29/12/2025", "NAO"),
            ("12506.pdf", "PAISJ PENITENCIARIA AGRO", "29/12/2025", "NAO"),
        ],
    )
    def test_amostra_hortifrute(self, arquivo, lugar_esperado, data_esperada, rep_esperada):
        linhas = self.df_horti[self.df_horti["arquivo"] == arquivo]
        assert len(linhas) == 1, f"Guia {arquivo} deve possuir exatamente 1 linha na planilha."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert linhas["reposicao"].iloc[0] == rep_esperada

    # 2. 5 PDFs de Perecíveis
    @pytest.mark.parametrize(
        "arquivo,lugar_esperado,data_esperada,rep_esperada",
        [
            ("12533.pdf", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO", "30/12/2025", "NAO"),
            ("12534.pdf", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS", "30/12/2025", "NAO"),
            ("12535.pdf", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO", "30/12/2025", "NAO"),
            ("12536.pdf", "PVSA - PRESÍDIO DE VITÓRIA DE SANTO ANTÃO", "30/12/2025", "NAO"),
            ("12538.pdf", "PDEPG - PENITENCIÁRIA DR. ÊNIO PESSOA GUERRA", "30/12/2025", "NAO"),
        ],
    )
    def test_amostra_pereciveis(self, arquivo, lugar_esperado, data_esperada, rep_esperada):
        linhas = self.df_perec[self.df_perec["arquivo"] == arquivo]
        assert len(linhas) == 1, f"Guia {arquivo} deve possuir exatamente 1 linha na planilha."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert linhas["reposicao"].iloc[0] == rep_esperada

    # 3. 5 PDFs de Não Perecíveis
    @pytest.mark.parametrize(
        "arquivo,lugar_esperado,data_esperada,rep_esperada",
        [
            ("12543.pdf", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO", "30/12/2025", "NAO"),
            ("12544.pdf", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO", "30/12/2025", "NAO"),
            ("12545.pdf", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS", "30/12/2025", "NAO"),
            ("12552.pdf", "CPFR - COLÔNIA PENAL FEMININA DO RECIFE", "05/01/2026", "NAO"),
            ("12553.pdf", "PFAL - COLÔNIA PENAL FEMININA DE ABREU E LIMA", "05/01/2026", "NAO"),
        ],
    )
    def test_amostra_nao_pereciveis(self, arquivo, lugar_esperado, data_esperada, rep_esperada):
        linhas = self.df_nao_perec[self.df_nao_perec["arquivo"] == arquivo]
        assert len(linhas) == 1, f"Guia {arquivo} deve possuir exatamente 1 linha na planilha."
        assert linhas["lugar"].iloc[0] == lugar_esperado
        assert linhas["data"].iloc[0] == data_esperada
        assert linhas["reposicao"].iloc[0] == rep_esperada

    def test_ausencia_total_de_nulos_e_colunas_obrigatorias(self):
        """Assegura estrutura exata de colunas e 0 valores nulos em todas as planilhas consolidadas."""
        colunas_esperadas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
        dfs = [self.df_horti, self.df_perec, self.df_nao_perec]
        for df in dfs:
            assert list(df.columns) == colunas_esperadas
            assert df["data"].isnull().sum() == 0
            assert df["mes"].isnull().sum() == 0
            assert df["lugar"].isnull().sum() == 0
            assert (df["lugar"] == "NÃO IDENTIFICADO").sum() == 0
            assert df["reposicao"].isnull().sum() == 0
            assert df["reposicao"].isin(["SIM", "NAO"]).all()
