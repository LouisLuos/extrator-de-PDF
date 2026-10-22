"""
Funções utilitárias de limpeza, normalização e correspondência fuzzy.
"""

import re
from difflib import SequenceMatcher
from typing import List, Optional


def limpar_nome_lugar(nome_bruto: str) -> str:
    """
    Higieniza o nome da unidade prisional extraída pelo OCR.
    Remove siglas coladas, códigos fiscais, CNPJs e sequências numéricas.
    """
    if not nome_bruto or nome_bruto == "NÃO IDENTIFICADO":
        return "NÃO IDENTIFICADO"

    texto = nome_bruto.strip()

    # Se for apenas números e pontuação (ex: '06290858000548')
    if re.fullmatch(r"[\d\s\.\-\/]+", texto):
        return "NÃO IDENTIFICADO"

    # 1. Cortar rótulos fiscais com ou sem espaço (ex: SANTOLF: 0629... -> SANTO)
    texto = re.sub(
        r"(?:[\s\|\-]+(?:I\.?F\.?|L\.?F\.?|E\.?F\.?|L\.?E\.?|1\.?F\.?|\.F|E\.?E\.?|E\.?R\.?|I\.?L\.?F\.?|RS|ER|CNPJ|FONE|CEP|UF|IE|ENDERE[CÇ]O)|LF|IF|LE|EF)[:\.]?\s*\d+.*$",
        "",
        texto,
        flags=re.IGNORECASE,
    )

    # 2. Cortar sequências numéricas longas (6 ou mais dígitos, como CNPJ/Inscrição)
    texto = re.sub(r"[\s\|\-]+(?:[A-Z0-9]{1,4}[\.:])?\s*\d{6,}.*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b\d{6,}\b.*$", "", texto)

    # 3. Remover quaisquer dígitos numéricos soltos restantes
    texto = re.sub(r"\b\d+\b", "", texto)

    # 4. Limpeza de pipes, traços e espaços duplicados
    texto = re.sub(r"[\s\|\-]+$", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    resultado = texto.strip(" -:|.,")
    return resultado if resultado else "NÃO IDENTIFICADO"


def encontrar_produto_fuzzy(
    texto: str, produtos: List[str], threshold: float = 0.75, min_word_score: float = 0.70
) -> Optional[str]:
    """
    Identifica se a linha contém algum dos produtos esperados utilizando
    correspondência aproximada (Fuzzy Matching).
    """
    if not texto:
        return None

    limpo = re.sub(r"[^A-ZÀ-Ý\s]", " ", texto.upper())
    tokens = [t for t in limpo.split() if t]
    if not tokens:
        return None

    junto = " ".join(tokens)
    melhor_prod, melhor_score = None, 0.0

    for prod in produtos:
        if prod in junto:
            return prod

        scores = []
        for palavra_prod in prod.split():
            melhor_local = max(
                (SequenceMatcher(None, palavra_prod, t).ratio() for t in tokens),
                default=0.0
            )
            scores.append(melhor_local)

        if min(scores) < min_word_score:
            continue

        score_medio = sum(scores) / len(scores)
        if score_medio > melhor_score:
            melhor_score = score_medio
            melhor_prod = prod

    return melhor_prod if melhor_score >= threshold else None


def separar_produtos_colados(produto: str, produtos_base: List[str]) -> List[str]:
    """Trata casos em que dois produtos foram concatenados pelo leitor."""
    nome = produto.upper().replace(" KG", "").strip()
    for prod in produtos_base:
        if nome.startswith(prod) and nome != prod:
            resto = nome[len(prod):].strip()
            if resto in produtos_base:
                return [f"{prod} KG", f"{resto} KG"]
    return [produto]
