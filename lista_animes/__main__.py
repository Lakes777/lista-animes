"""Ponto de entrada: python -m lista_animes."""

import uvicorn


def main() -> None:
    print("API rodando! Documentação em http://127.0.0.1:8000/docs (Ctrl+C para parar).")
    uvicorn.run("lista_animes.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
