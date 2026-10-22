"""
Utilitários de formatação e exportação para planilhas Excel.
"""

from pathlib import Path
from openpyxl import load_workbook


def ajustar_larguras_excel(caminho_xlsx: Path):
    """Formata as larguras das colunas do Excel para visualização elegante."""
    try:
        wb = load_workbook(caminho_xlsx)
        ws = wb.active
        for col_cells in ws.iter_cols():
            col_letter = col_cells[0].column_letter
            max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
            ws.column_dimensions[col_letter].width = min(max_len + 3, 50)
        wb.save(caminho_xlsx)
    except Exception as e:
        print(f"Aviso ao formatar colunas Excel: {e}")
