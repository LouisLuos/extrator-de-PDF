import pytest
from app import app, classificar_categoria_pdf


def test_flask_index_route():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Extrator Inteligente de Guias Prisionais" in html
    assert "/static/css/style.css" in html
    assert "/static/js/app.js" in html


def test_flask_static_assets_css_and_js():
    """Garante que a separação em 3 arquivos (HTML, CSS e JS) é servida corretamente pelo Flask."""
    client = app.test_client()
    res_css = client.get("/static/css/style.css")
    assert res_css.status_code == 200
    assert "--bg-primary" in res_css.get_data(as_text=True)

    res_js = client.get("/static/js/app.js")
    assert res_js.status_code == 200
    assert "iniciarProcessamento" in res_js.get_data(as_text=True)


def test_classificar_categoria():
    assert classificar_categoria_pdf("Guia de Entrega de Hortifrúti e Legumes") == "hortifrute"
    assert classificar_categoria_pdf("Carne bovina com osso e frango congelado") == "perecivel"
    assert classificar_categoria_pdf("Arroz parboilizado e feijão carioquinha") == "nao_perecivel"


def test_cors_preflight_and_headers():
    client = app.test_client()
    # 1. Preflight OPTIONS na rota /api/processar
    res_options = client.options("/api/processar", headers={
        "Origin": "http://127.0.0.1:5500",
        "Access-Control-Request-Method": "POST"
    })
    assert res_options.status_code == 200
    assert res_options.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in res_options.headers.get("Access-Control-Allow-Methods")

    # 2. Resposta normal GET contendo cabeçalho CORS
    res_get = client.get("/")
    assert res_get.headers.get("Access-Control-Allow-Origin") == "*"


def test_multi_guia_segmentation():
    """Valida que um PDF contendo múltiplas guias é desmembrado nas respectivas linhas."""
    import pymupdf, io
    from pathlib import Path

    doc_combined = pymupdf.open()
    base_dir = Path("PDFs/nao-perecivel/01. GUIAS DE ENTREGA N PEREC - JAN 2026")
    doc_combined.insert_pdf(pymupdf.open(base_dir / "12543.pdf"))
    doc_combined.insert_pdf(pymupdf.open(base_dir / "12544.pdf"))

    pdf_bytes = doc_combined.tobytes()
    client = app.test_client()

    data = {
        "files": (io.BytesIO(pdf_bytes), "caderno_composto.pdf"),
        "categoria": "nao_perecivel"
    }

    res = client.post("/api/processar", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["total_guias"] == 2
    presidios = [r["lugar"] for r in json_data["registros"]]
    assert "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO" in presidios
    assert "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO" in presidios
