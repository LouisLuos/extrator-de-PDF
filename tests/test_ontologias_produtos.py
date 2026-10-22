"""
Testes Unitários: Ontologias de Produtos (Hortifrúti, Carnes/Proteínas e Secos/Estocáveis).
Garante que os códigos de contrato do CEASA e termos do OCR mapeiem para os produtos oficiais.
"""

import pytest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extrator_perecivel import normalizar_produto_perecivel
from extrator_nao_perecivel import normalizar_produto_nao_perecivel
from utils.text_cleaner import encontrar_produto_fuzzy
from config.settings import PRODUTOS_ESPERADOS


class TestOntologiasProdutos:
    """Valida a classificação determinística dos alimentos do CEASA."""

    # 1. Testes de Perecíveis (Carnes, Frios, Peixes)
    @pytest.mark.parametrize("linha_ocr,esperado", [
        ("CEASA42-2 LINGUICA CALABRESA 10 KG 340,000", "LINGUICA CALABRESA KG"),
        ("CEASA43-3 SALSICHA HOT DOG 18 KG 666,000", "SALSICHA HOT DOG KG"),
        ("CEASA37-2 CARNE DE AVE CONGELADA COXA E SOBRECOXA 20 KG", "CARNE DE AVE CONGELADA COXA E SOBRECOXA KG"),
        ("CEASA44-4 CARNE CONGELADA DE SUINO SEM OSSO - LOMBO 22 KG", "CARNE CONGELADA DE SUINO SEM OSSO - LOMBO KG"),
        ("CEASA36-2 CARNE BOVINA SALGADA CURADA DESSECADA OU 120,000", "CARNE BOVINA SALGADA CURADA DESSECADA KG"),
        ("CEASA36-2 CARNE BOVINA SALGADA CURADA DEBBECADA 0]", "CARNE BOVINA SALGADA CURADA DESSECADA KG"),
        ("CEASA38-2 CARNE BOVINA DE SEGUNDA - MUSCULO 401,870", "CARNE BOVINA DE SEGUNDA - MUSCULO KG"),
        ("CEASA38-2 CARNE BOVINA DE SEGUNDA - MUSCUI 203,524", "CARNE BOVINA DE SEGUNDA - MUSCULO KG"),
        ("CEASA39-3 CARNE DE CHARQUE DO TIPO ROJAO 10 KG", "CARNE DE CHARQUE DO TIPO ROJAO KG"),
        ("CEASA45-1 MUIDO CONGELADO DE BOVINO - FIGADO 123,200", "MUIDO CONGELADO DE BOVINO - FIGADO KG"),
        ("CEASA115-2 FILE DE PEIXE 10 KG 360,000", "FILE DE PEIXE KG"),
    ])
    def test_produtos_pereciveis(self, linha_ocr, esperado):
        assert normalizar_produto_perecivel(linha_ocr) == esperado

    # 2. Testes de Não Perecíveis (Secos e Mercearia)
    @pytest.mark.parametrize("linha_ocr,esperado", [
        ("CEASA05-0 ACUCAR CRISTAL 1 KG 360,000 KG", "ACUCAR CRISTAL 1 KG"),
        ("CEASA08-0 ARROZ PARBOLIZADO 1 KG 370,000", "ARROZ PARBOILIZADO 1 KG"),
        ("CEASA20-1 FARINHA DE TRIGO 25 KG 15,000 FD", "FARINHA DE TRIGO 25 KG"),
        ("CEASA19-0 FARINHA DE MANDIOCA 1 KG 140,000", "FARINHA DE MANDIOCA 1 KG"),
        ("CEASA23-0 FEIJAO CARIOCA 1 KG 200,000", "FEIJAO CARIOCA 1 KG"),
        ("CEASA21-0 FEIJAO PRETO 1 KG 84,000", "FEIJAO PRETO 1 KG"),
        ("CEASA22-0 FEIJAO MACASSAR 1 KG 81,000", "FEIJAO MACASSAR 1 KG"),
        ("CEASA33-0 OLEO DE SOJA 900 ML 140,000", "OLEO DE SOJA 900 ML"),
        ("CEASA26-1 LEITE EM PO INTEGRAL 200 G 495,000", "LEITE EM PO INTEGRAL 200 G"),
        ("CEASA32-1 MILHO DE MUNGUNZA 500 G 134,000", "MILHO DE MUNGUNZA 500 G"),
        ("CEASA28-2 MACARRAO 500 G 130,000", "MACARRAO 500 G"),
        ("CEASA34-0 SAL 1 KG 93,000", "SAL 1 KG"),
        ("CEASA35-0 VINAGRE 500 ML 120,000", "VINAGRE 500 ML"),
        ("CEASA11-0 CAFE EM PO 250 G 113,000", "CAFE EM PO 250 G"),
    ])
    def test_produtos_nao_pereciveis(self, linha_ocr, esperado):
        assert normalizar_produto_nao_perecivel(linha_ocr) == esperado

    # 3. Testes de Hortifrúti (Fuzzy Matching)
    @pytest.mark.parametrize("texto,esperado", [
        ("ABOBORA JACAREZINHO 100 KG", "ABOBORA"),
        ("BATATA DOCE BRANCA", "BATATA DOCE"),
        ("OVOS VERMELHOS CARTELA", "OVOS"),
        ("BANANA PRATA CLIMATIZADA", "BANANA"),
        ("MELANCIA REDONDA", "MELANCIA"),
    ])
    def test_produtos_hortifrute(self, texto, esperado):
        resultado = encontrar_produto_fuzzy(texto, PRODUTOS_ESPERADOS)
        assert resultado == esperado

    # 4. Descarte de Linhas Falsas / Ruídos
    @pytest.mark.parametrize("linha_invalida", [
        "TOTAIS: 3.186,000 2.439,470",
        "Assinatura do Nutricionista",
        "A servico do CEASA/PE-O.S. 215",
        "Motorista: ELISSANDRO BRAGA Veiculo: GCF9H50",
    ])
    def test_descarte_de_ruidos_de_carimbos(self, linha_invalida):
        assert normalizar_produto_perecivel(linha_invalida) is None
        assert normalizar_produto_nao_perecivel(linha_invalida) is None

    # 5. Detecção de Reposição (SIM / NAO)
    @pytest.mark.parametrize("texto,esperado", [
        ("Operação dispensada de emissão de NF. Guia de entrega referente a semana de 29/12/2025", "NAO"),
        ("Operação dispensada de emissão de NF. Reposição da guia 12821 referente a semana de 02 a 06/02/2026", "SIM"),
        ("LACRES: 15866; 15853 REPOSIÇÃO GUIA 12779 DA SEMANA 26/01/2026", "SIM"),
        ("Observação: [ ] FALTA [ ] DEVOLUÇÃO REPOSIÇÃO ( ) SIM ( ) NÃO", "NAO"),
        ("Observação: [ ] FALTA [ ] DEVOLUÇÃO REPOSIÇÃO (X) SIM ( ) NÃO", "SIM"),
        ("Observação: [ ] FALTA [ ] DEVOLUÇÃO REPOSIÇÃO CA) SIM O) NÃO", "SIM"),
        ("Observação: REPOSIÇÃO: SIM", "SIM"),
    ])
    def test_deteccao_reposicao(self, texto, esperado):
        from utils.text_cleaner import detectar_reposicao
        assert detectar_reposicao(texto) == esperado
