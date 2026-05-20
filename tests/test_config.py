from app.core.config import Settings


def test_settings_read_database_and_runtime_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ENVIRONMENT", "test")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/test_db"
    assert settings.jwt_secret == "test-secret"
    assert settings.environment == "test"
