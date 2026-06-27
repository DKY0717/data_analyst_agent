"""认证模块测试。"""

import os
import pytest
from unittest.mock import patch

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
