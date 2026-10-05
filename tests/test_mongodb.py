import asyncio

from app.core.config import settings
from app.storage.mongodb import ensure_indexes


class FakeCollection:
    def __init__(self):
        self.calls = []

    async def create_index(self, spec):
        self.calls.append(spec)


class FakeDatabase:
    def __init__(self):
        self.sources = FakeCollection()
        self.extractions = FakeCollection()


def test_mongodb_settings_have_safe_local_defaults():
    assert settings.mongo_uri.startswith("mongodb://")
    assert settings.mongo_database == "chaos_translator"
    assert settings.mongo_server_selection_timeout_ms > 0


def test_initial_indexes_are_workspace_and_source_scoped():
    database = FakeDatabase()
    asyncio.run(ensure_indexes(database))

    assert database.sources.calls == [[("workspace_id", 1), ("created_at", -1)]]
    assert database.extractions.calls == [
        [("workspace_id", 1), ("created_at", -1)],
        [("source_id", 1)],
    ]
