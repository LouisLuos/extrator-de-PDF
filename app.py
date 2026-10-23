"""
Servidor Web Local do Extrator de Guias Prisionais (SERES-PE / CEASA).
Permite que usuários leigos processem lotes de PDFs via navegador com 1 clique.
"""

import hashlib
import os
import re
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# Adicionar pasta src ao sys.path
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Configurar encoding UTF-8 no Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from concurrent.futures import ThreadPoolExecutor
import json
import cv2
import numpy as np
import pytesseract

from flask import Flask, jsonify, render_template, request, send_from_directory
import pandas as pd
import pymupdf

from config.settings import TESSERACT_EXE
if TESSERACT_EXE:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

from extractors.header_extractor import processar_cabecalho_ocr
from extrator_perecivel import (
    extrair_data_robusta,
    identificar_unidade_prisional,
)
from utils.excel_exporter import ajustar_larguras_excel
from utils.text_cleaner import detectar_reposicao

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

DIR_WEB_OUTPUT = BASE_DIR / "planilhas_saida" / "web"
DIR_WEB_OUTPUT.mkdir(parents=True, exist_ok=True)
DIR_CACHE_PERECIVEL = BASE_DIR / "cache_ocr_perecivel"
DIR_CACHE_PERECIVEL.mkdir(parents=True, exist_ok=True)


def extrair_texto_pagina_acelerado(args):
    """
    Processa uma página de forma ultrarrápida:
    1. Verifica caches em disco (0ms).
    2. Usa texto vetorial se existir (0ms).
    3. Executa OCR apenas nas regiões essenciais (Cabeçalho 45% + Rodapé 30%), acelerando em 3x a 4x.
    """
    pdf_bytes, num_pag, pdf_hash = args
    cache_file = DIR_CACHE_PERECIVEL / f"{pdf_hash}_p{num_pag:04d}_fast.json"

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return num_pag, json.load(f)["texto"]
        except Exception:
            pass

    # Checa caches legados completos se existirem
    for dir_c in [DIR_CACHE_PERECIVEL, BASE_DIR / "cache_ocr_nao_perecivel", BASE_DIR / "cache_ocr"]:
        full_cache = dir_c / f"{pdf_hash}_p{num_pag:04d}_full.json"
        if full_cache.exists():
            try:
                with open(full_cache, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    txt = " ".join(t for t in d.get("text", []) if t.strip())
                    return num_pag, txt
            except Exception:
                pass
        h_cache = dir_c / f"{pdf_hash}_p{num_pag:04d}_header.json"
        if h_cache.exists():
            try:
                with open(h_cache, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    txt = " ".join(t for t in d.get("text", []) if t.strip())
                    return num_pag, txt
            except Exception:
                pass

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[num_pag - 1]

    # 1. Camada vetorial nativa (sem necessidade de OCR)
    txt_vetor = page.get_text()
    if len(txt_vetor.strip()) > 80:
        doc.close()
        return num_pag, txt_vetor

    # 2. OCR inteligente em ROI (Cabeçalho 45% + Rodapé 30%)
    try:
        pix = page.get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        h, w = img_gray.shape

        crop_h = img_gray[0:int(h * 0.45), 0:w]
        crop_f = img_gray[int(h * 0.70):h, 0:w]

        txt_h = pytesseract.image_to_string(crop_h, lang="por", config="--psm 6")
        txt_f = pytesseract.image_to_string(crop_f, lang="por", config="--psm 6")
        txt_total = f"{txt_h} {txt_f}"
    except Exception as e:
        txt_total = txt_vetor

    doc.close()

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"texto": txt_total}, f, ensure_ascii=False)
    except Exception:
        pass

    return num_pag, txt_total


def classificar_categoria_pdf(texto_amostra: str) -> str:
    """Classifica automaticamente o PDF caso o usuário selecione 'Identificação Automática'."""
    txt = texto_amostra.upper()
    if "HORTIFRUTI" in txt or "HORTI" in txt:
        return "hortifrute"
    if "NÃO PEREC" in txt or "NAO PEREC" in txt:
        return "nao_perecivel"
    if "PEREC" in txt or "CARNE" in txt or "LINGUICA" in txt or "SOBRECOXA" in txt:
        return "perecivel"
    if "ARROZ" in txt or "FEIJAO" in txt or "FARINHA" in txt or "OLEO" in txt:
        return "nao_perecivel"
    return "hortifrute"


