"""Cria a aplicação FastAPI e registra as rotas."""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lista_animes.banco import Banco
from lista_animes.catalogo import Catalogo
from lista_animes.modelos import AnimeNovo
from lista_animes.rotas import roteador, roteador_catalogo

PASTA_STATIC = Path(__file__).parent / "static"
ARQUIVO_EXEMPLOS = Path(__file__).parent / "exemplos.json"

# Na demonstração online, qualquer visitante pode adicionar animes.
# O limite impede que alguém encha o servidor.
LIMITE_DEMO = 100
LIMITE_COMENTARIOS_DEMO = 500


def carregar_exemplos(banco: Banco) -> None:
    """Preenche um banco vazio com a lista de exemplo (usada na demonstração)."""
    if banco.listar():
        return
    for dados in json.loads(ARQUIVO_EXEMPLOS.read_text(encoding="utf-8")):
        banco.adicionar(AnimeNovo(**dados))


def criar_app(
    caminho_banco: Path | str, catalogo: Catalogo | None = None, demo: bool = False
) -> FastAPI:
    app = FastAPI(
        title="Lista de Animes",
        description="Sua lista de animes: o que quer ver, o que está vendo e o que já viu.",
        version="0.1.0",
    )
    app.state.banco = Banco(caminho_banco)
    app.state.demo = demo
    app.state.limite_animes = LIMITE_DEMO if demo else None
    app.state.limite_comentarios = LIMITE_COMENTARIOS_DEMO if demo else None
    if demo:
        carregar_exemplos(app.state.banco)
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

    @app.get("/info", tags=["sistema"])
    def info() -> dict[str, bool | int | None]:
        """Diz se a API está em modo demonstração (o front mostra um aviso)."""
        return {"demo": app.state.demo, "limite_animes": app.state.limite_animes}

    return app
