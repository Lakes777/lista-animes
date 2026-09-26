import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from lista_animes import app as modulo_app
from lista_animes.app import criar_app

FRIEREN = {"titulo": "Sousou no Frieren", "mal_id": 52991, "total_episodios": 28}


@pytest.fixture
def frieren(cliente):
    resposta = cliente.post("/animes", json=FRIEREN)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def comentar(cliente, anime_id, **dados):
    resposta = cliente.post(f"/animes/{anime_id}/comentarios", json=dados)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_anime_novo_nao_tem_comentarios(cliente, frieren):
    assert frieren["comentarios"] == 0
    assert cliente.get(f"/animes/{frieren['id']}/comentarios").json() == []


def test_comentar_devolve_o_comentario_criado(cliente, frieren):
    comentario = comentar(cliente, frieren["id"], texto="  A luta foi incrível  ", episodio=7)

    assert comentario["id"] == 1
    assert comentario["anime_id"] == frieren["id"]
    assert comentario["texto"] == "A luta foi incrível"  # espaços das pontas saem
    assert comentario["episodio"] == 7
    assert "criado_em" in comentario


def test_episodio_do_comentario_e_opcional(cliente, frieren):
    assert comentar(cliente, frieren["id"], texto="Comecei por indicação")["episodio"] is None


def test_comentarios_vem_do_mais_novo_para_o_mais_antigo(cliente, frieren):
    comentar(cliente, frieren["id"], texto="primeiro")
    comentar(cliente, frieren["id"], texto="segundo")

    textos = [c["texto"] for c in cliente.get(f"/animes/{frieren['id']}/comentarios").json()]

    assert textos == ["segundo", "primeiro"]


def test_anime_mostra_quantos_comentarios_tem(cliente, frieren):
    outro = cliente.post("/animes", json={"titulo": "Cowboy Bebop", "mal_id": 1}).json()
    comentar(cliente, frieren["id"], texto="um")
    comentar(cliente, frieren["id"], texto="dois")

    contagem = {a["titulo"]: a["comentarios"] for a in cliente.get("/animes").json()}

    assert contagem == {"Sousou no Frieren": 2, "Cowboy Bebop": 0}
    assert cliente.get(f"/animes/{frieren['id']}").json()["comentarios"] == 2
    assert cliente.get(f"/animes/{outro['id']}/comentarios").json() == []


@pytest.mark.parametrize(
    "dados",
    [
        {"texto": ""},
        {"texto": "   "},
        {"texto": "x" * 1001},
        {"texto": "ok", "episodio": 0},
        {},
    ],
)
def test_comentario_invalido_devolve_422(cliente, frieren, dados):
    assert cliente.post(f"/animes/{frieren['id']}/comentarios", json=dados).status_code == 422
    assert cliente.get(f"/animes/{frieren['id']}/comentarios").json() == []


def test_episodio_alem_do_total_devolve_422(cliente, frieren):
    resposta = cliente.post(f"/animes/{frieren['id']}/comentarios", json={"texto": "?", "episodio": 29})

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Esse anime tem só 28 episódios"


def test_sem_total_de_episodios_aceita_qualquer_episodio(cliente):
    one_piece = cliente.post("/animes", json={"titulo": "One Piece", "mal_id": 21}).json()

    assert comentar(cliente, one_piece["id"], texto="Enfim", episodio=1087)["episodio"] == 1087


def test_comentar_em_anime_que_nao_existe_devolve_404(cliente):
    assert cliente.post("/animes/999/comentarios", json={"texto": "oi"}).status_code == 404
    assert cliente.get("/animes/999/comentarios").status_code == 404


def test_apagar_comentario(cliente, frieren):
    fica = comentar(cliente, frieren["id"], texto="fica")
    sai = comentar(cliente, frieren["id"], texto="sai")

    resposta = cliente.delete(f"/animes/{frieren['id']}/comentarios/{sai['id']}")

    assert resposta.status_code == 204
    assert cliente.get(f"/animes/{frieren['id']}/comentarios").json() == [fica]


def test_nao_apaga_comentario_pelo_link_de_outro_anime(cliente, frieren):
    outro = cliente.post("/animes", json={"titulo": "Cowboy Bebop", "mal_id": 1}).json()
    comentario = comentar(cliente, frieren["id"], texto="meu")

    resposta = cliente.delete(f"/animes/{outro['id']}/comentarios/{comentario['id']}")

    assert resposta.status_code == 404
    assert len(cliente.get(f"/animes/{frieren['id']}/comentarios").json()) == 1


def test_remover_o_anime_apaga_os_comentarios_dele(cliente, frieren, tmp_path):
    comentar(cliente, frieren["id"], texto="vai junto")

    cliente.delete(f"/animes/{frieren['id']}")

    # Olha direto no arquivo: o comentário não pode ficar sobrando no banco.
    with closing(sqlite3.connect(tmp_path / "teste.db")) as conexao:
        assert conexao.execute("SELECT COUNT(*) FROM comentarios").fetchone()[0] == 0


def test_editar_o_anime_mantem_a_contagem_de_comentarios(cliente, frieren):
    comentar(cliente, frieren["id"], texto="oi")

    editado = cliente.patch(f"/animes/{frieren['id']}", json={"nota": 10}).json()

    assert editado["comentarios"] == 1


def test_demo_limita_os_comentarios(tmp_path, catalogo, monkeypatch):
    monkeypatch.setattr(modulo_app, "LIMITE_COMENTARIOS_DEMO", 2)
    cliente = TestClient(criar_app(tmp_path / "demo.db", catalogo, demo=True))
    anime_id = cliente.get("/animes").json()[0]["id"]
    comentar(cliente, anime_id, texto="um")
    comentar(cliente, anime_id, texto="dois")

    resposta = cliente.post(f"/animes/{anime_id}/comentarios", json={"texto": "três"})

    assert resposta.status_code == 403
    assert "até 2 comentários" in resposta.json()["detail"]


def test_fora_da_demo_nao_tem_limite_de_comentarios(cliente, frieren):
    for n in range(30):
        comentar(cliente, frieren["id"], texto=f"comentário {n}")

    assert len(cliente.get(f"/animes/{frieren['id']}/comentarios").json()) == 30
