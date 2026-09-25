import sqlite3
from contextlib import closing

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


def test_remover_apaga_so_o_anime_escolhido(banco):
    frieren_salvo = banco.adicionar(frieren())
    bebop = banco.adicionar(AnimeNovo(titulo="Cowboy Bebop", mal_id=1))

    banco.remover(bebop.id)

    assert banco.listar() == [frieren_salvo]


def test_titulo_com_aspas_e_sql_e_salvo_como_texto_normal(banco):
    titulo = "Robert'); DROP TABLE animes;--"

    banco.adicionar(AnimeNovo(titulo=titulo))

    assert banco.listar()[0].titulo == titulo


def test_tabela_tem_as_colunas_esperadas(tmp_path):
    Banco(tmp_path / "lista.db")

    with sqlite3.connect(tmp_path / "lista.db") as conexao:
        colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(animes)")}
    assert {"id", "titulo", "mal_id", "status", "episodios_vistos", "nota"} <= colunas


@pytest.fixture
def banco_com_animes(banco):
    banco.adicionar(frieren(status=Status.CONCLUIDO, episodios_vistos=28, nota=10))
    banco.adicionar(AnimeNovo(titulo="Cowboy Bebop", mal_id=1, status=Status.ASSISTINDO,
                              total_episodios=26, episodios_vistos=10))
    banco.adicionar(AnimeNovo(titulo="Fullmetal Alchemist: Brotherhood", mal_id=5114,
                              status=Status.CONCLUIDO, total_episodios=64,
                              episodios_vistos=64, nota=9))
    banco.adicionar(AnimeNovo(titulo="100% Pascal-sensei", status=Status.QUERO_VER))
    return banco


def titulos(animes):
    return [a.titulo for a in animes]


def test_filtrar_por_status(banco_com_animes):
    concluidos = banco_com_animes.listar(status=Status.CONCLUIDO)

    assert titulos(concluidos) == ["Sousou no Frieren", "Fullmetal Alchemist: Brotherhood"]
    assert banco_com_animes.listar(status=Status.ABANDONADO) == []


def test_busca_por_parte_do_titulo_ignora_maiusculas(banco_com_animes):
    assert titulos(banco_com_animes.listar(busca="FRIER")) == ["Sousou no Frieren"]
    assert titulos(banco_com_animes.listar(busca="  bebop ")) == ["Cowboy Bebop"]


def test_busca_vazia_nao_filtra(banco_com_animes):
    assert len(banco_com_animes.listar(busca="   ")) == 4


def test_busca_trata_porcentagem_e_underline_como_texto(banco_com_animes):
    # Sem escapar, "%" e "_" seriam curingas do LIKE e achariam todos os animes.
    assert titulos(banco_com_animes.listar(busca="100%")) == ["100% Pascal-sensei"]
    assert titulos(banco_com_animes.listar(busca="%")) == ["100% Pascal-sensei"]
    assert banco_com_animes.listar(busca="_") == []


def test_filtros_juntos(banco_com_animes):
    resultado = banco_com_animes.listar(status=Status.CONCLUIDO, busca="alchemist")

    assert titulos(resultado) == ["Fullmetal Alchemist: Brotherhood"]


def test_estatisticas_da_lista_vazia(banco):
    estatisticas = banco.estatisticas()

    assert estatisticas.total == 0
    assert estatisticas.por_status == {status: 0 for status in Status}
    assert estatisticas.episodios_assistidos == 0
    assert estatisticas.nota_media is None


def test_estatisticas_somam_e_contam_por_status(banco_com_animes):
    estatisticas = banco_com_animes.estatisticas()

    assert estatisticas.total == 4
    assert estatisticas.por_status == {
        Status.QUERO_VER: 1,
        Status.ASSISTINDO: 1,
        Status.CONCLUIDO: 2,
        Status.ABANDONADO: 0,
    }
    assert estatisticas.episodios_assistidos == 28 + 10 + 64
    assert estatisticas.nota_media == 9.5  # só conta quem tem nota: (10 + 9) / 2


def test_nota_media_arredonda_meio_para_cima(banco):
    # (8 + 8 + 8 + 9) / 4 = 8.25. O round() do Python daria 8.2; aqui fica 8.3.
    for i, nota in enumerate([8, 8, 8, 9]):
        banco.adicionar(AnimeNovo(titulo=f"Anime {i}", nota=nota))

    assert banco.estatisticas().nota_media == 8.3


def test_ao_abrir_limpa_imagem_url_invalida_salva_por_versao_antiga(tmp_path):
    # Simula um banco de antes da validação do link: imagem_url = "string".
    caminho = tmp_path / "antigo.db"
    Banco(caminho)
    with closing(sqlite3.connect(caminho)) as conexao, conexao:
        conexao.executemany(
            "INSERT INTO animes (titulo, status, imagem_url, criado_em) VALUES (?, ?, ?, ?)",
            [
                ("Antigo", "quero_ver", "string", "2026-09-25T20:59:48+00:00"),
                ("Bom", "quero_ver", "https://cdn.myanimelist.net/a.jpg", "2026-09-25T21:00:00+00:00"),
            ],
        )

    antigo, bom = Banco(caminho).listar()  # antes da migração, isto dava ValidationError

    assert antigo.imagem_url is None
    assert bom.imagem_url == "https://cdn.myanimelist.net/a.jpg"
