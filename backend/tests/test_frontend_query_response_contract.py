"""前后端共享 QueryResponse 示例的契约测试。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.schemas import QueryResponse


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FIXTURE = ROOT / "frontend" / "tests" / "fixtures" / "query_response.json"


def load_contract_fixture() -> dict:
    """读取前端行为测试使用的同一份响应，避免两端各自维护假契约。"""
    return json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))


def test_frontend_query_response_fixture_matches_backend_model():
    response = QueryResponse.model_validate(load_contract_fixture())

    assert response.sql.startswith("SELECT")
    assert response.analysis_intent["metrics"][0]["concept"] == "sales_amount"
    assert response.optimization_suggestions == ["避免 SELECT *"]
    assert response.clarification["options"][0]["candidate_id"] == "metric_sales"


def test_query_response_rejects_removed_legacy_fields():
    payload = load_contract_fixture()
    payload["generated_sql"] = payload["sql"]

    # 对外响应采用严格模型，旧字段重新出现时必须让契约测试立即失败。
    with pytest.raises(ValidationError):
        QueryResponse.model_validate(payload)
