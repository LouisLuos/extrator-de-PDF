"""
Atalho de Compatibilidade para Execução em Lote (CLI).

Toda a lógica de negócio e orquestração foi desacoplada para:
- Caso de Uso: `src/core/use_cases/processar_lote_guias.py`
- Controlador CLI: `src/adapters/cli_controller.py`
- Ponto de Entrada Oficial: `app.py`
"""

from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from adapters.cli_controller import executar_cli
from core.domain.guia_service import obter_chave_ordenacao
from core.use_cases.processar_lote_guias import (
    executar_pipeline_hortifrute as executar_pipeline,
    processar_lote_pdfs,
)
from utils.excel_exporter import salvar_excel_seguro

__all__ = [
    "executar_pipeline",
    "obter_chave_ordenacao",
    "processar_lote_pdfs",
    "salvar_excel_seguro",
]

if __name__ == "__main__":
    executar_cli(sys.argv[1:])
