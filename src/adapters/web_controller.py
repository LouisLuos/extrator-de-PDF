"""
Adaptador de Entrada Web (Driving Adapter / Controller) — Flask HTTP.

Responsabilidades EXCLUSIVAS desta camada:
- Receber requisições HTTP do navegador (GET/POST/OPTIONS).
- Servir a View HTML (`templates/index.html`) e os arquivos estáticos (`static/css`, `static/js`).
- Salvar temporariamente os arquivos enviados via formulário multipart.
- Acionar o Caso de Uso (`processar_caminhos_pdf_acelerado`).
- Devolver a resposta HTTP (HTML ou JSON).
"""

import os
from pathlib import Path
import tempfile
import threading
import time
import webbrowser

from flask import Flask, jsonify, render_template, request, send_from_directory

from config.settings import BASE_DIR
from core.use_cases.processar_lote_guias import processar_caminhos_pdf_acelerado

DIR_WEB_OUTPUT = BASE_DIR / "planilhas_saida" / "web"
DIR_WEB_OUTPUT.mkdir(parents=True, exist_ok=True)


def criar_app_web() -> Flask:
    """Cria e configura a instância Flask apontando para `templates/` e `static/` na raiz."""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    @app.after_request
    def adicionar_cors_headers(response):
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
        if not arquivos:
            return jsonify({"erro": "Lista de arquivos vazia."}), 400

        print(f"\n[WEB CONTROLLER] 📥 Recebido lote de {len(arquivos)} arquivo(s)...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            caminhos_salvos = []

            for file_obj in arquivos:
                if not file_obj.filename or not file_obj.filename.lower().endswith(".pdf"):
                    continue
                caminho_salvo = temp_path / file_obj.filename
                file_obj.save(caminho_salvo)
                caminhos_salvos.append(caminho_salvo)

            # Aciona o Caso de Uso na camada de Aplicação
            resultado = processar_caminhos_pdf_acelerado(caminhos_salvos, DIR_WEB_OUTPUT)

        if not resultado:
            return jsonify({"erro": "Nenhuma guia pôde ser processada."}), 400

        return jsonify(resultado)

    @app.route("/api/download/<filename>", methods=["GET", "OPTIONS"])
    def download_excel(filename):
        if request.method == "OPTIONS":
            return "", 200
        return send_from_directory(DIR_WEB_OUTPUT, filename, as_attachment=True)

    @app.route("/api/encerrar", methods=["POST", "OPTIONS"])
    def encerrar():
        if request.method == "OPTIONS":
            return "", 200

        def shutdown():
            time.sleep(0.5)
            print("\n" + "=" * 70)
            print("🛑 SERVIDOR ENCERRADO PELO USUÁRIO")
            print("=" * 70 + "\n")
            os._exit(0)

        threading.Thread(target=shutdown, daemon=True).start()
        return jsonify({"mensagem": "Servidor encerrado com sucesso."})

    return app


def iniciar_servidor_web(app: Flask) -> None:
    """Inicia o servidor local Flask e abre o navegador padrão."""
    def abrir_navegador():
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:5000")

    print("\n" + "=" * 70)
    print("🚀 SERVIDOR WEB DO EXTRATOR DE GUIAS PRISIONAIS INICIADO")
    print("📍 Acesse no navegador: http://127.0.0.1:5000")
    print("=" * 70 + "\n")
    threading.Thread(target=abrir_navegador, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
