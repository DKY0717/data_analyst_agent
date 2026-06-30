from fastapi.testclient import TestClient

from app.main import app


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
