# Lista de Animes

API REST em Python com FastAPI para organizar sua lista de animes: o que você quer ver,
o que está vendo e o que já viu. Os dados dos animes vêm da [Jikan](https://jikan.moe),
uma API gratuita com o catálogo do MyAnimeList.

> 🚧 Em construção.

## Como rodar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m lista_animes
```

Depois abra http://127.0.0.1:8000/docs para ver e testar a API no navegador.

## Testes

```bash
pytest
```
