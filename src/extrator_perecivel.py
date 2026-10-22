"""
Pipeline especializado para extração de alimentos PERECÍVEIS (Carnes, Frios, Proteínas e Pescados).

Documentos digitalizados (sem camada vetorial nativa):
- Realiza OCR de página inteira a 300 DPI com cache JSON em cache_ocr_perecivel/
- Extrai metadados do cabeçalho (Data, Mês e Unidade Prisional) com normalização canônica
- Extrai itens da tabela de carnes/embutidos via mapeamento de códigos CEASA e ontologia oficial
- Salva os resultados individuais por mês e consolidados em planilhas_saida/ceasa/perecivel/
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

if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

DIR_PERECIVEL = BASE_DIR / "PDFs" / "perecivel"
DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_SAIDA_PERECIVEL = DIR_PLANILHAS / "ceasa" / "perecivel"

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
    ("COTEL", "COTEL - CENTRO DE OBSERVAÇÃO E TRIAGEM", ["COTEL", "EVERARDO LUNA", "OBSERVAÇÃO E TRIAGEM", "OBSERVACAO E TRIAGEM", "CENTRO DE OBSERVACAO"]),
    ("PFAL", "PFAL - COLÔNIA PENAL FEMININA DE ABREU E LIMA", ["PFAL", "ABREU E LIMA", "FEMININA DE ABREU"]),
    ("PAISJ", "PAISJ - PENITENCIÁRIA AGROINDUSTRIAL SÃO JOÃO", ["PAISJ", "PAIS", "AGROINDUSTRIAL", "AGRO INDUSTRIAL", "AGRO-"]),
    ("PI", "PI - PRESÍDIO DE IGARASSU", ["IGARASSU", "IGARASU", " PI "]),
]


def obter_chave_ordenacao(nome: str):
    stem = os.path.splitext(nome)[0]
    digitos = re.findall(r"\d+", stem)
    return int(digitos[0]) if digitos else stem


def processar_pagina_ocr_completo(pagina: pymupdf.Page, pdf_hash: str, num_pag: int) -> Tuple[Dict[str, Any], str]:
    """Executa OCR na página inteira e gerencia cache JSON local."""
    DIR_CACHE_PERECIVEL.mkdir(parents=True, exist_ok=True)
    arquivo_cache = DIR_CACHE_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_full.json"

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
    """
    Identifica de forma canônica a Unidade Prisional de Pernambuco.
    Prioriza o campo 'Nome:' e faz fallback no cabeçalho antes de observações.
    """
    m = re.search(
        r"(?:Nome|Destinat[áa]rio|Nomo!|Noma:)\s*:?\s*([^;,\n]+?)(?:LF|IF|LE|EF|ISENTO|CNPJ|FONE|CEP|UF|Endere[çc]o|$)",
        texto_completo,
        re.IGNORECASE,
    )
    nome_campo = m.group(1).upper() if m else ""

    # 1. Tentar casar prioritariamente no campo Nome:
    if nome_campo:
        for sigla, canonico, aliases in UNIDADES_CANONICAS:
            for a in aliases:
                if a in nome_campo:
                    return canonico

    # 2. Fallback no cabeçalho antes de Observação / LACRES
    cabecalho = re.split(r"(?:Observa[çc][ãa]o|LACRES)", texto_completo, flags=re.IGNORECASE)[0].upper()
    for sigla, canonico, aliases in UNIDADES_CANONICAS:
        for a in aliases:
            if a in cabecalho:
                return canonico

    # 3. Fallback no texto completo até 1200 caracteres
    alvo = texto_completo[:1200].upper()
    for sigla, canonico, aliases in UNIDADES_CANONICAS:
        for a in aliases:
            if a in alvo:
                return canonico

    return "NÃO IDENTIFICADO"


def extrair_data_robusta(texto_completo: str, nome_arquivo: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai a data da guia com tratamento de ruídos e fallbacks determinísticos."""
    # 1. Procura 'Data: DD/MM/AAAA' ou variações de cabeçalho
    m = re.search(r"\bData\s*:?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto_completo, re.IGNORECASE)
    if not m:
        m = re.search(r"\bData/?Hora\s*:?\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", texto_completo, re.IGNORECASE)
    if not m:
        # Fallback para qualquer data válida nos anos 2025/2026
        m = re.search(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](202[56])\b", texto_completo)

    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        # Correção pontual de ruído OCR (dia 37 em fevereiro -> 27)
        if dia == 37 and mes == 2:
            dia = 27
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            return f"{dia:02d}/{mes:02d}/{ano}", f"{mes:02d}"

    # Arquivos de 30/01/2026 com cabeçalho muito degradado
    if "12850" in nome_arquivo or "12851" in nome_arquivo:
        return "30/01/2026", "01"

    return None, None


def normalizar_produto_perecivel(texto_linha: str) -> Optional[str]:
    """
    Mapeia os códigos de contrato CEASA e termos do OCR para a ontologia oficial de perecíveis.
    """
    t = texto_linha.upper()

    if re.search(r"CEASA115", t) or "PEIXE" in t:
        return "FILE DE PEIXE KG"
    if re.search(r"CEASA36", t) or any(k in t for k in ["SALGADA", "CURADA", "DESSECADA", "DEBBECADA"]):
        return "CARNE BOVINA SALGADA CURADA DESSECADA KG"
    if re.search(r"CEASA37", t) or any(k in t for k in ["COXA", "SOBRECOXA", "AVE CONGELADA", "FRANGO"]):
        return "CARNE DE AVE CONGELADA COXA E SOBRECOXA KG"
    if re.search(r"CEASA38", t) or any(k in t for k in ["MUSCULO", "MÚSCULO", "MUSCUI", "SEGUND"]):
        return "CARNE BOVINA DE SEGUNDA - MUSCULO KG"
    if re.search(r"CEASA39", t) or any(k in t for k in ["CHARQUE", "ROJAO", "ROJÃO"]):
        return "CARNE DE CHARQUE DO TIPO ROJAO KG"
    if re.search(r"CEASA42", t) or any(k in t for k in ["CALABRESA", "TALABRESA"]):
        return "LINGUICA CALABRESA KG"
    if re.search(r"CEASA43", t) or any(k in t for k in ["SALSICHA", "HOT DOG", "HOTDOG"]):
        return "SALSICHA HOT DOG KG"
    if re.search(r"CEASA44", t) or any(k in t for k in ["LOMBO", "SUINO", "SÚINO"]):
        return "CARNE CONGELADA DE SUINO SEM OSSO - LOMBO KG"
    if re.search(r"CEASA45", t) or any(k in t for k in ["FIGADO", "FÍGADO", "MUIDO", "MÍUDO", "FIGSADO"]):
        return "MUIDO CONGELADO DE BOVINO - FIGADO KG"
    if "LINGUICA" in t:
        return "LINGUICA CALABRESA KG"

    return None


def extrair_produtos_ocr_perecivel(dados_ocr: Dict[str, Any]) -> List[str]:
    """Reconstitui linhas tabulares do OCR e normaliza nomes de carnes/embutidos."""
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

        # Ignorar linhas de totais, assinaturas e carimbos
        if any(ignore in linha.upper() for ignore in ["TOTAIS", "ASSINATURA", "NUTRIC", "ESTOQUIST"]):
            continue

        if re.search(r"\bCEASA\d+", linha) or any(k in linha.upper() for k in ["CARNE", "LINGUICA", "SALSICHA", "MUIDO", "FIGADO", "PEIXE"]):
            prod_padronizado = normalizar_produto_perecivel(linha)
            if prod_padronizado and prod_padronizado not in produtos:
                produtos.append(prod_padronizado)

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


def processar_lote_perecivel(arquivos: List[Path], nome_lote: str) -> pd.DataFrame:
    registros = []
    pagina_continua_global = 1

    for idx, caminho_pdf in enumerate(arquivos, start=1):
        nome_arquivo = caminho_pdf.name
        try:
            doc = pymupdf.open(caminho_pdf)
            pdf_hash = hashlib.md5(caminho_pdf.read_bytes()).hexdigest()[:10]

            for num_pag, pagina in enumerate(doc, start=1):
                dados_ocr, texto_completo = processar_pagina_ocr_completo(pagina, pdf_hash, num_pag)
                data, mes = extrair_data_robusta(texto_completo, nome_arquivo)
                lugar = identificar_unidade_prisional(texto_completo)
                produtos = extrair_produtos_ocr_perecivel(dados_ocr)

                print(
                    f"[{idx:03d}/{len(arquivos):03d}] {nome_arquivo} (pág {pagina_continua_global}): "
                    f"{len(produtos):2d} carnes/frios | Data: {data or 'N/A'} | Local: {lugar[:35]}"
                )

                for prod in produtos:
                    registros.append({
                        "pasta_origem": nome_lote,
                        "arquivo": nome_arquivo,
                        "pagina": pagina_continua_global,
                        "lugar": lugar,
                        "produto": prod,
                        "data": data,
                        "mes": mes,
                    })

                pagina_continua_global += 1

            doc.close()
        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")

    df = pd.DataFrame(registros)
    if not df.empty:
        colunas = ["arquivo", "pagina", "lugar", "produto", "data", "mes"]
        df = df[colunas]
    return df


def executar_pipeline_pereciveis():
    if not DIR_PERECIVEL.exists():
        print(f"Diretório não encontrado: {DIR_PERECIVEL}")
        return

    DIR_SAIDA_PERECIVEL.mkdir(parents=True, exist_ok=True)
    subpastas = sorted([p for p in DIR_PERECIVEL.iterdir() if p.is_dir()])

    print(f"\n🚀 Iniciando extração de alimentos PERECÍVEIS em {len(subpastas)} pastas...\n")

    todos_dfs = []

    for subpasta in subpastas:
        nome_subpasta = subpasta.name
        print("=" * 70)
        print(f"📂 PROCESSANDO PERECÍVEIS: {nome_subpasta}")
        print("=" * 70)

        arquivos = sorted(list(subpasta.glob("*.pdf")), key=lambda p: obter_chave_ordenacao(p.name))
        if not arquivos:
            continue

        df_lote = processar_lote_perecivel(arquivos, nome_subpasta)

        if not df_lote.empty:
            nome_limpo = re.sub(r'[\\/*?:"<>|.]', "_", nome_subpasta).replace(" ", "_")
            caminho_lote = DIR_SAIDA_PERECIVEL / f"saida_perecivel_{nome_limpo}.xlsx"
            salvar_excel_seguro(df_lote, caminho_lote)
            todos_dfs.append(df_lote)

    if todos_dfs:
        df_total = pd.concat(todos_dfs, ignore_index=True)
        print("\n" + "=" * 70)
        print("📊 GERANDO PLANILHA CONSOLIDADA GERAL DE PERECÍVEIS")
        print("=" * 70)
        caminho_consolidado = DIR_SAIDA_PERECIVEL / "saida_consolidada_perecivel_total.xlsx"
        salvar_excel_seguro(df_total, caminho_consolidado)
        print(f"\n🎉 Extração de Perecíveis 100% concluída em: {DIR_SAIDA_PERECIVEL.name}/\n")


if __name__ == "__main__":
    executar_pipeline_pereciveis()
