from pathlib import Path


def test_alembic_env_imports_heartbeat_model() -> None:
    env_path = Path(__file__).resolve().parents[2] / "src" / "alembic" / "env.py"
    source = env_path.read_text(encoding="utf-8")
    assert "import flow44.db.heartbeat" in source
