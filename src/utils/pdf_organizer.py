"""
Organizador Automatizado de PDFs por Mês e Unidade Prisional.

Lê os metadados gerados pela extração e copia/organiza os arquivos PDF em:
extrator_pdf/PDFs_organizados/<MES>/<LUGAR>/<ARQUIVO.pdf>
"""

import shutil
import sys
from pathlib import Path
import pandas as pd
import re

SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Garantir UTF-8 no console Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config.settings import BASE_DIR, DIR_PDFS, ARQUIVO_SAIDA_XLSX

DIR_ORGANIZADO = BASE_DIR / "PDFs_organizados"

MAPA_MESES = {
    "01": "01_JANEIRO",
    "02": "02_FEVEREIRO",
    "03": "03_MARCO",
    "04": "04_ABRIL",
    "05": "05_MAIO",
    "06": "06_JUNHO",
    "07": "07_JULHO",
    "08": "08_AGOSTO",
    "09": "09_SETEMBRO",
    "10": "10_OUTUBRO",
    "11": "11_NOVEMBRO",
    "12": "12_DEZEMBRO",
}


def sanitizar_nome_pasta(nome: str) -> str:
    """Substitui caracteres inválidos para pastas no Windows."""
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "", str(nome)).strip()
    return nome_limpo if nome_limpo else "NAO_IDENTIFICADO"


def organizar_arquivos_pdf(modo_mover: bool = False):
    """
    Organiza os PDFs nas pastas hierárquicas por Mês e Local.
    Por padrão copia (modo_mover=False) para não apagar a pasta original.
    """
    # Preferir a versão mais recente gerada
    planilha = ARQUIVO_SAIDA_XLSX
    backup_v2 = ARQUIVO_SAIDA_XLSX.with_name(f"{ARQUIVO_SAIDA_XLSX.stem}_novo.xlsx")
    if backup_v2.exists():
        planilha = backup_v2

    if not planilha.exists():
        print(f"❌ Planilha com metadados não encontrada: {planilha}")
        return

    df = pd.read_excel(planilha)
    mapa = df.groupby("arquivo")[["mes", "lugar"]].first().reset_index()

    DIR_ORGANIZADO.mkdir(parents=True, exist_ok=True)
    print(f"\n📂 Iniciando organização de {len(mapa)} arquivos em: {DIR_ORGANIZADO.name}\n")

    sucessos = 0
    for _, row in mapa.iterrows():
        nome_arq = str(row["arquivo"])
        mes_val = f"{int(row['mes']):02d}" if pd.notna(row["mes"]) else "OUTROS"
        pasta_mes = MAPA_MESES.get(mes_val, f"MES_{mes_val}")

        # Salvar diretamente dentro da pasta do Mês (sem subpastas de presídio)
        destino_pasta = DIR_ORGANIZADO / pasta_mes
        destino_pasta.mkdir(parents=True, exist_ok=True)

        origem = DIR_PDFS / nome_arq
        destino = destino_pasta / nome_arq

        if origem.exists():
            if modo_mover:
                shutil.move(str(origem), str(destino))
            else:
                shutil.copy2(str(origem), str(destino))
            sucessos += 1

    acao = "Movidos" if modo_mover else "Copiados e organizados"
    print(f"✅ {sucessos} arquivos {acao} com sucesso!")
    print(f"   Estrutura: PDFs_organizados / [MÊS] / arquivo.pdf\n")


if __name__ == "__main__":
    organizar_arquivos_pdf(modo_mover=False)
