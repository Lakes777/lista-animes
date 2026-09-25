import pytest
from pydantic import ValidationError

from lista_animes.modelos import AnimeNovo, Status


def test_titulo_perde_espacos_das_pontas():
    assert AnimeNovo(titulo="  Naruto  ").titulo == "Naruto"


@pytest.mark.parametrize("titulo", ["", "   ", "x" * 201])
def test_recusa_titulo_vazio_ou_grande_demais(titulo):
    with pytest.raises(ValidationError):
        AnimeNovo(titulo=titulo)


@pytest.mark.parametrize("nota", [0, 11, -1])
def test_nota_precisa_ficar_entre_1_e_10(nota):
    with pytest.raises(ValidationError):
        AnimeNovo(titulo="Naruto", nota=nota)


def test_aceita_notas_nos_limites():
    assert AnimeNovo(titulo="A", nota=1).nota == 1
    assert AnimeNovo(titulo="A", nota=10).nota == 10


def test_recusa_episodios_vistos_acima_do_total():
    with pytest.raises(ValidationError, match="passa do total"):
        AnimeNovo(titulo="Frieren", total_episodios=28, episodios_vistos=29)


def test_sem_total_conhecido_qualquer_quantidade_de_vistos_vale():
    # Animes em exibição (ex.: One Piece) ainda não têm total de episódios.
    assert AnimeNovo(titulo="One Piece", episodios_vistos=1100).episodios_vistos == 1100


def test_status_aceita_texto_e_recusa_valor_desconhecido():
    assert AnimeNovo(titulo="A", status="concluido").status is Status.CONCLUIDO
    with pytest.raises(ValidationError):
        AnimeNovo(titulo="A", status="vendo_talvez")


def test_imagem_url_aceita_link_web():
    url = "https://cdn.myanimelist.net/images/anime/1015/138006.jpg"

    assert AnimeNovo(titulo="Frieren", imagem_url=url).imagem_url == url


@pytest.mark.parametrize("url", ["string", "cdn.myanimelist.net/a.jpg", "javascript:alert(1)", "https://"])
def test_imagem_url_recusa_o_que_nao_e_link_web(url):
    with pytest.raises(ValidationError):
        AnimeNovo(titulo="Frieren", imagem_url=url)