@app.after_request
def adicionar_cors_headers(response):
    """Garante suporte nativo a CORS para permitir conexões de Live Server, file:/// ou qualquer porta local."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/processar", methods=["POST", "OPTIONS"])
def processar_arquivos():
    if request.method == "OPTIONS":
        return "", 200

    if "files" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arquivos = request.files.getlist("files")
    categoria_solicitada = request.form.get("categoria", "auto")

    if not arquivos:
        return jsonify({"erro": "Lista de arquivos vazia."}), 400

    registros = []
    pagina_continua_global = 1
    max_threads = min(4, os.cpu_count() or 4)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for idx, file_obj in enumerate(arquivos, start=1):
            if not file_obj.filename.lower().endswith(".pdf"):
                continue

            caminho_salvo = temp_path / file_obj.filename
            file_obj.save(caminho_salvo)

            try:
                doc = pymupdf.open(caminho_salvo)
                pdf_bytes = caminho_salvo.read_bytes()
                pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:10]
                total_pags = len(doc)
                doc.close()

                # Processamento paralelo de páginas
                tarefas = [(pdf_bytes, i, pdf_hash) for i in range(1, total_pags + 1)]
                with ThreadPoolExecutor(max_workers=max_threads) as executor:
                    paginas_processadas = list(executor.map(extrair_texto_pagina_acelerado, tarefas))

                paginas_processadas.sort(key=lambda x: x[0])

                # Segmentação inteligente de guias dentro do PDF (trata PDFs de 1 ou múltiplas guias)
                guias = []
                guia_atual = None

                for num_pag, texto_pag in paginas_processadas:
                    m_num = re.search(r"N[úu]mero\s*:?\s*(\d{4,6})", texto_pag, re.IGNORECASE)
                    num_encontrado = m_num.group(1) if m_num else None

                    is_nova_guia = False
                    if num_encontrado:
                        if guia_atual is None or (guia_atual.get("numero") and guia_atual["numero"] != num_encontrado):
                            is_nova_guia = True
                    elif guia_atual is None:
                        is_nova_guia = True

                    if is_nova_guia:
                        if guia_atual:
                            guias.append(guia_atual)
                        guia_atual = {
                            "numero": num_encontrado,
                            "paginas": [num_pag],
                            "textos": [texto_pag]
                        }
                    else:
                        if guia_atual:
                            guia_atual["paginas"].append(num_pag)
                            guia_atual["textos"].append(texto_pag)

                if guia_atual:
                    guias.append(guia_atual)

                tem_multi_guias = len(guias) > 1

                for g in guias:
                    texto_guia = " ".join(g["textos"])
                    lugar_final = identificar_unidade_prisional(texto_guia)
                    num_str = g["numero"] or ""
                    data_final, mes_final = extrair_data_robusta(
                        texto_guia, f"{num_str}.pdf" if num_str else file_obj.filename
                    )
                    reposicao = detectar_reposicao(texto_guia)

                    nome_arquivo_formatado = (
                        f"{file_obj.filename} [Guia {num_str}]"
                        if tem_multi_guias and num_str
                        else file_obj.filename
                    )

                    registros.append({
                        "arquivo": nome_arquivo_formatado,
                        "pagina": pagina_continua_global,
                        "lugar": lugar_final,
                        "data": data_final or "N/A",
                        "mes": mes_final or "N/A",
                        "reposicao": reposicao,
                    })

                    pagina_continua_global += 1

            except Exception as e:
                print(f"Erro ao processar {file_obj.filename}: {e}")


    if not registros:
        return jsonify({"erro": "Nenhuma guia pôde ser processada."}), 400

    df = pd.DataFrame(registros)
    colunas = ["arquivo", "pagina", "lugar", "data", "mes", "reposicao"]
    df = df[colunas]

    # Salvar em Excel formatado
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_excel = f"guias_consolidadas_{timestamp}.xlsx"
    caminho_excel = DIR_WEB_OUTPUT / nome_arquivo_excel

    df.to_excel(caminho_excel, index=False)
    ajustar_larguras_excel(caminho_excel)

    total_guias = len(df)
    total_reposicoes = (df["reposicao"] == "SIM").sum()
    total_regulares = total_guias - total_reposicoes

    return jsonify({
        "total_guias": int(total_guias),
        "total_regulares": int(total_regulares),
        "total_reposicoes": int(total_reposicoes),
        "arquivo_excel": nome_arquivo_excel,
        "registros": df.to_dict(orient="records"),
    })


@app.route("/api/download/<filename>", methods=["GET", "OPTIONS"])
def download_excel(filename):
    if request.method == "OPTIONS":
        return "", 200
    return send_from_directory(DIR_WEB_OUTPUT, filename, as_attachment=True)


def abrir_navegador():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 SERVIDOR WEB DO EXTRATOR DE GUIAS PRISIONAIS INICIADO")
    print("📍 Acesse no navegador: http://127.0.0.1:5000")
    print("=" * 70 + "\n")
    threading.Thread(target=abrir_navegador, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
