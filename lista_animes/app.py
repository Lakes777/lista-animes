"""Cria a aplicação FastAPI e registra as rotas."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from lista_animes.banco import Banco
from lista_animes.catalogo import Catalogo
from lista_animes.rotas import roteador, roteador_catalogo


def criar_app(caminho_banco: Path | str, catalogo: Catalogo | None = None) -> FastAPI:
    app = FastAPI(
        title="Lista de Animes",
        description="Sua lista de animes: o que quer ver, o que está vendo e o que já viu.",
        version="0.1.0",
    )
    app.state.banco = Banco(caminho_banco)
    # Os testes passam um catálogo falso; o servidor de verdade usa a Jikan.
    app.state.catalogo = catalogo or Catalogo()
    app.include_router(roteador)
    app.include_router(roteador_catalogo)

    @app.get("/", include_in_schema=False)
    def inicio() -> RedirectResponse:
        # Por enquanto a página inicial leva à documentação; depois vira o front.
        return RedirectResponse("/docs")

    @app.get("/saude", tags=["sistema"])
    def saude() -> dict[str, str]:
        """Responde se a API está no ar (útil para monitoramento)."""
        return {"status": "ok"}

    return app
