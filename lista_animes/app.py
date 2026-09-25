"""Cria a aplicação FastAPI e registra as rotas."""

from fastapi import FastAPI


def criar_app() -> FastAPI:
    app = FastAPI(
        title="Lista de Animes",
        description="Sua lista de animes: o que quer ver, o que está vendo e o que já viu.",
        version="0.1.0",
    )

    @app.get("/saude", tags=["sistema"])
    def saude() -> dict[str, str]:
        """Responde se a API está no ar (útil para monitoramento)."""
        return {"status": "ok"}

    return app


app = criar_app()
