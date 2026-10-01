"""Test defaults. CONFIG_FILE is set before any test module imports config."""

import os
import tempfile
from pathlib import Path

import pytest

_TEST_CONFIG = Path(tempfile.gettempdir()) / "anti-spam-pytest-config.yaml"
_TEST_CONFIG.write_text(
    "bot_token: '000000000:test-token'\n"
    "url: 'https://example.invalid/'\n"
    "admins:\n"
    "  - 1\n"
)
os.environ.setdefault("CONFIG_FILE", str(_TEST_CONFIG))


@pytest.fixture(autouse=True)
def _isolate_allowed_groups():
    import config

    before = set(config.allowed_groups.chat_ids)
    yield
    after = set(config.allowed_groups.chat_ids)
    added = after - before
    removed = before - after
    if added:
        config.allowed_groups.remove_chat_ids(added)
    if removed:
        config.allowed_groups.add_chat_ids(removed)


@pytest.fixture(autouse=True)
def _close_client_after_test():
    yield
    import core.mongodb as mongodb

    mongodb.close_db_client()


@pytest.fixture
def database(monkeypatch):
    import core.mongodb as mongodb
    from tests.memory_mongo import MemoryDatabase

    memory = MemoryDatabase()

    async def connect():
        return memory

    monkeypatch.setattr(mongodb, "db_connection", connect)
    return memory
