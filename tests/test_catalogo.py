import httpx
import pytest

from lista_animes.catalogo import CatalogoIndisponivel, ler_anime
from tests.conftest import frieren_da_jikan


def busca_com(*animes: dict) -> httpx.Response:
    return httpx.Response(200, json={"pagination": {}, "data": list(animes)})


def test_ler_anime_converte_resposta_real_da_jikan():
    anime = ler_anime(frieren_da_jikan()["data"])

    assert anime.mal_id == 52991
    assert anime.titulo == "Sousou no Frieren"
    assert anime.titulo_ingles == "Frieren: Beyond Journey's End"
    assert anime.total_episodios == 28
    assert anime.imagem_url == "https://cdn.myanimelist.net/images/anime/1015/138006.jpg"
    assert anime.ano == 2023
    assert anime.tipo == "TV"
    assert "Fantasy" in anime.generos
    assert anime.sinopse.startswith("During their decade-long quest")


def test_ler_anime_aceita_campos_que_faltam():
    # Animes em exibição vêm sem total de episódios, ano ou nota.
    anime = ler_anime({"mal_id": 21, "title": "One Piece", "episodes": None})

    assert anime.titulo == "One Piece"
    assert anime.total_episodios is None
    assert anime.generos == []


def test_ler_anime_em_formato_inesperado_vira_erro_amigavel():
    with pytest.raises(CatalogoIndisponivel, match="formato inesperado"):
        ler_anime({"titulo": "sem os campos da Jikan"})


def test_buscar_envia_termo_limite_e_sfw(catalogo, jikan):
    jikan.responder("/anime", busca_com(frieren_da_jikan()["data"]))

    resultado = catalogo.buscar("frieren", limite=5)

    assert [a.titulo for a in resultado] == ["Sousou no Frieren"]
    [pedido] = jikan.pedidos
    assert pedido.url.params["q"] == "frieren"
    assert pedido.url.params["limit"] == "5"
    assert pedido.url.params["sfw"] == "true"


def test_buscar_sem_resultados(catalogo, jikan):
    jikan.responder("/anime", busca_com())

    assert catalogo.buscar("xyzxyz") == []


def test_buscar_remove_animes_repetidos(catalogo, jikan):
    frieren = frieren_da_jikan()["data"]
    jikan.responder("/anime", busca_com(frieren, {"mal_id": 1, "title": "Cowboy Bebop"}, frieren))

    assert [a.mal_id for a in catalogo.buscar("x")] == [52991, 1]


def test_detalhes(catalogo, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))

    assert catalogo.detalhes(52991).titulo == "Sousou no Frieren"


def test_detalhes_de_anime_que_nao_existe_devolve_none(catalogo, jikan):
    jikan.responder("/anime/999999/full", httpx.Response(404, json={"status": 404}))

    assert catalogo.detalhes(999999) is None


@pytest.mark.parametrize(
    ("resposta", "mensagem"),
    [
        # O erro que vimos de verdade: o MyAnimeList fora do ar.
        (httpx.Response(504, json={"status": 504}), "fora do ar"),
        (httpx.Response(500), "fora do ar"),
        (httpx.Response(429), "Muitas consultas"),
        (httpx.Response(400), "erro 400"),
        (httpx.Response(200, text="<html>não é JSON</html>"), "formato inesperado"),
        (httpx.Response(200, json={"sem": "data"}), "formato inesperado"),
        (httpx.ConnectError("sem internet"), "Confira a internet"),
        (httpx.ReadTimeout("demorou"), "demorou demais"),
    ],
)
def test_falhas_da_jikan_viram_mensagens_amigaveis(catalogo, jikan, resposta, mensagem):
    # A Jikan inteira falhando: a busca, o /full e o /anime/{id} simples (a reserva).
    jikan.responder("/anime", resposta)
    jikan.responder("/anime/52991/full", resposta)
    jikan.responder("/anime/52991", resposta)

    with pytest.raises(CatalogoIndisponivel, match=mensagem):
        catalogo.buscar("frieren")
    with pytest.raises(CatalogoIndisponivel, match=mensagem):
        catalogo.detalhes(52991)


def test_com_o_full_fora_do_ar_detalhes_vem_sem_as_temporadas(catalogo, jikan):
    # O que acontece com o MyAnimeList fora do ar: só a cópia guardada pela Jikan responde.
    jikan.responder("/anime/52991/full", httpx.Response(504))
    simples = frieren_da_jikan()
    del simples["data"]["relations"]  # o /anime/{id} simples não traz as relações
    jikan.responder("/anime/52991", httpx.Response(200, json=simples))

    anime = catalogo.detalhes(52991)

    assert anime.titulo == "Sousou no Frieren"
    assert anime.relacionados is None  # "não sei", e não "não tem"


def test_full_que_responde_nao_usa_a_reserva(catalogo, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))

    assert [r.mal_id for r in catalogo.detalhes(52991).relacionados] == [59978]
    assert [p.url.path for p in jikan.pedidos] == ["/v4/anime/52991/full"]
