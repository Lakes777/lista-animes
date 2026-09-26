"""Catálogo de animes da Jikan (https://jikan.moe), com dados do MyAnimeList.

A Jikan é gratuita e não pede chave, mas tem limites: cerca de 3 consultas
por segundo. A busca por nome consulta o MyAnimeList na hora e às vezes falha
com erro 504, quando o MyAnimeList está fora do ar. Por isso, toda falha vira
CatalogoIndisponivel, com uma mensagem que dá para mostrar a quem usa a API.
"""

from datetime import date

import httpx

from lista_animes.modelos import AnimeCatalogo, Relacionado

URL_JIKAN = "https://api.jikan.moe/v4"


# No MyAnimeList, cada temporada é um anime separado, ligado aos outros por "relações".
# Só Prequel (a anterior) e Sequel (a seguinte) contam como temporadas; spin-offs,
# resumos e histórias paralelas ficam de fora.
RELACOES = {"Prequel": "anterior", "Sequel": "seguinte"}


class CatalogoIndisponivel(Exception):
    """A Jikan não respondeu direito. A mensagem explica o motivo."""


def ler_estreia(dados: dict) -> date | None:
    # A Jikan manda "2023-09-29T00:00:00+00:00"; só a data interessa.
    inicio = (dados.get("aired") or {}).get("from")
    return date.fromisoformat(inicio[:10]) if inicio else None


def ler_relacionados(dados: dict) -> list[Relacionado] | None:
    if "relations" not in dados:
        return None  # a resposta não diz nada sobre temporadas (não é o mesmo que "não tem")
    relacionados = []
    for grupo in dados.get("relations") or []:
        relacao = RELACOES.get(grupo["relation"])
        if relacao is None:
            continue
        for item in grupo["entry"]:
            if item["type"] == "anime":  # a relação também pode apontar para um mangá
                relacionados.append(
                    Relacionado(mal_id=item["mal_id"], titulo=item["name"], relacao=relacao)
                )
    return relacionados


def ler_anime(dados: dict) -> AnimeCatalogo:
    """Converte um anime no formato da Jikan (em inglês) para o nosso formato."""
    try:
        return AnimeCatalogo(
            mal_id=dados["mal_id"],
            titulo=dados["title"],
            titulo_ingles=dados.get("title_english"),
            total_episodios=dados.get("episodes"),
            imagem_url=dados.get("images", {}).get("jpg", {}).get("image_url"),
            ano=dados.get("year"),
            nota_mal=dados.get("score"),
            tipo=dados.get("type"),
            sinopse=dados.get("synopsis"),
            generos=[genero["name"] for genero in dados.get("genres", [])],
            estreia=ler_estreia(dados),
            relacionados=ler_relacionados(dados),
        )
    except (KeyError, TypeError, ValueError) as erro:
        raise CatalogoIndisponivel("A Jikan respondeu num formato inesperado.") from erro


class Catalogo:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # Nos testes, o transport é um httpx.MockTransport: nenhuma consulta vai à internet.
        self._transport = transport

    def _get(self, caminho: str, params: dict | None = None) -> httpx.Response:
        try:
            with httpx.Client(base_url=URL_JIKAN, timeout=10, transport=self._transport) as cliente:
                resposta = cliente.get(caminho, params=params)
        except httpx.TimeoutException as erro:
            raise CatalogoIndisponivel("A Jikan demorou demais para responder. Tente de novo.") from erro
        except httpx.HTTPError as erro:
            raise CatalogoIndisponivel("Não consegui acessar a Jikan. Confira a internet.") from erro

        if resposta.status_code == 429:
            raise CatalogoIndisponivel("Muitas consultas seguidas à Jikan. Espere alguns segundos.")
        if resposta.status_code >= 500:
            raise CatalogoIndisponivel(
                "O MyAnimeList está fora do ar para a Jikan agora. Tente mais tarde."
            )
        return resposta

    def buscar(self, termo: str, limite: int = 10) -> list[AnimeCatalogo]:
        """Procura animes pelo nome. O sfw esconde conteúdo adulto dos resultados."""
        resposta = self._get("/anime", params={"q": termo, "limit": limite, "sfw": "true"})
        if resposta.status_code != 200:
            raise CatalogoIndisponivel(f"A Jikan recusou a busca (erro {resposta.status_code}).")
        try:
            itens = resposta.json()["data"]
        except (ValueError, KeyError) as erro:
            raise CatalogoIndisponivel("A Jikan respondeu num formato inesperado.") from erro

        # A Jikan às vezes repete o mesmo anime na busca; mostramos cada um só uma vez.
        animes, vistos = [], set()
        for item in itens:
            anime = ler_anime(item)
            if anime.mal_id not in vistos:
                vistos.add(anime.mal_id)
                animes.append(anime)
        return animes

    def detalhes(self, mal_id: int) -> AnimeCatalogo | None:
        """Busca um anime pelo ID do MyAnimeList. Devolve None se ele não existir.

        Tenta a versão /full, que já traz as relações (temporada anterior e seguinte).
        Com o MyAnimeList fora do ar, a Jikan só responde o /full se tiver uma cópia
        guardada; já o /anime/{id} simples ela quase sempre tem. Então, se o /full
        falhar, usa o simples: o anime vem sem as relações (relacionados = None).
        """
        try:
            resposta = self._get(f"/anime/{mal_id}/full")
        except CatalogoIndisponivel:
            resposta = self._get(f"/anime/{mal_id}")
        if resposta.status_code == 404:
            return None
        if resposta.status_code != 200:
            raise CatalogoIndisponivel(f"A Jikan recusou a consulta (erro {resposta.status_code}).")
        try:
            return ler_anime(resposta.json()["data"])
        except (ValueError, KeyError) as erro:
            raise CatalogoIndisponivel("A Jikan respondeu num formato inesperado.") from erro
