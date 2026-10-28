import pytest
from app import app, classificar_categoria_pdf


def test_flask_index_route():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "Extrator Inteligente de Guias Prisionais" in response.get_data(as_text=True)


def test_classificar_categoria():
    assert classificar_categoria_pdf("Guia de Entrega de Hortifrúti e Legumes") == "hortifrute"
    assert classificar_categoria_pdf("Carne bovina com osso e frango congelado") == "perecivel"
    assert classificar_categoria_pdf("Arroz parboilizado e feijão carioquinha") == "nao_perecivel"


def test_cors_preflight_and_headers():
    client = app.test_client()
    # 1. Preflight OPTIONS na rota /api/processar
    res_options = client.options(
        "/api/processar",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_options.status_code == 200
    assert res_options.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in res_options.headers.get("Access-Control-Allow-Methods")

    # 2. Resposta normal GET contendo cabeçalho CORS
    res_get = client.get("/")
    assert res_get.headers.get("Access-Control-Allow-Origin") == "*"


def test_multi_guia_segmentation():
    """Valida que um PDF contendo múltiplas guias é desmembrado nas respectivas linhas."""
    import io
    from pathlib import Path
    import pymupdf

    doc_combined = pymupdf.open()
    base_dir = Path("PDFs/nao-perecivel/01. GUIAS DE ENTREGA N PEREC - JAN 2026")
    arq1 = base_dir / "12543.pdf"
    arq2 = base_dir / "12544.pdf"

    if arq1.exists() and arq2.exists():
        doc_combined.insert_pdf(pymupdf.open(arq1))
        doc_combined.insert_pdf(pymupdf.open(arq2))
    else:
        # Fallback em memória quando a pasta PDFs/ não está presente nesta máquina
        p1 = doc_combined.new_page()
        p1.insert_text(
            (50, 100),
            "GOVERNO DE PERNAMBUCO - CEASA/PE - GUIA DE ENTREGA DE ALIMENTOS\n"
            "Número: 12543   Data: 30/12/2025\n"
            "Nome: PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO   L.F: ISENTO\n"
            "Observação: Guia regular referente à entrega mensal.",
        )
        p2 = doc_combined.new_page()
        p2.insert_text(
            (50, 100),
            "GOVERNO DE PERNAMBUCO - CEASA/PE - GUIA DE ENTREGA DE ALIMENTOS\n"
            "Número: 12544   Data: 30/12/2025\n"
            "Nome: PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO   L.F: ISENTO\n"
            "Observação: Guia regular referente à entrega mensal.",
        )

    pdf_bytes = doc_combined.tobytes()
    client = app.test_client()

    data = {
        "files": (io.BytesIO(pdf_bytes), "caderno_composto.pdf"),
        "categoria": "nao_perecivel",
    }

    res = client.post("/api/processar", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["total_guias"] == 2
    presidios = [r["lugar"] for r in json_data["registros"]]
    assert "PFDB - PRESÍDIO FREI DAMIÃO DE BOZZANO" in presidios
    assert "PPLL - PRESÍDIO PROFESSOR LISBOA CORDEIRO" in presidios


def test_rejeicao_pdf_aleatorio_fora_do_dominio():
    """Garante que enviar um PDF aleatório (ex: livro, currículo, boleto) retorna 400 e não inventa guias."""
    import io
    import pymupdf

    doc_aleatorio = pymupdf.open()
    page = doc_aleatorio.new_page()
    page.insert_text(
        (50, 100),
        "CAPÍTULO 1: HISTÓRIA DA DEMOCRACIA E DO HOSPITAL DA CAPITAL\n"
        "Autor: Professor Carlos Eduardo - Vitória, 15/01/2026\n"
        "Este documento é um artigo acadêmico completamente aleatório e não possui relação com guias.",
    )
    pdf_bytes = doc_aleatorio.tobytes()
    client = app.test_client()

    data = {
        "files": (io.BytesIO(pdf_bytes), "artigo_aleatorio.pdf"),
        "categoria": "auto",
    }

    res = client.post("/api/processar", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    json_data = res.get_json()
    assert "erro" in json_data
    assert "Nenhuma Guia de Entrega Prisional válida" in json_data["erro"]
