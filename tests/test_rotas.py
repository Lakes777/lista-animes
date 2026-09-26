import httpx

from tests.conftest import frieren_da_jikan

FRIEREN = {"titulo": "Sousou no Frieren", "mal_id": 52991, "total_episodios": 28}


def adicionar(cliente, **dados):
    resposta = cliente.post("/animes", json=dados or FRIEREN)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_lista_comeca_vazia(cliente):
    resposta = cliente.get("/animes")

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_adicionar_devolve_201_com_o_anime_criado(cliente):
    anime = adicionar(cliente)

    assert anime["id"] == 1
    assert anime["titulo"] == "Sousou no Frieren"
    assert anime["status"] == "quero_ver"
    assert anime["episodios_vistos"] == 0
    assert "criado_em" in anime


def test_anime_adicionado_aparece_na_lista(cliente):
    adicionar(cliente)
    adicionar(cliente, titulo="Cowboy Bebop", mal_id=1)

    titulos = [a["titulo"] for a in cliente.get("/animes").json()]
    assert titulos == ["Sousou no Frieren", "Cowboy Bebop"]


def test_adicionar_repetido_devolve_409(cliente):
    adicionar(cliente)

    resposta = cliente.post("/animes", json=FRIEREN)

    assert resposta.status_code == 409
    assert "já está na lista" in resposta.json()["detail"]


def test_adicionar_com_dados_invalidos_devolve_422(cliente):
    resposta = cliente.post("/animes", json={"titulo": "Naruto", "nota": 11})

    assert resposta.status_code == 422
    assert cliente.get("/animes").json() == []


def test_adicionar_sem_titulo_devolve_422(cliente):
    assert cliente.post("/animes", json={"mal_id": 20}).status_code == 422


def test_ver_um_anime(cliente):
    criado = adicionar(cliente)

    resposta = cliente.get(f"/animes/{criado['id']}")

    assert resposta.status_code == 200
    assert resposta.json() == criado


def test_ver_anime_que_nao_existe_devolve_404(cliente):
    resposta = cliente.get("/animes/999")

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Anime 999 não está na lista"


def test_id_que_nao_e_numero_devolve_422(cliente):
    assert cliente.get("/animes/abc").status_code == 422


def test_editar_muda_so_os_campos_enviados(cliente):
    criado = adicionar(cliente)

    resposta = cliente.patch(
        f"/animes/{criado['id']}", json={"status": "assistindo", "episodios_vistos": 12}
    )

    assert resposta.status_code == 200
    editado = resposta.json()
    assert editado["status"] == "assistindo"
    assert editado["episodios_vistos"] == 12
    assert editado["titulo"] == criado["titulo"]
    assert cliente.get(f"/animes/{criado['id']}").json() == editado


def test_editar_passando_do_total_devolve_422_e_nao_salva(cliente):
    criado = adicionar(cliente)

    resposta = cliente.patch(f"/animes/{criado['id']}", json={"episodios_vistos": 30})

    assert resposta.status_code == 422
    assert "passa do total" in resposta.text
    assert cliente.get(f"/animes/{criado['id']}").json()["episodios_vistos"] == 0


def test_editar_com_nota_invalida_devolve_422(cliente):
    criado = adicionar(cliente)

    assert cliente.patch(f"/animes/{criado['id']}", json={"nota": 0}).status_code == 422


def test_editar_anime_que_nao_existe_devolve_404(cliente):
    assert cliente.patch("/animes/999", json={"nota": 8}).status_code == 404


def test_apagar_devolve_204_e_tira_da_lista(cliente):
    criado = adicionar(cliente)

    resposta = cliente.delete(f"/animes/{criado['id']}")

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert cliente.get(f"/animes/{criado['id']}").status_code == 404


def test_apagar_anime_que_nao_existe_devolve_404(cliente):
    assert cliente.delete("/animes/999").status_code == 404


def test_rotas_aparecem_na_documentacao(cliente):
    caminhos = cliente.get("/openapi.json").json()["paths"]

    assert set(caminhos["/animes"]) == {"get", "post"}
    assert set(caminhos["/animes/{anime_id}"]) == {"get", "patch", "delete"}


def test_exemplo_da_documentacao_e_um_anime_valido(cliente):
    # O exemplo do "Try it out" precisa funcionar se a pessoa só clicar em Execute.
    esquemas = cliente.get("/openapi.json").json()["components"]["schemas"]
    [exemplo] = esquemas["AnimeNovo"]["examples"]

    resposta = cliente.post("/animes", json=exemplo)

    assert resposta.status_code == 201
    assert resposta.json()["titulo"] == "Sousou no Frieren"


