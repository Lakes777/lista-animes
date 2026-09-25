import pytest
from fastapi.testclient import TestClient

from lista_animes.app import criar_app


@pytest.fixture
def cliente(tmp_path):
    # O TestClient chama a API direto na memória, sem abrir porta nem usar internet.
    # Cada teste ganha uma API com banco novo numa pasta temporária.
    return TestClient(criar_app(tmp_path / "teste.db"))
