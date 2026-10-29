"""
Script de Comparação e Auditoria: Baseline vs. Nova Extração.

Compara o gabarito histórico (saida_hibrida.xlsx) com o resultado recém-gerado
(saida_extracao_janeiro.xlsx) medindo:
1. Cobertura de arquivos processados.
2. Contagem total de produtos extraídos por arquivo.
3. Consistência das datas e locais identificados.
4. Divergências e itens faltantes/novos.
"""

import sys
from pathlib import Path
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
GABARITO_PATH = BASE_DIR / "saida_hibrida.xlsx"
NOVO_PATH = BASE_DIR / "extrator_pdf" / "saida_extracao_janeiro.xlsx"


def comparar_resultados():
    if not GABARITO_PATH.exists():
        print(f"❌ Gabarito não encontrado em: {GABARITO_PATH}")
        return
    if not NOVO_PATH.exists():
        print(f"❌ Nova saída ainda não gerada em: {NOVO_PATH}")
        return

    df_gab = pd.read_excel(GABARITO_PATH)
    df_novo = pd.read_excel(NOVO_PATH)

    print("=" * 60)
    print("📊 RELATÓRIO DE AUDITORIA E COMPARAÇÃO")
    print("=" * 60)
    print(f"Total de registros no Gabarito Histórico: {len(df_gab)}")
    print(f"Total de registros na Nova Extração:     {len(df_novo)}")

    # Filtrar o gabarito apenas para os arquivos presentes no lote testado
    arquivos_novos = set(df_novo["arquivo"].dropna().unique())
    df_gab_filtrado = df_gab[df_gab["arquivo"].isin(arquivos_novos)]

    print(f"\nArquivos analisados no lote atual: {len(arquivos_novos)}")
    print(f"Registros esperados no gabarito para este lote: {len(df_gab_filtrado)}")
    print(f"Registros capturados pela nova extração:        {len(df_novo)}")

    taxa_cobertura = (len(df_novo) / len(df_gab_filtrado)) * 100 if len(df_gab_filtrado) else 0
    print(f"Taxa de paridade de registros: {taxa_cobertura:.2f}%")

    # Comparação de preenchimento de metadados
    datas_validas_novo = df_novo["data"].notna().sum()
    locais_validos_novo = (df_novo["lugar"] != "NÃO IDENTIFICADO").sum()
    print(f"\nQualidade da Nova Extração:")
    print(f" - Datas preenchidas:  {datas_validas_novo}/{len(df_novo)} ({(datas_validas_novo/len(df_novo))*100:.1f}%)")
    print(f" - Locais detectados:  {locais_validos_novo}/{len(df_novo)} ({(locais_validos_novo/len(df_novo))*100:.1f}%)")

    # Divergências por arquivo
    print("\nDetalhamento por Arquivo (Top 10 comparados):")
    contagem_gab = df_gab_filtrado.groupby("arquivo")["produto"].count()
    contagem_novo = df_novo.groupby("arquivo")["produto"].count()
    comp_df = pd.DataFrame({"Gabarito": contagem_gab, "Novo": contagem_novo}).fillna(0).astype(int)
    comp_df["Dif"] = comp_df["Novo"] - comp_df["Gabarito"]
    print(comp_df.head(10).to_string())


if __name__ == "__main__":
    comparar_resultados()
