"""Ponto de entrada: python -m lista_animes.

Configuração por variáveis de ambiente (todas opcionais):
    LISTA_ANIMES_BANCO  arquivo do banco (padrão: animes.db, na pasta atual)
    LISTA_ANIMES_DEMO   "1" liga o modo demonstração (lista de exemplo + limite)
    HOST e PORT         endereço e porta (padrão: 127.0.0.1 e 8000; o Render define PORT)
"""

import os

import uvicorn

from lista_animes.app import criar_app


def main() -> None:
    caminho_banco = os.environ.get("LISTA_ANIMES_BANCO", "animes.db")
    demo = os.environ.get("LISTA_ANIMES_DEMO", "").lower() in {"1", "true", "sim"}
    host = os.environ.get("HOST", "127.0.0.1")
    porta = int(os.environ.get("PORT", "8000"))

    print(f"Lista salva em: {os.path.abspath(caminho_banco)}")
    if demo:
        print("Modo demonstração ligado: lista de exemplo e limite de animes.")
    print(f"API rodando! Documentação em http://{host}:{porta}/docs (Ctrl+C para parar).")
    uvicorn.run(criar_app(caminho_banco, demo=demo), host=host, port=porta)


if __name__ == "__main__":
    main()
