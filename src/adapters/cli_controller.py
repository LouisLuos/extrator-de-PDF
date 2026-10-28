"""
Camada Interface Adapters: Controlador de Linha de Comando (CLI / Processamento em Lote).

Responsabilidade (Clean Architecture):
- Interpretar argumentos passados via terminal e acionar o Caso de Uso correspondente
  (Hortifrúti, Perecíveis ou Não Perecíveis).
"""

import argparse
from typing import List, Optional

from core.use_cases.processar_lote_guias import (
    executar_pipeline_hortifrute,
    executar_pipeline_nao_pereciveis,
    executar_pipeline_pereciveis,
)


def executar_cli(argv: Optional[List[str]] = None) -> None:
    """Executa o modo batch/CLI a partir dos argumentos informados no terminal."""
    parser = argparse.ArgumentParser(
        description="Extrator de Guias Prisionais (SERES-PE / CEASA) - Modo CLI / Lote"
    )
    parser.add_argument(
        "--batch",
        "--categoria",
        dest="categoria",
        choices=["hortifrute", "perecivel", "nao_perecivel", "todos"],
        default="hortifrute",
        help="Categoria de pastas locais a processar em lote (padrão: hortifrute).",
    )
    args = parser.parse_args(argv)

    if args.categoria == "hortifrute":
        executar_pipeline_hortifrute()
    elif args.categoria == "perecivel":
        executar_pipeline_pereciveis()
    elif args.categoria == "nao_perecivel":
        executar_pipeline_nao_pereciveis()
    elif args.categoria == "todos":
        executar_pipeline_hortifrute()
        executar_pipeline_pereciveis()
        executar_pipeline_nao_pereciveis()
