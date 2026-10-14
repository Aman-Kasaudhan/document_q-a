import shutil
from pathlib import Path

import pytest

from src.config import PROJECT_ROOT, Settings
from src.db import connect, init_db
from src.ingest import ingest_directory

RAW_DIR = PROJECT_ROOT / "data" / "raw"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(db_path=tmp_path / "test.db", raw_data_dir=tmp_path / "raw")


@pytest.fixture
def conn(settings):
    c = connect(settings.db_path)
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def docs_dir(tmp_path) -> Path:
    """A fresh, writable copy of the sample documents (including the deliberately bad files)."""
    target = tmp_path / "docs"
    shutil.copytree(RAW_DIR, target)
    return target


@pytest.fixture
def loaded(conn, docs_dir, settings):
    """A database with all sample documents ingested."""
    ingest_directory(conn, docs_dir, settings.chunk_size, settings.chunk_overlap)
    return conn
