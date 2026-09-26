import json
import sqlite3
from contextlib import closing
from datetime import date

import httpx
import pytest

from lista_animes.banco import Banco
from lista_animes.catalogo import ler_anime
from lista_animes.modelos import AnimeNovo
from tests.conftest import DADOS

# Respostas reais da Jikan (/anime/{id}/full), gravadas em tests/dados.
# Shingeki no Kyojin: 16498 (1ª temporada) -> 25777 (2ª) -> 35760 (3ª).
# Sousou no Frieren: 52991 (1ª) -> 59978 (2ª).


def da_jikan(mal_id: int) -> dict:
    return json.loads((DADOS / f"jikan_anime_{mal_id}.json").read_text(encoding="utf-8"))


def responder_com_os_dados_gravados(jikan, *mal_ids):
    for mal_id in mal_ids:
        jikan.responder(f"/anime/{mal_id}/full", httpx.Response(200, json=da_jikan(mal_id)))


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path / "teste.db")


def anime(titulo, mal_id, estreia=None) -> AnimeNovo:
    return AnimeNovo(titulo=titulo, mal_id=mal_id, estreia=estreia)


# ---------- Catálogo ----------


def test_detalhes_trazem_estreia_e_temporadas_vizinhas():
    snk2 = ler_anime(da_jikan(25777)["data"])

    assert snk2.estreia == date(2017, 4, 1)
    assert snk2.tipo == "TV"
    assert [(r.mal_id, r.relacao) for r in snk2.relacionados] == [
        (16498, "anterior"),
        (35760, "seguinte"),
    ]


def test_relacoes_que_nao_sao_temporadas_ficam_de_fora():
    # A 1ª temporada tem mangá (Adaptation), OVA (Side Story), spin-offs e resumos.
    snk1 = ler_anime(da_jikan(16498)["data"])

    assert [(r.mal_id, r.titulo, r.relacao) for r in snk1.relacionados] == [
        (25777, "Shingeki no Kyojin Season 2", "seguinte")
    ]


def test_relacao_com_manga_e_ignorada():
    dados = {
        "mal_id": 1,
        "title": "X",
        "relations": [{"relation": "Sequel", "entry": [{"mal_id": 9, "type": "manga", "name": "X"}]}],
    }

    assert ler_anime(dados).relacionados == []


def test_anime_sem_data_de_estreia():
    assert ler_anime({"mal_id": 1, "title": "X", "aired": {"from": None}}).estreia is None
    assert ler_anime({"mal_id": 1, "title": "X"}).estreia is None


# ---------- Banco ----------


def test_anime_sozinho_e_uma_franquia_propria(banco):
    frieren = banco.adicionar(anime("Frieren", 52991))
    bebop = banco.adicionar(anime("Cowboy Bebop", 1))

    assert frieren.franquia == frieren.id
    assert bebop.franquia == bebop.id


def test_temporada_seguinte_entra_na_franquia_da_anterior(banco):
    snk1 = banco.adicionar(anime("SnK", 16498))
    snk2 = banco.adicionar(anime("SnK 2", 25777), relacionados=[16498, 35760])

    assert snk2.franquia == snk1.franquia
    assert [a.franquia for a in banco.listar()] == [snk1.id, snk1.id]


def test_relacionado_fora_da_lista_nao_junta_nada(banco):
    banco.adicionar(anime("Frieren", 52991))
    snk2 = banco.adicionar(anime("SnK 2", 25777), relacionados=[16498, 35760])

    assert snk2.franquia == snk2.id


def test_temporada_do_meio_junta_duas_franquias(banco):
    snk1 = banco.adicionar(anime("SnK", 16498))
    snk3 = banco.adicionar(anime("SnK 3", 35760))
    assert snk1.franquia != snk3.franquia

    banco.adicionar(anime("SnK 2", 25777), relacionados=[16498, 35760])

    assert {a.franquia for a in banco.listar()} == {snk1.id}


def test_lista_deixa_temporadas_juntas_e_em_ordem_de_estreia(banco):
    # Adicionados fora de ordem: 2ª temporada, outro anime e, por último, a 1ª.
    banco.adicionar(anime("SnK 2", 25777, date(2017, 4, 1)))
    banco.adicionar(anime("Frieren", 52991, date(2023, 9, 29)))
    banco.adicionar(anime("SnK", 16498, date(2013, 4, 7)), relacionados=[25777])

    assert [a.titulo for a in banco.listar()] == ["SnK", "SnK 2", "Frieren"]


