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
