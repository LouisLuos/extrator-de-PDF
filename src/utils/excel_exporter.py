"""
Utilitários de formatação e exportação para planilhas Excel.
Gera Tabelas Oficiais do Excel (ListObject) com filtros e estilos corporativos.
"""

import re
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


def formatar_como_tabela_excel(caminho_xlsx: Path, estilo: str = "TableStyleMedium9"):
    """
    Transforma os dados de uma planilha Excel em uma Tabela Oficial do Excel (ListObject):
    - Cabeçalhos estilizados com botões de filtro automáticos (AutoFilter)
    - Linhas zebradas alternadas (Banded Rows)
    - Ajuste automático de largura de colunas (Autofit)
    """
    try:
        wb = load_workbook(caminho_xlsx)
        ws = wb.active

        max_row = ws.max_row
        max_col = ws.max_column

        if max_row < 2 or max_col < 1:
            wb.close()
            return

        # Nome da tabela válido no Excel (sem espaços, sem hífens, começando com letra)
        nome_base = re.sub(r"[^a-zA-Z0-9_]", "_", caminho_xlsx.stem)
        nome_base = re.sub(r"_+", "_", nome_base).strip("_")
        if not nome_base or nome_base[0].isdigit():
            nome_base = f"Tab_{nome_base}"
        nome_tabela = f"Tab_{nome_base[:25]}"

        # Se já existir tabela com esse nome na worksheet, remove primeiro
        tabelas_existentes = list(ws.tables.keys())
        for t_nome in tabelas_existentes:
            del ws.tables[t_nome]

        col_fim = get_column_letter(max_col)
        ref_tabela = f"A1:{col_fim}{max_row}"

        tabela = Table(displayName=nome_tabela, ref=ref_tabela)
        tabela.tableStyleInfo = TableStyleInfo(
            name=estilo,
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        ws.add_table(tabela)

        # Ajuste de largura das colunas
        for col_cells in ws.iter_cols():
            col_letter = col_cells[0].column_letter
            max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 50)

        wb.save(caminho_xlsx)
        wb.close()
    except Exception as e:
        print(f"Aviso ao formatar tabela em {caminho_xlsx.name}: {e}")


def ajustar_larguras_excel(caminho_xlsx: Path):
    """Aplica formatação completa de Tabela Oficial do Excel e autoajuste de largura."""
    formatar_como_tabela_excel(caminho_xlsx)


def salvar_excel_seguro(df, caminho_destino: Path) -> Path:
    """Salva um DataFrame em Excel com formatação de tabela e fallback para PermissionError."""
    caminho_destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(caminho_destino, index=False)
        ajustar_larguras_excel(caminho_destino)
        print(f"✅ Planilha gerada com sucesso: {caminho_destino.name} ({len(df)} registros)")
        return caminho_destino
    except PermissionError:
        backup_nome = caminho_destino.with_name(f"{caminho_destino.stem}_novo.xlsx")
        df.to_excel(backup_nome, index=False)
        ajustar_larguras_excel(backup_nome)
        print(f"⚠️ Arquivo aberto no Excel. Salvo como: {backup_nome.name} ({len(df)} registros)")
        return backup_nome
