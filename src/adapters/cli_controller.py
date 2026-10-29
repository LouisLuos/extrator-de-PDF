"""
Adaptador de Entrada CLI (Driving Adapter / Controller) — Linha de Comando.

Responsabilidades EXCLUSIVAS desta camada:
- Ler argumentos passados pelo terminal (ex.: `hortifrute`, `perecivel`, `nao_perecivel`, `todos`).
- Disparar o Caso de Uso correspondente na camada `core/use_cases`.
"""

from typing import List

from core.use_cases.processar_lote_guias import (
    executar_pipeline_hortifrute,
    executar_pipeline_nao_pereciveis,
    executar_pipeline_pereciveis,
)


def executar_cli(args: List[str]) -> None:
    """Roteia o comando recebido via terminal para o pipeline correspondente."""
    modo = args[0].lower() if args else "hortifrute"

    if modo in ("hortifrute", "hortifruti", "horti"):
        executar_pipeline_hortifrute()
    elif modo in ("perecivel", "pereciveis"):
        executar_pipeline_pereciveis()
    elif modo in ("nao_perecivel", "nao-perecivel", "naoperecivel"):
        executar_pipeline_nao_pereciveis()
    elif modo in ("todos", "all"):
        executar_pipeline_hortifrute()
        executar_pipeline_pereciveis()
        executar_pipeline_nao_pereciveis()
    else:
        print(f"Modo '{modo}' não reconhecido. Executando pipeline padrão (Hortifrúti)...")
        executar_pipeline_hortifrute()
