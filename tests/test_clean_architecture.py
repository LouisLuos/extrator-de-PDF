"""
Testes Unitários da Arquitetura Limpa (Core / Domain & Use Cases).
Demonstra como testar regras de domínio e reconstituição de tabelas em memória,
sem depender de arquivos externos no disco.
"""

from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.domain.guia_service import (
    GuiaSegmentada,
    RegistroGuiaConsolidada,
    consolidar_guia_segmentada,
    obter_chave_ordenacao,
    segmentar_guias_por_pagina,
)
from core.domain.ontologia_produtos import (
    extrair_produtos_ocr_nao_perecivel,
    extrair_produtos_ocr_perecivel,
)


def test_segmentacao_multiplas_guias_em_memoria():
    paginas = [
        (1, "CABEÇALHO CEASA Número: 12543 Nome: PFDB Data: 30/12/2025"),
        (2, "Continuação da Guia Número: 12543 itens adicionais"),
        (3, "CABEÇALHO CEASA Número: 12544 Nome: PPLL Data: 05/01/2026 REPOSIÇÃO: SIM"),
    ]
    guias = segmentar_guias_por_pagina(paginas)
    assert len(guias) == 2
    assert guias[0].numero == "12543"
    assert guias[0].paginas == [1, 2]
    assert guias[1].numero == "12544"
    assert guias[1].paginas == [3]


def test_consolidar_guia_em_value_object():
    guia = GuiaSegmentada(
        numero="12800",
        paginas=[1],
        textos=["Nome: CPFR - COLÔNIA PENAL FEMININA DO RECIFE Data: 15/02/2026 Reposição da guia 12700"],
    )
    registro: RegistroGuiaConsolidada = consolidar_guia_segmentada(
        guia=guia,
        nome_arquivo_original="lote_fevereiro.pdf",
        pagina_continua_global=10,
        tem_multi_guias=True,
    )
    assert registro.arquivo == "lote_fevereiro.pdf [Guia 12800]"
    assert registro.pagina == 10
    assert registro.lugar == "CPFR - COLÔNIA PENAL FEMININA DO RECIFE"
    assert registro.data == "15/02/2026"
    assert registro.mes == "02"
    assert registro.reposicao == "SIM"


def test_extracao_tabular_ocr_em_memoria():
    dados_ocr_fake = {
        "text": ["CEASA42-2", "LINGUICA", "CALABRESA", "TOTAIS:", "100,00", "CEASA08-0", "ARROZ"],
        "top": [100, 102, 101, 200, 201, 300, 302],
        "left": [10, 80, 160, 10, 100, 10, 90],
    }
    pereciveis = extrair_produtos_ocr_perecivel(dados_ocr_fake)
    nao_pereciveis = extrair_produtos_ocr_nao_perecivel(dados_ocr_fake)

    assert pereciveis == ["LINGUICA CALABRESA KG"]
    assert nao_pereciveis == ["ARROZ PARBOILIZADO 1 KG"]


def test_ordenacao_natural_arquivos():
    arquivos = ["12510.pdf", "12502.pdf", "999.pdf"]
    ordenados = sorted(arquivos, key=obter_chave_ordenacao)
    assert ordenados == ["999.pdf", "12502.pdf", "12510.pdf"]

