"""认证模块测试。"""

import os
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import (
    AuthUser,
    _hash_key,
    create_jwt_token,
    is_auth_enabled,
    verify_api_key,
    verify_jwt_token,
)


class TestJWTToken:
    def test_create_and_verify_token(self):
        with patch("app.security.auth.JWT_SECRET", "test-secret-key"):
            token_data = create_jwt_token("test_user", ["user"])
            assert "access_token" in token_data
            assert token_data["token_type"] == "bearer"

            user = verify_jwt_token(token_data["access_token"])
            assert user.user_id == "test_user"
            assert user.auth_method == "jwt"
            assert "user" in user.roles

    def test_expired_token_raises_error(self):
        with patch("app.security.auth.JWT_SECRET", "test-secret-key"):
            import jwt
            payload = {"sub": "test", "roles": ["user"], "iat": 0, "exp": 0}
            expired_token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
            with pytest.raises(Exception):
                verify_jwt_token(expired_token)

    def test_invalid_token_raises_error(self):
        with patch("app.security.auth.JWT_SECRET", "test-secret-key"):
            with pytest.raises(Exception):
                verify_jwt_token("invalid.token.here")


class TestAPIKey:
    def test_verify_valid_key(self):
        test_key = "sk-test-12345678"
        with patch("app.security.auth.API_KEYS_RAW", test_key):
            from app.security.auth import reload_api_keys, _api_keys
            import app.security.auth as auth_mod
            auth_mod._api_keys = {}
            user = verify_api_key(test_key)
            assert user.auth_method == "api_key"
            assert "sk-test-" in user.user_id

    def test_verify_invalid_key_raises_error(self):
        with patch("app.security.auth.API_KEYS_RAW", "sk-valid-key"):
            from app.security.auth import reload_api_keys
            import app.security.auth as auth_mod
            auth_mod._api_keys = {}
            with pytest.raises(Exception):
                verify_api_key("sk-invalid-key")


class TestAuthEnabled:
    def test_no_config_means_disabled(self):
        with patch("app.security.auth.JWT_SECRET", ""), \
             patch("app.security.auth.API_KEYS_RAW", ""):
            import app.security.auth as auth_mod
            auth_mod._api_keys = {}
            assert is_auth_enabled() is False

    def test_jwt_secret_enables_auth(self):
        with patch("app.security.auth.JWT_SECRET", "some-secret"):
            assert is_auth_enabled() is True

    def test_api_keys_enable_auth(self):
        with patch("app.security.auth.API_KEYS_RAW", "sk-key1,sk-key2"):
            import app.security.auth as auth_mod
            auth_mod._api_keys = {}
            assert is_auth_enabled() is True


class TestHashKey:
    def test_hash_consistency(self):
        assert _hash_key("test") == _hash_key("test")
        assert _hash_key("test") != _hash_key("other")


class TestDemoLoginEndpoint:
    def test_demo_login_disabled_by_default(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", False):
            response = client.post("/api/auth/demo-login", json={"role": "analyst"})

        assert response.status_code == 404

    def test_demo_login_requires_jwt_secret_when_enabled(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", True), \
             patch("app.security.auth.JWT_SECRET", ""):
            response = client.post("/api/auth/demo-login", json={"role": "analyst"})

        assert response.status_code == 503
        assert "JWT_SECRET" in response.json()["detail"]
        assert "secret" not in response.text.lower().replace("jwt_secret", "")

    @pytest.mark.parametrize(
        ("role", "expected_user_id"),
        [
            ("admin", "demo:admin"),
            ("analyst", "demo:analyst"),
            ("support", "demo:support"),
        ],
    )
    def test_demo_login_returns_token_for_allowed_roles(self, role, expected_user_id):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", True), \
             patch("app.security.auth.JWT_SECRET", "test-secret"):
            response = client.post("/api/auth/demo-login", json={"role": role})

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["token_type"] == "bearer"
        assert payload["access_token"]
        assert payload["user"] == {
            "user_id": expected_user_id,
            "auth_method": "jwt",
            "roles": [role],
        }

    def test_demo_login_rejects_invalid_role(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", True), \
             patch("app.security.auth.JWT_SECRET", "test-secret"):
            response = client.post("/api/auth/demo-login", json={"role": "guest"})

        assert response.status_code == 400
        assert "不支持的演示角色" in response.json()["detail"]

    def test_demo_login_token_can_load_current_user(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", True), \
             patch("app.security.auth.JWT_SECRET", "test-secret"):
            login_response = client.post("/api/auth/demo-login", json={"role": "support"})
            token = login_response.json()["data"]["access_token"]
            me_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert me_response.status_code == 200
        assert me_response.json() == {
            "user_id": "demo:support",
            "auth_method": "jwt",
            "roles": ["support"],
        }

    def test_demo_login_response_does_not_expose_jwt_secret(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_DEMO_ENABLED", True), \
             patch("app.security.auth.JWT_SECRET", "super-private-demo-secret"):
            response = client.post("/api/auth/demo-login", json={"role": "admin"})

        assert response.status_code == 200
        assert "super-private-demo-secret" not in response.text


class TestPasswordLoginEndpoint:
    def test_password_login_disabled_by_default(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_PASSWORD_LOGIN_ENABLED", False):
            response = client.post(
                "/api/auth/login",
                params={"username": "admin", "password": "admin123"},
            )

        assert response.status_code == 404

    def test_password_login_uses_configured_credentials_not_hardcoded_defaults(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_PASSWORD_LOGIN_ENABLED", True), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_USERNAME", "owner"), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_PASSWORD", "private-pass"), \
             patch("app.security.auth.JWT_SECRET", "test-secret"):
            response = client.post(
                "/api/auth/login",
                params={"username": "admin", "password": "admin123"},
            )

        assert response.status_code == 401

    def test_password_login_requires_jwt_secret_when_enabled(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_PASSWORD_LOGIN_ENABLED", True), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_USERNAME", "owner"), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_PASSWORD", "private-pass"), \
             patch("app.security.auth.JWT_SECRET", ""):
            response = client.post(
                "/api/auth/login",
                params={"username": "owner", "password": "private-pass"},
            )

        assert response.status_code == 503
        assert "JWT_SECRET" in response.json()["detail"]

    def test_password_login_returns_token_for_configured_admin(self):
        client = TestClient(app)

        with patch("app.api.auth_router.settings.AUTH_PASSWORD_LOGIN_ENABLED", True), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_USERNAME", "owner"), \
             patch("app.api.auth_router.settings.AUTH_ADMIN_PASSWORD", "private-pass"), \
             patch("app.security.auth.JWT_SECRET", "test-secret"):
            response = client.post(
                "/api/auth/login",
                params={"username": "owner", "password": "private-pass"},
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["token_type"] == "bearer"
        assert payload["access_token"]
        assert "private-pass" not in response.text