def test_franquia_devolve_todas_as_temporadas(banco):
    snk1 = banco.adicionar(anime("SnK", 16498, date(2013, 4, 7)))
    banco.adicionar(anime("Frieren", 52991))
    snk2 = banco.adicionar(anime("SnK 2", 25777, date(2017, 4, 1)), relacionados=[16498])

    assert [a.id for a in banco.franquia(snk2.id)] == [snk1.id, snk2.id]
    assert banco.franquia(999) is None


def test_completar_so_preenche_o_que_esta_vazio(banco):
    sem_data = banco.adicionar(anime("SnK", 16498))
    com_data = banco.adicionar(AnimeNovo(titulo="Filme", tipo="Movie", estreia=date(2020, 1, 1)))

    banco.completar(sem_data.id, "TV", date(2013, 4, 7))
    banco.completar(com_data.id, "TV", date(1999, 1, 1))

    assert (banco.buscar(sem_data.id).tipo, banco.buscar(sem_data.id).estreia) == ("TV", date(2013, 4, 7))
    assert (banco.buscar(com_data.id).tipo, banco.buscar(com_data.id).estreia) == ("Movie", date(2020, 1, 1))


def test_banco_antigo_ganha_as_colunas_novas(tmp_path):
    # Um banco criado pela versão anterior, sem tipo, estreia e franquia.
    caminho = tmp_path / "antigo.db"
    with closing(sqlite3.connect(caminho)) as conexao, conexao:
        conexao.execute(
            "CREATE TABLE animes (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, "
            "mal_id INTEGER UNIQUE, total_episodios INTEGER, imagem_url TEXT, status TEXT NOT NULL, "
            "episodios_vistos INTEGER NOT NULL DEFAULT 0, nota INTEGER, criado_em TEXT NOT NULL)"
        )
        conexao.execute(
            "INSERT INTO animes (titulo, mal_id, status, criado_em) "
            "VALUES ('Antigo', 16498, 'concluido', '2026-09-01T00:00:00+00:00')"
        )

    banco = Banco(caminho)
    antigo = banco.listar()[0]

    assert (antigo.franquia, antigo.tipo, antigo.estreia) == (antigo.id, None, None)
    # E o anime antigo recebe as temporadas novas na franquia dele.
    assert banco.adicionar(anime("SnK 2", 25777), relacionados=[16498]).franquia == antigo.id


# ---------- Rotas ----------


def test_adicionar_do_catalogo_guarda_tipo_e_estreia(cliente, jikan):
    responder_com_os_dados_gravados(jikan, 16498)

    snk1 = cliente.post("/animes/do-catalogo/16498").json()

    assert (snk1["tipo"], snk1["estreia"], snk1["franquia"]) == ("TV", "2013-04-07", snk1["id"])


def test_adicionar_do_catalogo_junta_com_a_temporada_anterior(cliente, jikan):
    responder_com_os_dados_gravados(jikan, 16498, 25777)
    snk1 = cliente.post("/animes/do-catalogo/16498").json()

    snk2 = cliente.post("/animes/do-catalogo/25777").json()

    assert snk2["franquia"] == snk1["franquia"]


def test_temporada_antiga_sem_data_e_completada_ao_juntar(cliente, jikan):
    # Adicionada à mão (ou antes desta versão): sem tipo nem estreia.
    antiga = cliente.post("/animes", json={"titulo": "Shingeki no Kyojin", "mal_id": 16498}).json()
    responder_com_os_dados_gravados(jikan, 16498, 25777)

    cliente.post("/animes/do-catalogo/25777")

    completada = cliente.get(f"/animes/{antiga['id']}").json()
    assert (completada["tipo"], completada["estreia"]) == ("TV", "2013-04-07")
    assert [a["mal_id"] for a in cliente.get("/animes").json()] == [16498, 25777]


def test_jikan_fora_do_ar_ao_completar_nao_impede_de_adicionar(cliente, jikan):
    cliente.post("/animes", json={"titulo": "Shingeki no Kyojin", "mal_id": 16498})
    responder_com_os_dados_gravados(jikan, 25777)
    jikan.responder("/anime/16498/full", httpx.Response(504))
    jikan.responder("/anime/16498", httpx.Response(504))

    resposta = cliente.post("/animes/do-catalogo/25777")

    assert resposta.status_code == 201
    assert len({a["franquia"] for a in cliente.get("/animes").json()}) == 1


