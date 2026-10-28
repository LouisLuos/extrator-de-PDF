"""
Módulo Adaptador de Extração de Alimentos PERECÍVEIS (Carnes, Frios, Proteínas e Pescados).

Refatorado segundo a Clean Architecture:
- Regras de Domínio (Unidades, Datas, Reposição): `src/core/domain/guia_service.py`
- Ontologia de Produtos Perecíveis:               `src/core/domain/ontologia_produtos.py`
- Motor de OCR e Cache JSON:                      `src/infra/ocr_cache_engine.py`
- Caso de Uso de Processamento em Lote:           `src/core/use_cases/processar_lote_guias.py`
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.domain.guia_service import (
    UNIDADES_CANONICAS,
    detectar_reposicao,
    extrair_data_robusta,
    identificar_unidade_prisional,
    obter_chave_ordenacao,
)
from core.domain.ontologia_produtos import (
    CATALOGO_PERECIVEIS,
    extrair_produtos_ocr_perecivel,
    normalizar_produto_perecivel,
)

BASE_DIR = SRC_DIR.parent
DIR_PERECIVEL = BASE_DIR / "PDFs" / "perecivel"
DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_SAIDA_PERECIVEL = BASE_DIR / "planilhas_saida" / "ceasa" / "perecivel"


def processar_pagina_ocr_completo(
    pagina: Any, pdf_hash: str, num_pag: int
) -> Tuple[Dict[str, Any], str]:
    """Delega a execução de OCR com cache para a camada de Infraestrutura."""
    from infra.ocr_cache_engine import (
        processar_pagina_ocr_completo as _processar_ocr,
    )

    return _processar_ocr(pagina, pdf_hash, num_pag, dir_cache=DIR_CACHE_PERECIVEL)


def processar_lote_perecivel(arquivos: List[Path], nome_lote: str):
    """Delega o processamento em lote para o Caso de Uso unificado."""
    from core.use_cases.processar_lote_guias import processar_lote_ocr_completo

    return processar_lote_ocr_completo(
        arquivos=arquivos,
        nome_lote=nome_lote,
        dir_cache=DIR_CACHE_PERECIVEL,
    )


def executar_pipeline_pereciveis() -> None:
    """Aciona o Caso de Uso de extração completa de alimentos Perecíveis."""
    from core.use_cases.processar_lote_guias import (
        executar_pipeline_pereciveis as _executar,
    )

    _executar()


__all__ = [
    "CATALOGO_PERECIVEIS",
    "UNIDADES_CANONICAS",
    "detectar_reposicao",
    "executar_pipeline_pereciveis",
    "extrair_data_robusta",
    "extrair_produtos_ocr_perecivel",
    "identificar_unidade_prisional",
    "normalizar_produto_perecivel",
    "obter_chave_ordenacao",
    "processar_lote_perecivel",
    "processar_pagina_ocr_completo",
]

if __name__ == "__main__":
    executar_pipeline_pereciveis()
