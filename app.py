"""
Ponto de Partida Único (Composition Root) — Extrator de Guias Prisionais (SERES-PE / CEASA).

Arquitetura Limpa (Clean Architecture):
- Core / Domain:       src/core/domain/guia_service.py
- Application / Cases: src/core/use_cases/processar_lote_guias.py
- Interface Adapters:  src/adapters/web_controller.py & src/adapters/cli_controller.py
- Infrastructure:      src/infra/ocr_cache_engine.py & src/utils/excel_exporter.py
"""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from adapters.cli_controller import executar_cli
from adapters.web_controller import criar_app_web, iniciar_servidor_web
from core.domain.guia_service import classificar_categoria_pdf
from infra.ocr_cache_engine import extrair_texto_pagina_acelerado

app = criar_app_web()

__all__ = [
    "app",
    "classificar_categoria_pdf",
    "extrair_texto_pagina_acelerado",
]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        executar_cli(sys.argv[1:])
    else:
        iniciar_servidor_web(app)
