"""Rotas de /animes: criar, listar (com filtros), ver, editar e apagar, e estatísticas."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError

from lista_animes.banco import AnimeRepetido, Banco
from lista_animes.modelos import Anime, AnimeAtualizacao, AnimeNovo, Estatisticas, Status

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
def listar(
    status_anime: Status | None = Query(
        default=None, alias="status", description="Mostra só os animes com esse status"
    ),
    busca: str | None = Query(
        default=None, max_length=100, description="Parte do título (maiúsculas ou minúsculas)"
    ),
    banco: Banco = Depends(pegar_banco),
) -> list[Anime]:
    """Lista os animes, na ordem em que foram adicionados. Os filtros são opcionais."""
    return banco.listar(status=status_anime, busca=busca)


# Esta rota precisa vir antes de /{anime_id}: as rotas são testadas na ordem,
# e "estatisticas" seria lido como um id (e recusado por não ser número).
@roteador.get("/estatisticas")
def estatisticas(banco: Banco = Depends(pegar_banco)) -> Estatisticas:
    """Resumo da lista: quantos animes por status, episódios assistidos e nota média."""
    return banco.estatisticas()


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
