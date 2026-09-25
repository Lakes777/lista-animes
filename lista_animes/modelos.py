"""Formatos dos dados: o que a API recebe e o que ela devolve.

O Pydantic valida tudo sozinho. Se chegar uma nota 11 ou um título vazio,
a API recusa antes de qualquer coisa ser salva no banco.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(str, Enum):
    QUERO_VER = "quero_ver"
    ASSISTINDO = "assistindo"
    CONCLUIDO = "concluido"
    ABANDONADO = "abandonado"


class AnimeNovo(BaseModel):
    """Dados para adicionar um anime à lista."""

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=1, max_length=200)
    mal_id: int | None = Field(default=None, gt=0, description="ID do anime no MyAnimeList")
    total_episodios: int | None = Field(default=None, ge=1)
    imagem_url: str | None = None
    status: Status = Status.QUERO_VER
    episodios_vistos: int = Field(default=0, ge=0)
    nota: int | None = Field(default=None, ge=1, le=10, description="De 1 a 10, como no MyAnimeList")

    @model_validator(mode="after")
    def vistos_cabem_no_total(self) -> "AnimeNovo":
        if self.total_episodios is not None and self.episodios_vistos > self.total_episodios:
            raise ValueError(
                f"episodios_vistos ({self.episodios_vistos}) passa do total "
                f"de episódios ({self.total_episodios})"
            )
        return self


class AnimeAtualizacao(BaseModel):
    """Campos que podem mudar depois. Só os que forem enviados são alterados."""

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    total_episodios: int | None = Field(default=None, ge=1)
    imagem_url: str | None = None
    status: Status | None = None
    episodios_vistos: int | None = Field(default=None, ge=0)
    nota: int | None = Field(default=None, ge=1, le=10)


class Anime(AnimeNovo):
    """Um anime já salvo na lista."""

    id: int
    criado_em: datetime
