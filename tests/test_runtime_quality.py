from core.runtime import env_bool, env_int, env_str


def test_env_bool_truthy(monkeypatch):
    monkeypatch.setenv("FEATURE_X", "YES")
    assert env_bool("FEATURE_X", False) is True


def test_env_bool_default(monkeypatch):
    monkeypatch.delenv("MISSING_BOOL", raising=False)
    assert env_bool("MISSING_BOOL", True) is True


def test_env_int_valid(monkeypatch):
    monkeypatch.setenv("WORKERS", "4")
    assert env_int("WORKERS", 1) == 4


def test_env_int_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("WORKERS", "abc")
    assert env_int("WORKERS", 2) == 2


def test_env_str_trim(monkeypatch):
    monkeypatch.setenv("MODE", "  prod  ")
    assert env_str("MODE", "dev") == "prod"
