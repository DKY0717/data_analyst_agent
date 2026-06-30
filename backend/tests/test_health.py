from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import create_jwt_token


def test_readiness_checks_database():
    client = TestClient(app)

    response = client.get("/health/readiness")

    # readiness 不只检查进程存活，还要证明数据库连接当前可用。
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "ready"
    assert payload["database"]["ok"] is True
    assert payload["database"]["backend"] in {"duckdb", "postgresql"}


def test_readiness_failure_hides_database_error(monkeypatch):
    from app.api import health

    class BrokenConnection:
        backend = "duckdb"

        def get_session(self):
            raise RuntimeError("password=private DSN failure")

    client = TestClient(app)
    monkeypatch.setattr(health, "db_connection", BrokenConnection())

    response = client.get("/health/readiness")

    # 数据库异常可能包含 DSN 或密码，API 对外只返回稳定的泛化错误。
    assert response.status_code == 503
    assert response.json()["detail"] == "服务未就绪"
    assert "private" not in response.text


def make_ab_test_payload(test_id: str = "prompt_test"):
    # 使用完整的 A/B 测试 payload，确保测试覆盖真实管理写入接口。
    return {
        "test_id": test_id,
        "description": "compare prompt variants",
        "variants": [
            {"name": "control", "prompt_name": "generate_sql", "prompt_version": 1, "weight": 1.0},
            {"name": "treatment", "prompt_name": "generate_sql", "prompt_version": 2, "weight": 1.0},
        ],
    }


def test_create_ab_test_requires_credentials_when_auth_enabled():
    client = TestClient(app)

    # 认证开启后，运行时配置写入口不能再匿名调用。
    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        response = client.post("/health/ab-tests", json=make_ab_test_payload())

    assert response.status_code == 401


def test_create_ab_test_rejects_non_admin_jwt_when_auth_enabled():
    client = TestClient(app)

    # 普通分析员身份只能查询数据，不能修改 A/B 测试运行时配置。
    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        token = create_jwt_token("demo:analyst", ["analyst"])["access_token"]
        response = client.post(
            "/health/ab-tests",
            json=make_ab_test_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_monitoring_detail_endpoints_require_credentials_when_auth_enabled():
    client = TestClient(app)

    # 这些端点不是 liveness/readiness 探针，会暴露缓存、prompt 版本和实验状态。
    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        for path in ["/health/cache", "/health/metrics", "/health/ab-tests"]:
            response = client.get(path)
            assert response.status_code == 401


def test_monitoring_detail_endpoints_reject_non_admin_jwt_when_auth_enabled():
    client = TestClient(app)

    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        token = create_jwt_token("demo:analyst", ["analyst"])["access_token"]
        for path in ["/health/cache", "/health/metrics", "/health/ab-tests"]:
            response = client.get(path, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 403


def test_monitoring_detail_endpoints_accept_api_key_when_auth_enabled():
    import app.security.auth as auth_mod

    client = TestClient(app)

    try:
        with patch("app.security.auth.API_KEYS_RAW", "sk-monitoring-key"):
            auth_mod._api_keys = {}
            for path in ["/health/cache", "/health/metrics", "/health/ab-tests"]:
                response = client.get(path, headers={"X-API-Key": "sk-monitoring-key"})
                assert response.status_code == 200
    finally:
        auth_mod._api_keys = {}


def test_create_ab_test_accepts_admin_jwt_when_auth_enabled():
    client = TestClient(app)

    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        token = create_jwt_token("demo:admin", ["admin"])["access_token"]
        response = client.post(
            "/health/ab-tests",
            json=make_ab_test_payload("admin_prompt_test"),
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["test_id"] == "admin_prompt_test"


def test_create_ab_test_accepts_api_key_when_auth_enabled():
    import app.security.auth as auth_mod

    client = TestClient(app)

    # API Key 作为机器凭证保留给 CI、监控或运维脚本使用。
    try:
        with patch("app.security.auth.API_KEYS_RAW", "sk-management-key"):
            auth_mod._api_keys = {}
            response = client.post(
                "/health/ab-tests",
                json=make_ab_test_payload("api_key_prompt_test"),
                headers={"X-API-Key": "sk-management-key"},
            )
    finally:
        auth_mod._api_keys = {}

    assert response.status_code == 200
    assert response.json()["data"]["test_id"] == "api_key_prompt_test"


def test_create_ab_test_rejects_invalid_variant_payloads():
    client = TestClient(app, raise_server_exceptions=False)
    with patch("app.security.auth.JWT_SECRET", "test-secret"):
        token = create_jwt_token("demo:admin", ["admin"])["access_token"]
    invalid_payloads = [
        {**make_ab_test_payload("missing_prompt_name"), "variants": [{"name": "control", "prompt_version": 1}]},
        {**make_ab_test_payload("empty_variants"), "variants": []},
        {
            **make_ab_test_payload("negative_weight"),
            "variants": [
                {"name": "control", "prompt_name": "generate_sql", "prompt_version": 1, "weight": -1.0},
            ],
        },
    ]

    for payload in invalid_payloads:
        with patch("app.security.auth.JWT_SECRET", "test-secret"):
            response = client.post(
                "/health/ab-tests",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        # 管理接口输入错误应稳定返回 422，而不是进入业务逻辑后抛 500。
        assert response.status_code == 422
