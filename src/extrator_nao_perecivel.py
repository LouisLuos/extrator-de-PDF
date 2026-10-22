"""
Pipeline especializado para extração de alimentos NÃO PERECÍVEIS (Itens Secos, Estocáveis e Mercearia).

Documentos digitalizados:
- Realiza OCR de página inteira a 300 DPI com cache JSON em cache_ocr_nao_perecivel/
- Extrai metadados do cabeçalho (Data, Mês e Unidade Prisional) com normalização canônica (23 presídios)
- Extrai itens da tabela de estocáveis via códigos de contrato CEASA e ontologia padronizada
- Salva os resultados individuais por mês e consolidados em planilhas_saida/ceasa/nao_perecivel/
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Configurar UTF-8 no console Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np
import pandas as pd
import pymupdf
import pytesseract
from pytesseract import Output

from config.settings import BASE_DIR, DIR_PLANILHAS, DPI, TESSERACT_EXE, TOLERANCIA_LINHA_OCR
from utils.excel_exporter import ajustar_larguras_excel
from utils.text_cleaner import detectar_reposicao

if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

DIR_NAO_PERECIVEL = BASE_DIR / "PDFs" / "nao-perecivel"
DIR_CACHE_NAO_PERECIVEL = BASE_DIR / "cache_ocr_nao_perecivel"
DIR_SAIDA_NAO_PERECIVEL = DIR_PLANILHAS / "ceasa" / "nao_perecivel"

# Tabela Canônica das Unidades Prisionais de Pernambuco (SERES-PE)
UNIDADES_CANONICAS = [
    ("PIT II", "PIT II - PRESÍDIO DE ITAQUITINGA II", ["PIT II", "PIT IL", "PIT 2", "ITAQUITINGA II", "ITAQUITINGA 2"]),
    ("PIT", "PIT - PRESÍDIO DE ITAQUITINGA", ["PIT", "ITAQUITINGA"]),
    ("PFDB", "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO", ["PFDB", "FREI DAMIAO", "FREI DAMIÃO", "BOZZANO"]),
    ("PJALLB", "PJALLB - PRESÍDIO JUIZ ANTÔNIO LUIZ LINS DE BARROS", ["PJALLB", "ANTONIO LUIZ", "ANTÔNIO LUIZ", "LINS DE BARROS"]),
    ("PPLL", "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO", ["PPLL", "LISBOA CORDEIRO", "LISBOA", "PROFESSOR"]),
    ("PVSA", "PVSA - PRESÍDIO DE VITÓRIA DE SANTO ANTÃO", ["PVSA", "VITORIA", "VITÓRIA", "SANTO ANTAO", "SANTO ANTÃO", "SANTOI"]),
    ("PDEPG", "PDEPG - PENITENCIÁRIA DR. ÊNIO PESSOA GUERRA", ["PDEPG", "ENIO PESSOA", "ÊNIO PESSOA", "ENIO", "ÊNIO"]),
    ("PSAL", "PSAL - PRESÍDIO DE SALGUEIRO", ["PSAL", "SALGUEIRO", "PEAL-PRES"]),
    ("PDEG", "PDEG - PENITENCIÁRIA DR. EVALDO GOMES", ["PDEG", "EVALDO GOMES", "EVALDO"]),
    ("CPFR", "CPFR - COLÔNIA PENAL FEMININA DO RECIFE", ["CPFR", "FEMININA DO RECIFE", "FEMININA DO"]),
    ("PDRRL", "PDRRL - PRESÍDIO RORINILDO DA ROCHA LEÃO", ["PDRRL", "RORINILDO", "ROCHA LEAO", "ROCHA LEÃO"]),
    ("CRA", "CRA - CENTRO DE RESSOCIALIZAÇÃO DO AGRESTE", ["CRA", "RESSOCIALIZACAO", "RESSOCIALIZAÇÃO", "AGRESTE"]),
    ("PJPS", "PJPS - PENITENCIÁRIA JUIZ PLÁCIDO DE SOUZA", ["PJPS", "PLACIDO", "PLÁCIDO"]),
    ("PSCC", "PSCC - PRESÍDIO DE SANTA CRUZ DO CAPIBARIBE", ["PSCC", "SANTA CRUZ"]),
    ("PABA", "PABA - PRESÍDIO ADVOGADO BRITO ALVES", ["PABA", "BRITO ALVES", "ADVOGADO BRITO"]),
    ("CPFB", "CPFB - COLÔNIA PENAL FEMININA DE BUÍQUE", ["CPFB", "BUIQUE", "BUÍQUE", "FEMININA DE B"]),
    ("PDAD", "PDAD - PRESÍDIO DESEMBARGADOR AUGUSTO DUQUE", ["PDAD", "AUGUSTO DUQUE", "DESEMBARGADOR"]),
    ("PTAC", "PTAC - PENITENCIÁRIA DE TACAIMBÓ", ["PTAC", "TACAIMBO", "TACAIMBÓ"]),
    ("CSP", "CSP - CENTRO DE SAÚDE PENAL", ["CSP", "SAUDE PENAL", "SAÚDE PENAL", "CENTRO DE SAUDE", "CENTRO DE SAÚDE"]),
    ("COTEL", "COTEL - CENTRO DE OBSERVAÇÃO E TRIAGEM", ["COTEL", "EVERARDO LUNA", "OBSERVAÇÃO E TRIAGEM", "OBSERVACAO E TRIAGEM", "CENTRO DE OBSERVACAO", "EOREL", "RINALDO PINHO"]),
    ("PFAL", "PFAL - COLÔNIA PENAL FEMININA DE ABREU E LIMA", ["PFAL", "ABREU E LIMA", "FEMININA DE ABREU"]),
    ("PAISJ", "PAISJ - PENITENCIÁRIA AGROINDUSTRIAL SÃO JOÃO", ["PAISJ", "PAIS", "AGROINDUSTRIAL", "AGRO INDUSTRIAL", "AGRO-"]),
    ("PI", "PI - PRESÍDIO DE IGARASSU", ["IGARASSU", "IGARASU", " PI "]),
]

# Catálogo Oficial de Itens Não Perecíveis / Estocáveis do CEASA
CATALOGO_NAO_PERECIVEIS = [
    (r"CEASA02", "ADOCANTE 100 ML", ["ADOCANTE", "ADOÇANTE"]),
    (r"CEASA05", "ACUCAR CRISTAL 1 KG", ["ACUCAR", "AÇÚCAR"]),
    (r"CEASA08", "ARROZ PARBOILIZADO 1 KG", ["ARROZ", "PARBOLIZADO", "PARBOILIZADO"]),
    (r"CEASA11", "CAFE EM PO 250 G", ["CAFE", "CAFÉ"]),
    (r"CEASA13", "COMINHO 1 KG", ["COMINHO"]),
    (r"CEASA15", "COLORAU 1 KG", ["COLORAU"]),
    (r"CEASA18", "FUBA 500 G", ["FUBA", "FUBÁ"]),
    (r"CEASA19", "FARINHA DE MANDIOCA 1 KG", ["FARINHA DE MANDIOCA", "MANDIOCA"]),
    (r"CEASA20", "FARINHA DE TRIGO 25 KG", ["FARINHA DE TRIGO", "TRIGO"]),
    (r"CEASA21", "FEIJAO PRETO 1 KG", ["FEIJAO PRETO", "FEIJÃO PRETO"]),
    (r"CEASA22", "FEIJAO MACASSAR 1 KG", ["FEIJAO MACASSAR", "FEIJÃO MACASSAR", "MACASSAR"]),
    (r"CEASA23", "FEIJAO CARIOCA 1 KG", ["FEIJAO CARIOCA", "FEIJÃO CARIOCA", "CARIOCA"]),
    (r"CEASA24", "FERMENTO 500 G", ["FERMENTO"]),
    (r"CEASA26", "LEITE EM PO INTEGRAL 200 G", ["LEITE EM PO", "LEITE EM PÓ"]),
    (r"CEASA27", "LEITE DE COCO 200 ML", ["LEITE DE COCO", "COCO"]),
    (r"CEASA28", "MACARRAO 500 G", ["MACARRAO", "MACARRÃO", "ESPAGUETE"]),
    (r"CEASA30", "MARGARINA 5 KG", ["MARGARINA"]),
    (r"CEASA31", "MELHORADOR EM PASTA 10 KG", ["MELHORADOR"]),
    (r"CEASA32", "MILHO DE MUNGUNZA 500 G", ["MUNGUNZA", "MUNGUNZÁ", "MILHO DE MUNGUN"]),
    (r"CEASA33", "OLEO DE SOJA 900 ML", ["OLEO", "ÓLEO", "SOJA"]),
    (r"CEASA34", "SAL 1 KG", ["SAL 1 KG", "SAL MOIDO", "SAL MOÍDO"]),
    (r"CEASA35", "VINAGRE 500 ML", ["VINAGRE"]),
    (r"CEASA47", "ALHO EM PASTA 1 KG", ["ALHO EM PASTA", "ALHO"]),
    (r"CEASA49", "AVEIA 200 G", ["AVEIA"]),
    (r"CEASA50", "EXTRATO DE TOMATE 4 KG", ["EXTRATO DE TOMATE", "EXTRATO"]),
    (r"CEASA57", "AMEIXA SECA SEM CAROCO 1 KG", ["AMEIXA SECA", "AMEIXA"]),
]


def obter_chave_ordenacao(nome: str):
    stem = os.path.splitext(nome)[0]
    digitos = re.findall(r"\d+", stem)
    return int(digitos[0]) if digitos else stem


def processar_pagina_ocr_completo(pagina: pymupdf.Page, pdf_hash: str, num_pag: int) -> Tuple[Dict[str, Any], str]:
    """Executa OCR na página com gerenciamento de cache local em JSON."""
    DIR_CACHE_NAO_PERECIVEL.mkdir(parents=True, exist_ok=True)
    arquivo_cache = DIR_CACHE_NAO_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_full.json"

    if arquivo_cache.exists():
        with open(arquivo_cache, "r", encoding="utf-8") as f:
            dados_ocr = json.load(f)
    else:
        pix = pagina.get_pixmap(dpi=DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_cinza = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        dados_ocr = pytesseract.image_to_data(
            img_cinza, lang="por", output_type=Output.DICT, config="--psm 6"
        )
        with open(arquivo_cache, "w", encoding="utf-8") as f:
            json.dump(dados_ocr, f, ensure_ascii=False)

    texto_completo = " ".join(t for t in dados_ocr.get("text", []) if t.strip())
    return dados_ocr, texto_completo


def identificar_unidade_prisional(texto_completo: str) -> str:
    """Identifica a Unidade Prisional de PE priorizando campo Nome e com fallback no cabeçalho."""
    m = re.search(
        r"(?:Nome|Destinat[áa]rio|Nomo!|Noma:)\s*:?\s*([^;,\n]+?)(?:LF|IF|LE|EF|ISENTO|CNPJ|FONE|CEP|UF|Endere[çc]o|$)",
        texto_completo,
        re.IGNORECASE,
    )
    nome_campo = m.group(1).upper() if m else ""

    if nome_campo:
        for sigla, canonico, aliases in UNIDADES_CANONICAS:
            for a in aliases:
                if a in nome_campo:
                    return canonico

    cabecalho = re.split(r"(?:Observa[çc][ãa]o|LACRES)", texto_completo, flags=re.IGNORECASE)[0].upper()
    for sigla, canonico, aliases in UNIDADES_CANONICAS:
        for a in aliases:
            if a in cabecalho:
                return canonico

    alvo = texto_completo[:1200].upper()
    for sigla, canonico, aliases in UNIDADES_CANONICAS:
        for a in aliases:
            if a in alvo:
                return canonico

    return "NÃO IDENTIFICADO"


def extrair_data_robusta(texto_completo: str, nome_arquivo: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai a data de emissão/entrega e o mês de competência com tratamento de ruídos."""
    m = re.search(r"\bData\s*:?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto_completo, re.IGNORECASE)
    if not m:
        m = re.search(r"\bData/?Hora\s*:?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto_completo, re.IGNORECASE)
    if not m:
        m = re.search(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](202[56])\b", texto_completo)

    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        if dia == 37 and mes == 2:
            dia = 27
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{dia:02d}/{mes:02d}/{ano}", f"{mes:02d}"

    return None, None


def normalizar_produto_nao_perecivel(texto_linha: str) -> Optional[str]:
    """Mapeia os códigos CEASA e descrições do OCR para a ontologia de não perecíveis."""
    t = texto_linha.upper()

    # 1. Busca por código CEASA explícito
    for padrao_cod, nome_canonico, _ in CATALOGO_NAO_PERECIVEIS:
        if re.search(padrao_cod, t):
            return nome_canonico

    # 2. Busca por termos semânticos
    for _, nome_canonico, aliases in CATALOGO_NAO_PERECIVEIS:
        for a in aliases:
            if re.search(r"\b" + re.escape(a) + r"\b", t):
                return nome_canonico

    return None


def extrair_produtos_ocr_nao_perecivel(dados_ocr: Dict[str, Any]) -> List[str]:
    """Reconstitui linhas tabulares do OCR e extrai os alimentos não perecíveis."""
    linhas: Dict[int, List[Tuple[int, str]]] = {}
    total = len(dados_ocr.get("text", []))

    for i in range(total):
        t = dados_ocr["text"][i].strip()
        if not t:
            continue
        y = dados_ocr["top"][i]
        matched = False
        for yk in linhas:
            if abs(yk - y) < TOLERANCIA_LINHA_OCR:
                linhas[yk].append((dados_ocr["left"][i], t))
                matched = True
                break
        if not matched:
            linhas[y] = [(dados_ocr["left"][i], t)]

    produtos = []
    for yk in sorted(linhas.keys()):
        linha = " ".join(t[1] for t in sorted(linhas[yk], key=lambda x: x[0]))
        linha_upper = linha.upper()

        # Descartar cabeçalhos, totais e assinaturas
        if any(ignore in linha_upper for ignore in ["TOTAIS", "TOTAL", "ASSINATURA", "NUTRIC", "ESTOQUIST", "MOTORISTA"]):
            continue

        # Checar se é uma linha de item do CEASA ou contém alimentos estocáveis
        if re.search(r"\bCEASA\d+", linha) or any(k in linha_upper for k in ["ARROZ", "FEIJAO", "ACUCAR", "OLEO", "CAFE", "MACARRAO", "LEITE", "FARINHA", "FUBA", "SAL", "VINAGRE", "MUNGUNZA", "COLORAU", "COMINHO", "AVEIA", "FERMENTO"]):
            prod = normalizar_produto_nao_perecivel(linha)
            if prod and prod not in produtos:
                produtos.append(prod)

    return produtos


def salvar_excel_seguro(df: pd.DataFrame, caminho_destino: Path):
    caminho_destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(caminho_destino, index=False)
        ajustar_larguras_excel(caminho_destino)
        print(f"✅ Planilha gerada com sucesso: {caminho_destino.name} ({len(df)} registros)")
    except PermissionError:
        backup_nome = caminho_destino.with_name(f"{caminho_destino.stem}_novo.xlsx")
        df.to_excel(backup_nome, index=False)
        ajustar_larguras_excel(backup_nome)
        print(f"⚠️ Arquivo aberto no Excel. Salvo como: {backup_nome.name} ({len(df)} registros)")


def processar_lote_nao_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            textos_doc = []
            data_final, mes_final, lugar_final = None, None, "NÃO IDENTIFICADO"

            for num_pag, pagina in enumerate(doc, start=1):
                dados_ocr, texto_completo = processar_pagina_ocr_completo(pagina, pdf_hash, num_pag)
                textos_doc.append(texto_completo)
                textos_doc.append(pagina.get_text())

                if num_pag == 1 or data_final is None:
                    d, m = extrair_data_robusta(texto_completo, nome_arquivo)
                    if d:
                        data_final, mes_final = d, m

                if num_pag == 1 or lugar_final == "NÃO IDENTIFICADO":
                    lug = identificar_unidade_prisional(texto_completo)
                    if lug != "NÃO IDENTIFICADO":
                        lugar_final = lug

            doc.close()

            texto_total = " ".join(textos_doc)
            reposicao = detectar_reposicao(texto_total)

            print(
                f"[{idx:03d}/{len(arquivos):03d}] {nome_arquivo} (guia {pagina_continua_global}): "
                f"Data: {data_final or 'N/A'} | Local: {lugar_final[:35]} | Reposição: {reposicao}"
            )

            registros.append({
                "pasta_origem": nome_lote,
                "arquivo": nome_arquivo,
                "pagina": pagina_continua_global,
                "lugar": lugar_final,
                "data": data_final,
                "mes": mes_final,
                "reposicao": reposicao,
            })

            pagina_continua_global += 1

        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        colunas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
        df = df[colunas]
    return df


def executar_pipeline_nao_pereciveis():
    if not DIR_NAO_PERECIVEL.exists():
        print(f"Diretório não encontrado: {DIR_NAO_PERECIVEL}")
        return

    DIR_SAIDA_NAO_PERECIVEL.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in DIR_NAO_PERECIVEL.iterdir() if p.is_dir()])

    print(f"\n🚀 Iniciando extração de alimentos NÃO PERECÍVEIS em {len(subpastas)} pastas...\n")

    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO NÃO PERECÍVEIS: {nome_subpasta}")
        print("=" * 70)

        arquivos = sorted(list(subpasta.glob("*.pdf")), key=lambda p: obter_chave_ordenacao(p.name))
        if not arquivos:
            continue

        df_lote = processar_lote_nao_perecivel(arquivos, nome_subpasta)

        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_lote = DIR_SAIDA_NAO_PERECIVEL / f"saida_nao_perecivel_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL DE NÃO PERECÍVEIS")
        print("=" * 70)
        caminho_consolidado = DIR_SAIDA_NAO_PERECIVEL / "saida_consolidada_nao_perecivel_total.xlsx"
        salvar_excel_seguro(df_total, caminho_consolidado)
        print(f"\n🎉 Extração de Não Perecíveis 100% concluída em: {DIR_SAIDA_NAO_PERECIVEL.name}/\n")


if __name__ == "__main__":
    executar_pipeline_nao_pereciveis()
