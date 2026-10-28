"""
Extração geométrica de itens alimentícios com correspondência fuzzy.
"""

import re
from typing import Any, Dict, List

from config.settings import (
    HEADER_KEYWORDS,
    PRODUTOS_ESPERADOS,
    PRODUTOS_SEM_KG,
    TOLERANCIA_LINHA_PDF,
    VARIACOES_KG,
)
from utils.text_cleaner import encontrar_produto_fuzzy, separar_produtos_colados


def extrair_produtos_da_pagina(pagina: Any) -> List[str]:
    """Extrai os alimentos da tabela com controle geométrico de cabeçalho e totais."""
    palavras_raw = pagina.get_text("words")
    if not palavras_raw:
        return []

    # Ignorar folhas de checklist
    texto_geral = " ".join(w[4] for w in palavras_raw)
    if "CHECKLIST" in texto_geral.upper():
        return []

    # Agrupar em linhas horizontais
    linhas: Dict[float, List[Dict[str, Any]]] = {}
    for w in palavras_raw:
        item = {"texto": w[4], "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3]}
        y = w[1]
        matched = False
        for yk in linhas:
            if abs(yk - y) < TOLERANCIA_LINHA_PDF:
                linhas[yk].append(item)
                matched = True
                break
        if not matched:
            linhas[y] = [item]

    # Delimitar início e fim da tabela
    y_cabecalho = None
    for y, palavras_linha in linhas.items():
        textos = [p["texto"].upper().strip(".,;:") for p in palavras_linha]
        score = sum(1 for t in textos if any(k in t for k in HEADER_KEYWORDS))
        if score >= 2:
            y_cabecalho = y
            break

    y_fim = float("inf")
    if y_cabecalho is not None:
        for y, palavras_linha in linhas.items():
            if y > y_cabecalho:
                txt = " ".join(p["texto"] for p in palavras_linha)
                if "Totais" in txt or "Observação" in txt or "Observacao" in txt:
                    y_fim = y
                    break

    produtos_encontrados = []
    for y, palavras_linha in sorted(linhas.keys()):
        if y_cabecalho is not None and (y <= y_cabecalho or y > y_fim):
            continue

        ordenadas = sorted(palavras_linha, key=lambda p: p["x0"])
        texto_linha = " ".join(p["texto"] for p in ordenadas)

        if any(h in texto_linha for h in ["Descrição", "U.M.", "Código", "CÓDIGO", "QTD"]):
            continue

        idx_kg = -1
        for i, p in enumerate(ordenadas):
            if p["texto"].upper().strip(".,;:") in VARIACOES_KG:
                idx_kg = i
                break

        if idx_kg != -1:
            candidato = " ".join(p["texto"] for p in ordenadas[: idx_kg + 1])
            prod = encontrar_produto_fuzzy(candidato, PRODUTOS_ESPERADOS)
            if prod:
                for item_final in separar_produtos_colados(f"{prod} KG", PRODUTOS_ESPERADOS):
                    if item_final not in produtos_encontrados:
                        produtos_encontrados.append(item_final)
            continue

        for sem_kg in PRODUTOS_SEM_KG:
            if re.search(r"\b" + re.escape(sem_kg) + r"\b", texto_linha.upper()):
                nome_padrao = "OVOS" if sem_kg in ("OVOS", "OVO") else sem_kg
                if nome_padrao not in produtos_encontrados:
                    produtos_encontrados.append(nome_padrao)
                break

    return produtos_encontrados
