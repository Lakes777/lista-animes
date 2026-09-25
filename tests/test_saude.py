def test_saude_responde_ok(cliente):
    resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_documentacao_automatica_existe(cliente):
    assert cliente.get("/docs").status_code == 200


def test_pagina_inicial_leva_para_a_documentacao(cliente):
    resposta = cliente.get("/", follow_redirects=False)

    assert resposta.status_code == 307
    assert resposta.headers["location"] == "/docs"
