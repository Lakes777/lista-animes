from fastapi.testclient import TestClient

from lista_animes.app import criar_app


def test_saude_responde_ok():
    # O TestClient chama a API direto na memória, sem abrir porta nem usar internet.
    cliente = TestClient(criar_app())

    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_documentacao_automatica_existe():
    cliente = TestClient(criar_app())

    assert cliente.get("/docs").status_code == 200


def test_pagina_inicial_leva_para_a_documentacao():
    cliente = TestClient(criar_app())

    resposta = cliente.get("/", follow_redirects=False)

    assert resposta.status_code == 307
    assert resposta.headers["location"] == "/docs"
