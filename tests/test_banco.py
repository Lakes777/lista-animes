import sqlite3

import pytest
from pydantic import ValidationError

from lista_animes.banco import AnimeRepetido, Banco
from lista_animes.modelos import AnimeAtualizacao, AnimeNovo, Status


@pytest.fixture
def banco(tmp_path):
    # Cada teste ganha um banco novo numa pasta temporária: nunca toca na sua lista real.
    return Banco(tmp_path / "teste.db")


def frieren(**extras) -> AnimeNovo:
    return AnimeNovo(titulo="Sousou no Frieren", mal_id=52991, total_episodios=28, **extras)


def test_banco_novo_comeca_vazio(banco):
    assert banco.listar() == []


def test_adicionar_devolve_anime_com_id_e_valores_padrao(banco):
    anime = banco.adicionar(frieren())

    assert anime.id == 1
    assert anime.titulo == "Sousou no Frieren"
    assert anime.status is Status.QUERO_VER
    assert anime.episodios_vistos == 0
    assert anime.nota is None
    assert anime.criado_em.tzinfo is not None


def test_dados_continuam_salvos_ao_reabrir_o_banco(tmp_path):
    Banco(tmp_path / "lista.db").adicionar(frieren(nota=10))

    reaberto = Banco(tmp_path / "lista.db")

    [anime] = reaberto.listar()
    assert anime.titulo == "Sousou no Frieren"
    assert anime.nota == 10


def test_listar_mantem_a_ordem_em_que_foram_adicionados(banco):
    banco.adicionar(frieren())
    banco.adicionar(AnimeNovo(titulo="Cowboy Bebop", mal_id=1))

    assert [a.titulo for a in banco.listar()] == ["Sousou no Frieren", "Cowboy Bebop"]


def test_nao_deixa_adicionar_o_mesmo_anime_duas_vezes(banco):
    banco.adicionar(frieren())

    with pytest.raises(AnimeRepetido):
        banco.adicionar(frieren())
    assert len(banco.listar()) == 1


def test_animes_sem_mal_id_podem_ser_varios(banco):
    # O UNIQUE do SQLite deixa vários NULL: animes cadastrados à mão não brigam entre si.
    banco.adicionar(AnimeNovo(titulo="Anime A"))
    banco.adicionar(AnimeNovo(titulo="Anime B"))

    assert len(banco.listar()) == 2


def test_buscar_por_id(banco):
    criado = banco.adicionar(frieren())

    assert banco.buscar(criado.id) == criado
    assert banco.buscar(999) is None


def test_atualizar_muda_so_os_campos_enviados(banco):
    criado = banco.adicionar(frieren())

    atualizado = banco.atualizar(
        criado.id, AnimeAtualizacao(status=Status.ASSISTINDO, episodios_vistos=5)
    )

    assert atualizado.status is Status.ASSISTINDO
    assert atualizado.episodios_vistos == 5
    assert atualizado.titulo == "Sousou no Frieren"
    assert banco.buscar(criado.id) == atualizado


def test_atualizar_anime_que_nao_existe_devolve_none(banco):
    assert banco.atualizar(999, AnimeAtualizacao(nota=8)) is None


def test_atualizar_nao_deixa_passar_do_total_de_episodios(banco):
    criado = banco.adicionar(frieren(episodios_vistos=20))

    with pytest.raises(ValidationError):
        banco.atualizar(criado.id, AnimeAtualizacao(episodios_vistos=29))
    assert banco.buscar(criado.id).episodios_vistos == 20


def test_remover(banco):
    criado = banco.adicionar(frieren())

    assert banco.remover(criado.id) is True
    assert banco.buscar(criado.id) is None
    assert banco.remover(criado.id) is False


def test_titulo_com_aspas_e_sql_e_salvo_como_texto_normal(banco):
    titulo = "Robert'); DROP TABLE animes;--"

    banco.adicionar(AnimeNovo(titulo=titulo))

    assert banco.listar()[0].titulo == titulo


def test_tabela_tem_as_colunas_esperadas(tmp_path):
    Banco(tmp_path / "lista.db")

    with sqlite3.connect(tmp_path / "lista.db") as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(animes)")}
    assert {"id", "titulo", "mal_id", "status", "episodios_vistos", "nota"} <= colunas
