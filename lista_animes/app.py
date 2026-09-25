"""Cria a aplicação FastAPI e registra as rotas."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lista_animes.banco import Banco
from lista_animes.catalogo import Catalogo
from lista_animes.rotas import roteador, roteador_catalogo

PASTA_STATIC = Path(__file__).parent / "static"


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

    # O front (HTML, CSS e JS) é servido pela própria API: um só servidor para tudo.
    app.mount("/static", StaticFiles(directory=PASTA_STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        return FileResponse(PASTA_STATIC / "index.html")

    @app.get("/saude", tags=["sistema"])
    def saude() -> dict[str, str]:
        """Responde se a API está no ar (útil para monitoramento)."""
        return {"status": "ok"}

    return app
