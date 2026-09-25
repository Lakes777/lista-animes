"""Rotas de /animes: criar, listar, ver, editar e apagar (CRUD)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError

from lista_animes.banco import AnimeRepetido, Banco
from lista_animes.modelos import Anime, AnimeAtualizacao, AnimeNovo

roteador = APIRouter(prefix="/animes", tags=["animes"])


def pegar_banco(request: Request) -> Banco:
    # O banco é guardado no app ao criá-lo (app.state.banco). O Depends entrega
    # ele para cada rota, e os testes podem trocar por um banco temporário.
    return request.app.state.banco


def nao_encontrado(anime_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Anime {anime_id} não está na lista")


@roteador.post("", status_code=status.HTTP_201_CREATED)
def adicionar(novo: AnimeNovo, banco: Banco = Depends(pegar_banco)) -> Anime:
    """Adiciona um anime à lista."""
    try:
        return banco.adicionar(novo)
    except AnimeRepetido as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from erro


@roteador.get("")
def listar(banco: Banco = Depends(pegar_banco)) -> list[Anime]:
    """Lista todos os animes, na ordem em que foram adicionados."""
    return banco.listar()


@roteador.get("/{anime_id}", responses={404: {"description": "Anime não encontrado"}})
def ver(anime_id: int, banco: Banco = Depends(pegar_banco)) -> Anime:
    """Mostra um anime da lista."""
    anime = banco.buscar(anime_id)
    if anime is None:
        raise nao_encontrado(anime_id)
    return anime


@roteador.patch("/{anime_id}", responses={404: {"description": "Anime não encontrado"}})
def editar(
    anime_id: int, mudancas: AnimeAtualizacao, banco: Banco = Depends(pegar_banco)
) -> Anime:
    """Muda só os campos enviados (ex.: status e episódios vistos)."""
    try:
        anime = banco.atualizar(anime_id, mudancas)
    except ValidationError as erro:
        # A combinação final não é válida (ex.: 30 episódios vistos de um total de 28).
        detalhes = erro.errors(include_url=False, include_context=False, include_input=False)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detalhes) from erro
    if anime is None:
        raise nao_encontrado(anime_id)
    return anime


@roteador.delete(
    "/{anime_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Anime não encontrado"}},
)
def apagar(anime_id: int, banco: Banco = Depends(pegar_banco)) -> Response:
    """Tira um anime da lista."""
    if not banco.remover(anime_id):
        raise nao_encontrado(anime_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