def test_listar_filtrando_por_status_e_busca(cliente):
    adicionar(cliente)
    adicionar(cliente, titulo="Cowboy Bebop", mal_id=1, status="assistindo")
    adicionar(cliente, titulo="Cowboy Bebop: O Filme", mal_id=5, status="quero_ver")

    assistindo = cliente.get("/animes", params={"status": "assistindo"}).json()
    bebop = cliente.get("/animes", params={"busca": "bebop"}).json()
    ambos = cliente.get("/animes", params={"busca": "bebop", "status": "quero_ver"}).json()

    assert [a["titulo"] for a in assistindo] == ["Cowboy Bebop"]
    assert [a["titulo"] for a in bebop] == ["Cowboy Bebop", "Cowboy Bebop: O Filme"]
    assert [a["titulo"] for a in ambos] == ["Cowboy Bebop: O Filme"]


def test_listar_com_status_desconhecido_devolve_422(cliente):
    assert cliente.get("/animes", params={"status": "vendo_talvez"}).status_code == 422


def test_estatisticas(cliente):
    adicionar(cliente, **FRIEREN, status="concluido", episodios_vistos=28, nota=10)
    adicionar(cliente, titulo="Cowboy Bebop", mal_id=1, status="assistindo", episodios_vistos=5)

    resposta = cliente.get("/animes/estatisticas")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "total": 2,
        "por_status": {"quero_ver": 0, "assistindo": 1, "concluido": 1, "abandonado": 0},
        "episodios_assistidos": 33,
        "nota_media": 10.0,
    }


def test_buscar_no_catalogo(cliente, jikan):
    jikan.responder(
        "/anime", httpx.Response(200, json={"data": [frieren_da_jikan()["data"]]})
    )

    resposta = cliente.get("/catalogo/busca", params={"q": "frieren"})

    assert resposta.status_code == 200
    [anime] = resposta.json()
    assert anime["mal_id"] == 52991
    assert anime["titulo_ingles"] == "Frieren: Beyond Journey's End"


def test_busca_no_catalogo_precisa_de_pelo_menos_2_letras(cliente, jikan):
    assert cliente.get("/catalogo/busca", params={"q": "a"}).status_code == 422
    assert jikan.pedidos == []  # nem chegou a consultar a Jikan


def test_catalogo_fora_do_ar_devolve_503_com_mensagem(cliente, jikan):
    jikan.responder("/anime", httpx.Response(504))

    resposta = cliente.get("/catalogo/busca", params={"q": "frieren"})

    assert resposta.status_code == 503
    assert "fora do ar" in resposta.json()["detail"]


def test_ver_no_catalogo(cliente, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))

    resposta = cliente.get("/catalogo/52991")

    assert resposta.status_code == 200
    assert "Fantasy" in resposta.json()["generos"]


def test_ver_no_catalogo_anime_que_nao_existe_devolve_404(cliente, jikan):
    jikan.responder("/anime/999999/full", httpx.Response(404))

    assert cliente.get("/catalogo/999999").status_code == 404


def test_adicionar_do_catalogo_preenche_dados_da_jikan(cliente, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))

    resposta = cliente.post("/animes/do-catalogo/52991", params={"status": "assistindo"})

    assert resposta.status_code == 201
    anime = resposta.json()
    assert anime["titulo"] == "Sousou no Frieren"
    assert anime["mal_id"] == 52991
    assert anime["total_episodios"] == 28
    assert anime["imagem_url"].startswith("https://cdn.myanimelist.net/")
    assert anime["status"] == "assistindo"
    assert cliente.get("/animes").json() == [anime]


def test_adicionar_do_catalogo_sem_status_fica_quero_ver(cliente, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))

    assert cliente.post("/animes/do-catalogo/52991").json()["status"] == "quero_ver"


def test_adicionar_do_catalogo_repetido_devolve_409(cliente, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(200, json=frieren_da_jikan()))
    cliente.post("/animes/do-catalogo/52991")

    assert cliente.post("/animes/do-catalogo/52991").status_code == 409


def test_adicionar_do_catalogo_anime_inexistente_devolve_404(cliente, jikan):
    jikan.responder("/anime/999999/full", httpx.Response(404))

    assert cliente.post("/animes/do-catalogo/999999").status_code == 404
    assert cliente.get("/animes").json() == []


def test_adicionar_do_catalogo_com_jikan_fora_do_ar_devolve_503(cliente, jikan):
    jikan.responder("/anime/52991/full", httpx.Response(504))
    jikan.responder("/anime/52991", httpx.Response(504))

    assert cliente.post("/animes/do-catalogo/52991").status_code == 503
    assert cliente.get("/animes").json() == []


def test_adicionar_do_catalogo_anime_com_zero_episodios(cliente, jikan):
    # Anime ainda sem episódios anunciados: a Jikan pode mandar 0 ou null.
    jikan.responder(
        "/anime/60000/full", httpx.Response(200, json={"data": {"mal_id": 60000, "title": "Novo", "episodes": 0}})
    )

    assert cliente.post("/animes/do-catalogo/60000").json()["total_episodios"] is None
