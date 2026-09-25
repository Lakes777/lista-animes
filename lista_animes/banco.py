"""Guarda a lista de animes num arquivo SQLite.

Usa o sqlite3 que já vem com o Python, com SQL escrito à mão, sem ORM.
Cada operação abre e fecha a própria conexão. O FastAPI atende pedidos
em threads diferentes, e uma conexão do sqlite3 não pode ser dividida entre elas.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lista_animes.modelos import Anime, AnimeAtualizacao, AnimeNovo

CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS animes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo           TEXT    NOT NULL,
    mal_id           INTEGER UNIQUE,
    total_episodios  INTEGER,
    imagem_url       TEXT,
    status           TEXT    NOT NULL,
    episodios_vistos INTEGER NOT NULL DEFAULT 0,
    nota             INTEGER,
    criado_em        TEXT    NOT NULL
)
"""


class AnimeRepetido(Exception):
    """O anime (mesmo mal_id) já está na lista."""


class Banco:
    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)
        with self._conectar() as conexao:
            conexao.execute(CRIAR_TABELA)

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.caminho)) as conexao:
            conexao.row_factory = sqlite3.Row  # linhas acessíveis por nome: linha["titulo"]
            with conexao:  # confirma (commit) no final, ou desfaz tudo se der erro
                yield conexao

    def adicionar(self, novo: AnimeNovo) -> Anime:
        dados = novo.model_dump(mode="json")
        dados["criado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        colunas = ", ".join(dados)
        marcadores = ", ".join(f":{coluna}" for coluna in dados)
        try:
            with self._conectar() as conexao:
                # Os valores vão por marcadores (:titulo), nunca colados no texto do SQL.
                # Isso evita SQL injection.
                cursor = conexao.execute(
                    f"INSERT INTO animes ({colunas}) VALUES ({marcadores})", dados
                )
        except sqlite3.IntegrityError as erro:
            raise AnimeRepetido(f"O anime com mal_id {novo.mal_id} já está na lista") from erro
        return Anime(id=cursor.lastrowid, **dados)

    def listar(self) -> list[Anime]:
        with self._conectar() as conexao:
            linhas = conexao.execute("SELECT * FROM animes ORDER BY id").fetchall()
        return [Anime(**linha) for linha in linhas]

    def buscar(self, anime_id: int) -> Anime | None:
        with self._conectar() as conexao:
            linha = conexao.execute("SELECT * FROM animes WHERE id = ?", (anime_id,)).fetchone()
        return Anime(**linha) if linha else None

    def atualizar(self, anime_id: int, mudancas: AnimeAtualizacao) -> Anime | None:
        atual = self.buscar(anime_id)
        if atual is None:
            return None
        # Junta o que já existe com o que mudou e valida o resultado inteiro de novo.
        # Assim a regra "vistos <= total" também vale para atualizações parciais.
        alterados = mudancas.model_dump(exclude_unset=True)
        atualizado = Anime.model_validate({**atual.model_dump(), **alterados})
        if alterados:
            dados = atualizado.model_dump(mode="json", include=set(alterados))
            atribuicoes = ", ".join(f"{campo} = :{campo}" for campo in dados)
            with self._conectar() as conexao:
                conexao.execute(
                    f"UPDATE animes SET {atribuicoes} WHERE id = :id", {**dados, "id": anime_id}
                )
        return atualizado

    def remover(self, anime_id: int) -> bool:
        with self._conectar() as conexao:
            cursor = conexao.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
        return cursor.rowcount > 0
