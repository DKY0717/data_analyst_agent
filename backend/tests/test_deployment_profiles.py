"""Demo / secure Compose 部署边界契约测试。"""

from pathlib import Path

import yaml

from app.security import auth


ROOT = Path(__file__).resolve().parents[2]


def environment_entries(file_name: str) -> set[str]:
    payload = yaml.safe_load((ROOT / file_name).read_text(encoding="utf-8"))
    return set(payload["services"]["backend"]["environment"])


def test_base_compose_is_explicit_demo_profile_with_sandbox():
    environment = environment_entries("docker-compose.yml")

    assert "DEPLOYMENT_PROFILE=demo" in environment
    assert "SANDBOX_MODE=true" in environment


def test_secure_compose_requires_auth_cors_llm_and_disables_demo_login():
    environment = environment_entries("docker-compose.secure.yml")
    joined = "\n".join(environment)

    assert "DEPLOYMENT_PROFILE=secure" in environment
    assert "SANDBOX_MODE=true" in environment
    assert "AUTH_DEMO_ENABLED=false" in environment
    assert "AUTH_PASSWORD_LOGIN_ENABLED=false" in environment
    for variable in [
        "JWT_SECRET",
        "CORS_ALLOW_ORIGINS",
        "QWEN_API_KEY",
        "QWEN_API_URL",
        "QWEN_MODEL",
    ]:
        assert f"${{{variable}:?" in joined


def test_env_example_documents_profile_boundary():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "DEPLOYMENT_PROFILE=demo" in env_example
    assert "secure 会在 readiness 强制认证" in env_example


def test_secure_auth_rejects_short_credentials(monkeypatch):
    monkeypatch.setattr(auth, "JWT_SECRET", "short")
    monkeypatch.setattr(auth, "API_KEYS_RAW", "tiny-key")

    assert auth.has_secure_auth_configuration() is False


def test_secure_auth_accepts_long_jwt_or_api_key(monkeypatch):
    monkeypatch.setattr(auth, "JWT_SECRET", "j" * 32)
    monkeypatch.setattr(auth, "API_KEYS_RAW", "")
    assert auth.has_secure_auth_configuration() is True

    monkeypatch.setattr(auth, "JWT_SECRET", "")
    monkeypatch.setattr(auth, "API_KEYS_RAW", "k" * 24)
    assert auth.has_secure_auth_configuration() is True
