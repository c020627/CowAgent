"""Mirror test_vector_row_corruption.py for the non-retrieval path.

vector_backend.search (cd73478e) isolates a malformed / non-finite embedding so
a single bad row cannot hide healthy matches. The same corrupted BLOB must not
crash the list / export / FTS5-rebuild / get-by-id paths, which all funnel
through ``MemoryStorage._row_to_chunk``. Today that method decodes the embedding
with no guard, so one damaged row raises ``ValueError`` / ``struct.error`` /
``JSONDecodeError`` and takes the whole read down.
"""

import json
import sqlite3
import struct

import pytest

from agent.memory import storage as storage_module
from agent.memory.storage import MemoryStorage


def _broken_row(damaged):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE chunks ("
        "id TEXT, user_id TEXT, scope TEXT, source TEXT, path TEXT, "
        "start_line INTEGER, end_line INTEGER, text TEXT, embedding BLOB, "
        "hash TEXT, metadata TEXT)"
    )
    conn.execute(
        "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("broken", "u", "shared", "memory", "broken.md", 1, 1, "t",
         damaged, "h", None),
    )
    return conn.execute("SELECT * FROM chunks WHERE id='broken'").fetchone()


@pytest.mark.parametrize("numpy_enabled", [False, True])
@pytest.mark.parametrize("damaged", [
    b"x",                 # byte length is not a multiple of 4
    "not-valid-json",     # legacy JSON column that no longer parses
])
def test_row_to_chunk_isolates_malformed_embedding(numpy_enabled, damaged):
    if numpy_enabled and storage_module._HAS_NUMPY is False:
        pytest.skip("NumPy is optional")
    original = storage_module._HAS_NUMPY
    storage_module._HAS_NUMPY = numpy_enabled
    try:
        storage = object.__new__(MemoryStorage)
        chunk = storage._row_to_chunk(_broken_row(damaged))
    finally:
        storage_module._HAS_NUMPY = original
    assert chunk.id == "broken"
    assert chunk.embedding is None


@pytest.mark.parametrize("numpy_enabled", [False, True])
def test_row_to_chunk_isolates_nonfinite_embedding(numpy_enabled):
    if numpy_enabled and storage_module._HAS_NUMPY is False:
        pytest.skip("NumPy is optional")
    original = storage_module._HAS_NUMPY
    storage_module._HAS_NUMPY = numpy_enabled
    try:
        raw = struct.pack("<2f", float("nan"), 1.0)
        storage = object.__new__(MemoryStorage)
        chunk = storage._row_to_chunk(_broken_row(raw))
    finally:
        storage_module._HAS_NUMPY = original
    assert chunk.id == "broken"
    assert chunk.embedding is None


@pytest.mark.parametrize("numpy_enabled", [False, True])
def test_row_to_chunk_keeps_valid_embedding(numpy_enabled):
    if numpy_enabled and storage_module._HAS_NUMPY is False:
        pytest.skip("NumPy is optional")
    original = storage_module._HAS_NUMPY
    storage_module._HAS_NUMPY = numpy_enabled
    try:
        if numpy_enabled:
            payload = struct.pack("<2f", 1.0, 0.0)
        else:
            payload = json.dumps([1.0, 0.0])
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE chunks ("
            "id TEXT, user_id TEXT, scope TEXT, source TEXT, path TEXT, "
            "start_line INTEGER, end_line INTEGER, text TEXT, embedding BLOB, "
            "hash TEXT, metadata TEXT)"
        )
        conn.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("ok", "u", "shared", "memory", "ok.md", 1, 1, "t",
             payload, "h", None),
        )
        row = conn.execute("SELECT * FROM chunks WHERE id='ok'").fetchone()
        storage = object.__new__(MemoryStorage)
        chunk = storage._row_to_chunk(row)
    finally:
        storage_module._HAS_NUMPY = original
    assert chunk.id == "ok"
    assert chunk.embedding is not None
