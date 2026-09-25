"""Ponto de entrada: python -m lista_animes."""

import os

import uvicorn

from lista_animes.app import criar_app


def main() -> None:
    # A lista fica em animes.db, na pasta de onde o comando foi rodado.
    # Para usar outro arquivo: LISTA_ANIMES_BANCO=outro.db python -m lista_animes
    caminho_banco = os.environ.get("LISTA_ANIMES_BANCO", "animes.db")
    print(f"Lista salva em: {os.path.abspath(caminho_banco)}")
    print("API rodando! Documentação em http://127.0.0.1:8000/docs (Ctrl+C para parar).")
    uvicorn.run(criar_app(caminho_banco), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
