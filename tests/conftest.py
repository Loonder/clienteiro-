from dataclasses import dataclass, field

import pytest
from flask import Flask


@dataclass
class MockCursor:
    fetchone_queue: list = field(default_factory=list)
    fetchall_queue: list = field(default_factory=list)
    executed: list = field(default_factory=list)

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        if self.fetchone_queue:
            return self.fetchone_queue.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_queue:
            return self.fetchall_queue.pop(0)
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@dataclass
class MockConn:
    cursor_obj: MockCursor
    committed: bool = False
    closed: bool = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture
def flask_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    return app