def test_outras_temporadas_mostra_a_proxima(cliente, jikan):
    responder_com_os_dados_gravados(jikan, 16498, 25777)
    cliente.post("/animes/do-catalogo/16498")
    snk2 = cliente.post("/animes/do-catalogo/25777").json()
    jikan.pedidos.clear()

    resposta = cliente.get(f"/animes/{snk2['id']}/outras-temporadas")

    assert resposta.status_code == 200
    assert resposta.json() == [
        {"mal_id": 35760, "titulo": "Shingeki no Kyojin Season 3", "relacao": "seguinte"}
    ]
    # Consulta só as pontas da franquia (1ª e última), uma vez cada.
    assert sorted(p.url.path for p in jikan.pedidos) == [
        "/v4/anime/16498/full",
        "/v4/anime/25777/full",
    ]


def test_outras_temporadas_de_um_anime_sozinho(cliente, jikan):
    responder_com_os_dados_gravados(jikan, 52991)
    frieren = cliente.post("/animes/do-catalogo/52991").json()

    temporadas = cliente.get(f"/animes/{frieren['id']}/outras-temporadas").json()

    assert [(t["mal_id"], t["relacao"]) for t in temporadas] == [(59978, "seguinte")]


def test_outras_temporadas_sem_mal_id_nao_consulta_a_jikan(cliente, jikan):
    manual = cliente.post("/animes", json={"titulo": "Anime caseiro"}).json()

    assert cliente.get(f"/animes/{manual['id']}/outras-temporadas").json() == []
    assert jikan.pedidos == []


def test_outras_temporadas_de_anime_que_nao_existe_devolve_404(cliente):
    assert cliente.get("/animes/999/outras-temporadas").status_code == 404


def sem_relacoes(mal_id: int) -> httpx.Response:
    # Como o /anime/{id} simples responde: os dados do anime, sem as relações.
    dados = da_jikan(mal_id)
    del dados["data"]["relations"]
    return httpx.Response(200, json=dados)


def test_outras_temporadas_com_jikan_fora_do_ar_devolve_503(cliente, jikan):
    frieren = cliente.post(
        "/animes", json={"titulo": "Frieren", "mal_id": 52991, "estreia": "2023-09-29"}
    ).json()
    jikan.responder("/anime/52991/full", httpx.Response(504))
    jikan.responder("/anime/52991", httpx.Response(504))

    resposta = cliente.get(f"/animes/{frieren['id']}/outras-temporadas")

    assert resposta.status_code == 503
    assert "fora do ar" in resposta.json()["detail"]


def test_outras_temporadas_sem_as_relacoes_devolve_503(cliente, jikan):
    # O MyAnimeList fora do ar: a Jikan tem o anime, mas não as relações.
    frieren = cliente.post(
        "/animes", json={"titulo": "Frieren", "mal_id": 52991, "estreia": "2023-09-29"}
    ).json()
    jikan.responder("/anime/52991/full", httpx.Response(504))
    jikan.responder("/anime/52991", sem_relacoes(52991))

    resposta = cliente.get(f"/animes/{frieren['id']}/outras-temporadas")

    assert resposta.status_code == 503
    assert "sem ele não dá para ver as temporadas" in resposta.json()["detail"]


def test_com_o_myanimelist_fora_do_ar_adiciona_sem_agrupar_e_junta_depois(cliente, jikan):
    responder_com_os_dados_gravados(jikan, 16498)
    snk1 = cliente.post("/animes/do-catalogo/16498").json()
    # A 2ª temporada chega com o MyAnimeList fora do ar: entra, mas sozinha.
    jikan.responder("/anime/25777/full", httpx.Response(504))
    jikan.responder("/anime/25777", sem_relacoes(25777))
    snk2 = cliente.post("/animes/do-catalogo/25777").json()
    assert snk2["franquia"] != snk1["franquia"]

    # Depois ele volta, e "outras temporadas" encontra a vizinha na lista e junta as duas.
    responder_com_os_dados_gravados(jikan, 25777)
    faltando = cliente.get(f"/animes/{snk1['id']}/outras-temporadas").json()

    assert faltando == []  # a seguinte (a 2ª) já está na lista
    assert {a["franquia"] for a in cliente.get("/animes").json()} == {snk1["franquia"]}


def test_demo_comeca_com_duas_temporadas_juntas(tmp_path, catalogo):
    from fastapi.testclient import TestClient

    from lista_animes.app import criar_app

    cliente = TestClient(criar_app(tmp_path / "demo.db", catalogo, demo=True))
    snk = [a for a in cliente.get("/animes").json() if a["titulo"].startswith("Shingeki")]

    assert [a["mal_id"] for a in snk] == [16498, 25777]
    assert snk[0]["franquia"] == snk[1]["franquia"]
