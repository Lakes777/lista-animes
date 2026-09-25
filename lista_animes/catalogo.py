"""Catálogo de animes da Jikan (https://jikan.moe), com dados do MyAnimeList.

A Jikan é gratuita e não pede chave, mas tem limites: cerca de 3 consultas
por segundo. A busca por nome consulta o MyAnimeList na hora e às vezes falha
com erro 504, quando o MyAnimeList está fora do ar. Por isso, toda falha vira
CatalogoIndisponivel, com uma mensagem que dá para mostrar a quem usa a API.
"""

import httpx

from lista_animes.modelos import AnimeCatalogo

URL_JIKAN = "https://api.jikan.moe/v4"


class CatalogoIndisponivel(Exception):
    """A Jikan não respondeu direito. A mensagem explica o motivo."""


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
        """Busca um anime pelo ID do MyAnimeList. Devolve None se ele não existir."""
        resposta = self._get(f"/anime/{mal_id}")
        if resposta.status_code == 404:
            return None
        if resposta.status_code != 200:
            raise CatalogoIndisponivel(f"A Jikan recusou a consulta (erro {resposta.status_code}).")
        try:
            return ler_anime(resposta.json()["data"])
        except (ValueError, KeyError) as erro:
            raise CatalogoIndisponivel("A Jikan respondeu num formato inesperado.") from erro
