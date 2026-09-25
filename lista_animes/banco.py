"""Guarda a lista de animes num arquivo SQLite.

Usa o sqlite3 que já vem com o Python, com SQL escrito à mão, sem ORM.
Cada operação abre e fecha a própria conexão. O FastAPI atende pedidos
em threads diferentes, e uma conexão do sqlite3 não pode ser dividida entre elas.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lista_animes.modelos import Anime, AnimeAtualizacao, AnimeNovo, Estatisticas, Status

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


# Migrações: ajustes nos dados salvos por versões antigas, rodados ao abrir o banco.
MIGRACOES = [
    # Antes, imagem_url aceitava qualquer texto; agora só links http(s).
    # Sem isso, um único item antigo inválido derrubava a listagem inteira.
    "UPDATE animes SET imagem_url = NULL "
    "WHERE imagem_url NOT LIKE 'http://_%' AND imagem_url NOT LIKE 'https://_%'",
]


class AnimeRepetido(Exception):
    """O anime (mesmo mal_id) já está na lista."""


class Banco:
    def __init__(self, caminho: Path | str) -> None:
        self.caminho = Path(caminho)
        with self._conectar() as conexao:
            conexao.execute(CRIAR_TABELA)
            for migracao in MIGRACOES:
                conexao.execute(migracao)

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

    def listar(self, status: Status | None = None, busca: str | None = None) -> list[Anime]:
        # Monta o WHERE só com os filtros que foram pedidos.
        condicoes, valores = [], []
        if status is not None:
            condicoes.append("status = ?")
            valores.append(status.value)
        if busca and busca.strip():
            # No LIKE, % e _ são curingas. Escapamos para que "100%" busque o texto "100%".
            termo = busca.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            condicoes.append("titulo LIKE ? ESCAPE '\\'")
            valores.append(f"%{termo}%")
        where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
        with self._conectar() as conexao:
            linhas = conexao.execute(f"SELECT * FROM animes {where} ORDER BY id", valores).fetchall()
        return [Anime(**linha) for linha in linhas]

    def estatisticas(self) -> Estatisticas:
        with self._conectar() as conexao:
            contagem = dict(
                conexao.execute("SELECT status, COUNT(*) FROM animes GROUP BY status").fetchall()
            )
            # COUNT(nota) conta só as linhas que têm nota (ignora NULL).
            episodios, com_nota, soma_notas = conexao.execute(
                "SELECT COALESCE(SUM(episodios_vistos), 0), COUNT(nota), COALESCE(SUM(nota), 0) "
                "FROM animes"
            ).fetchone()
        nota_media = None
        if com_nota:
            # Decimal com ROUND_HALF_UP: 8.25 vira 8.3, como aprendemos na escola.
            media = (Decimal(soma_notas) / com_nota).quantize(Decimal("0.1"), ROUND_HALF_UP)
            nota_media = float(media)
        return Estatisticas(
            total=sum(contagem.values()),
            por_status={s: contagem.get(s.value, 0) for s in Status},
            episodios_assistidos=episodios,
            nota_media=nota_media,
        )

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
