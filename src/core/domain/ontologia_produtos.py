"""
Camada Core / Domain: Ontologia e Normalização Canônica de Produtos Alimentícios (CEASA / SERES-PE).

Regra de Dependência (Clean Architecture):
- Zero dependências externas (usa apenas biblioteca padrão do Python: `re`, `typing`).
- Contém os catálogos oficiais de contratos do CEASA (Perecíveis e Não Perecíveis),
  normalização semântica contra ruídos de OCR e reconstituição geométrica de linhas.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

TOLERANCIA_LINHA_OCR_PADRAO = 15

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

# Catálogo Oficial de Itens Perecíveis (Carnes, Frios, Proteínas e Pescados)
CATALOGO_PERECIVEIS = [
    (r"CEASA115", "FILE DE PEIXE KG", ["PEIXE"]),
    (r"CEASA36", "CARNE BOVINA SALGADA CURADA DESSECADA KG", ["SALGADA", "CURADA", "DESSECADA", "DEBBECADA"]),
    (r"CEASA37", "CARNE DE AVE CONGELADA COXA E SOBRECOXA KG", ["COXA", "SOBRECOXA", "AVE CONGELADA", "FRANGO"]),
    (r"CEASA38", "CARNE BOVINA DE SEGUNDA - MUSCULO KG", ["MUSCULO", "MÚSCULO", "MUSCUI", "SEGUND"]),
    (r"CEASA39", "CARNE DE CHARQUE DO TIPO ROJAO KG", ["CHARQUE", "ROJAO", "ROJÃO"]),
    (r"CEASA42", "LINGUICA CALABRESA KG", ["CALABRESA", "TALABRESA"]),
    (r"CEASA43", "SALSICHA HOT DOG KG", ["SALSICHA", "HOT DOG", "HOTDOG"]),
    (r"CEASA44", "CARNE CONGELADA DE SUINO SEM OSSO - LOMBO KG", ["LOMBO", "SUINO", "SÚINO"]),
    (r"CEASA45", "MUIDO CONGELADO DE BOVINO - FIGADO KG", ["FIGADO", "FÍGADO", "MUIDO", "MÍUDO", "FIGSADO"]),
]


def normalizar_produto_perecivel(texto_linha: str) -> Optional[str]:
    """Mapeia os códigos de contrato CEASA e termos do OCR para a ontologia oficial de perecíveis."""
    t = texto_linha.upper()

    for padrao_cod, nome_canonico, aliases in CATALOGO_PERECIVEIS:
        if re.search(padrao_cod, t) or any(k in t for k in aliases):
            return nome_canonico

    if "LINGUICA" in t:
        return "LINGUICA CALABRESA KG"

    return None


def normalizar_produto_nao_perecivel(texto_linha: str) -> Optional[str]:
    """Mapeia os códigos CEASA e descrições do OCR para a ontologia oficial de não perecíveis."""
    t = texto_linha.upper()

    # 1. Busca por código CEASA explícito
    for padrao_cod, nome_canonico, _ in CATALOGO_NAO_PERECIVEIS:
        if re.search(padrao_cod, t):
            return nome_canonico

    # 2. Busca por termos semânticos com fronteira de palavra
    for _, nome_canonico, aliases in CATALOGO_NAO_PERECIVEIS:
        for a in aliases:
            if re.search(r"\b" + re.escape(a) + r"\b", t):
                return nome_canonico

    return None


def reconstituir_linhas_ocr(
    dados_ocr: Dict[str, Any], tolerancia: int = TOLERANCIA_LINHA_OCR_PADRAO
) -> List[str]:
    """Agrupa palavras do OCR pela coordenada vertical (top) e ordena horizontalmente (left)."""
    linhas: Dict[int, List[Tuple[int, str]]] = {}
    total = len(dados_ocr.get("text", []))

    for i in range(total):
        t = dados_ocr["text"][i].strip()
        if not t:
            continue
        y = dados_ocr["top"][i]
        matched = False
        for yk in linhas:
            if abs(yk - y) < tolerancia:
                linhas[yk].append((dados_ocr["left"][i], t))
                matched = True
                break
        if not matched:
            linhas[y] = [(dados_ocr["left"][i], t)]

    return [
        " ".join(t[1] for t in sorted(linhas[yk], key=lambda x: x[0]))
        for yk in sorted(linhas.keys())
    ]


def extrair_produtos_ocr_perecivel(
    dados_ocr: Dict[str, Any], tolerancia: int = TOLERANCIA_LINHA_OCR_PADRAO
) -> List[str]:
    """Reconstitui linhas tabulares do OCR e normaliza nomes de carnes/embutidos."""
    produtos: List[str] = []
    palavras_chave = ["CARNE", "LINGUICA", "SALSICHA", "MUIDO", "FIGADO", "PEIXE"]
    ignorar = ["TOTAIS", "ASSINATURA", "NUTRIC", "ESTOQUIST"]

    for linha in reconstituir_linhas_ocr(dados_ocr, tolerancia):
        linha_upper = linha.upper()
        if any(ig in linha_upper for ig in ignorar):
            continue

        if re.search(r"\bCEASA\d+", linha) or any(k in linha_upper for k in palavras_chave):
            prod_padronizado = normalizar_produto_perecivel(linha)
            if prod_padronizado and prod_padronizado not in produtos:
                produtos.append(prod_padronizado)

    return produtos


def extrair_produtos_ocr_nao_perecivel(
    dados_ocr: Dict[str, Any], tolerancia: int = TOLERANCIA_LINHA_OCR_PADRAO
) -> List[str]:
    """Reconstitui linhas tabulares do OCR e extrai os alimentos não perecíveis."""
    produtos: List[str] = []
    palavras_chave = [
        "ARROZ", "FEIJAO", "ACUCAR", "OLEO", "CAFE", "MACARRAO", "LEITE",
        "FARINHA", "FUBA", "SAL", "VINAGRE", "MUNGUNZA", "COLORAU",
        "COMINHO", "AVEIA", "FERMENTO",
    ]
    ignorar = ["TOTAIS", "TOTAL", "ASSINATURA", "NUTRIC", "ESTOQUIST", "MOTORISTA"]

    for linha in reconstituir_linhas_ocr(dados_ocr, tolerancia):
        linha_upper = linha.upper()
        if any(ig in linha_upper for ig in ignorar):
            continue

        if re.search(r"\bCEASA\d+", linha) or any(k in linha_upper for k in palavras_chave):
            prod = normalizar_produto_nao_perecivel(linha)
            if prod and prod not in produtos:
                produtos.append(prod)

    return produtos

