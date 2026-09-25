import json

import pytest
from fastapi.testclient import TestClient

from lista_animes import __main__ as principal
from lista_animes.app import ARQUIVO_EXEMPLOS, LIMITE_DEMO, criar_app
from lista_animes.banco import Banco
from lista_animes.modelos import AnimeNovo


@pytest.fixture
def cliente_demo(tmp_path, catalogo):
    return TestClient(criar_app(tmp_path / "demo.db", catalogo, demo=True))


def test_fora_da_demo_a_lista_comeca_vazia_e_sem_limite(cliente):
    assert cliente.get("/animes").json() == []
    assert cliente.get("/info").json() == {"demo": False, "limite_animes": None}


def test_demo_comeca_com_a_lista_de_exemplo(cliente_demo):
    exemplos = json.loads(ARQUIVO_EXEMPLOS.read_text(encoding="utf-8"))

    titulos = [a["titulo"] for a in cliente_demo.get("/animes").json()]

    assert titulos == [e["titulo"] for e in exemplos]
    assert cliente_demo.get("/info").json() == {"demo": True, "limite_animes": LIMITE_DEMO}


def test_exemplos_sao_validos_e_tem_capa():
    for dados in json.loads(ARQUIVO_EXEMPLOS.read_text(encoding="utf-8")):
        anime = AnimeNovo(**dados)
        assert anime.imagem_url.startswith("https://cdn.myanimelist.net/")


def test_demo_nao_substitui_uma_lista_que_ja_existe(tmp_path, catalogo):
    caminho = tmp_path / "demo.db"
    Banco(caminho).adicionar(AnimeNovo(titulo="Meu anime"))

    cliente = TestClient(criar_app(caminho, catalogo, demo=True))

    assert [a["titulo"] for a in cliente.get("/animes").json()] == ["Meu anime"]


def test_demo_recusa_adicionar_depois_do_limite(cliente_demo, jikan):
    cliente_demo.app.state.limite_animes = 9  # a lista de exemplo tem 8

    primeiro = cliente_demo.post("/animes", json={"titulo": "Nono"})
    passou = cliente_demo.post("/animes", json={"titulo": "Décimo"})
    pelo_catalogo = cliente_demo.post("/animes/do-catalogo/52991")

    assert primeiro.status_code == 201
    assert passou.status_code == 403
    assert "até 9 animes" in passou.json()["detail"]
    assert pelo_catalogo.status_code == 403
    assert jikan.pedidos == []  # o limite é conferido antes de gastar uma consulta à Jikan


def test_main_le_a_configuracao_das_variaveis_de_ambiente(tmp_path, monkeypatch):
    chamadas = {}
    monkeypatch.setattr(
        principal.uvicorn, "run", lambda app, host, port: chamadas.update(app=app, host=host, port=port)
    )
    monkeypatch.setenv("LISTA_ANIMES_BANCO", str(tmp_path / "online.db"))
    monkeypatch.setenv("LISTA_ANIMES_DEMO", "1")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "10000")

    principal.main()

    assert chamadas["host"] == "0.0.0.0"
    assert chamadas["port"] == 10000
    assert chamadas["app"].state.demo is True


def test_main_sem_variaveis_usa_so_o_proprio_pc(tmp_path, monkeypatch):
    chamadas = {}
    monkeypatch.setattr(
        principal.uvicorn, "run", lambda app, host, port: chamadas.update(app=app, host=host, port=port)
    )
    monkeypatch.chdir(tmp_path)  # o animes.db padrão é criado aqui, não no projeto
    for variavel in ("LISTA_ANIMES_BANCO", "LISTA_ANIMES_DEMO", "HOST", "PORT"):
        monkeypatch.delenv(variavel, raising=False)

    principal.main()

    assert chamadas["host"] == "127.0.0.1"  # só o próprio PC acessa
    assert chamadas["port"] == 8000
    assert chamadas["app"].state.demo is False
