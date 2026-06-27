"""速率限制模块测试。"""

import pytest
from unittest.mock import patch

from app.security.rate_limit import limiter, setup_rate_limit, _get_client_id, RATE_LIMIT_QUERY, RATE_LIMIT_DEFAULT
from fastapi import Request


class TestRateLimitConfig:
    def test_limiter_instance_exists(self):
        assert limiter is not None

    def test_default_rate_limit_is_set(self):
        assert RATE_LIMIT_DEFAULT == "30/minute"

    def test_query_rate_limit_is_stricter(self):
        assert RATE_LIMIT_QUERY == "10/minute"

    def test_get_client_id_with_api_key(self):
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat/query",
            "headers": [(b"x-api-key", b"sk-test-12345678")],
        }
        request = Request(scope)
        client_id = _get_client_id(request)
        assert client_id.startswith("apikey:sk-test-")

    def test_get_client_id_with_auth_header(self):
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat/query",
            "headers": [(b"authorization", b"Bearer eyJhbGciOiJIUzI1NiJ9.test.payload")],
        }
        request = Request(scope)
        client_id = _get_client_id(request)
        assert client_id.startswith("auth:")

    def test_get_client_id_fallback_to_ip(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
            "server": ("192.168.1.1", 8000),
        }
        request = Request(scope)
        client_id = _get_client_id(request)
        assert client_id is not None
        assert isinstance(client_id, str)


class TestSetupRateLimit:
    def test_setup_adds_limiter_to_app(self):
        from fastapi import FastAPI

        app = FastAPI()
        setup_rate_limit(app)
        assert app.state.limiter is limiter
