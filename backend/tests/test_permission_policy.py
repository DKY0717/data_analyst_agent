from pathlib import Path

import pytest

from app.security.permission_policy import (
    PermissionPolicyError,
    PermissionPolicyLoader,
)


def write_policy(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_loader_reads_valid_policy_and_normalizes_names(tmp_path):
    path = write_policy(
        tmp_path / "policy.yaml",
        """
version: 1
roles:
  Analyst:
    tables:
      Orders:
        columns: ["ORDER_ID", "TOTAL_AMOUNT"]
        row_filter:
          expression: "customer_id IN (SELECT customer_id FROM customers WHERE region_id IN (1, 2))"
          rule_id: "row_filter_region_scope"
""",
    )

    policy = PermissionPolicyLoader(path).load()

    table = policy.roles["analyst"].tables["orders"]
    assert table.columns == {"order_id", "total_amount"}
    assert table.row_filter is not None
    assert table.row_filter.rule_id == "row_filter_region_scope"
    assert "customers" in table.row_filter.referenced_tables


def test_loader_reuses_cached_policy_when_file_is_unchanged(tmp_path):
    path = write_policy(
        tmp_path / "policy.yaml",
        """
version: 1
roles:
  analyst:
    tables:
      orders:
        columns: ["order_id"]
""",
    )

    first = PermissionPolicyLoader(path).load()
    second = PermissionPolicyLoader(path).load()

    assert second is first


def test_loader_rejects_missing_configured_file(tmp_path):
    loader = PermissionPolicyLoader(tmp_path / "missing.yaml")

    with pytest.raises(PermissionPolicyError, match="not found"):
        loader.load()


def test_loader_rejects_malformed_yaml(tmp_path):
    path = write_policy(tmp_path / "bad.yaml", "version: [")

    with pytest.raises(PermissionPolicyError, match="malformed"):
        PermissionPolicyLoader(path).load()


def test_loader_rejects_invalid_row_filter_expression(tmp_path):
    path = write_policy(
        tmp_path / "bad_filter.yaml",
        """
version: 1
roles:
  analyst:
    tables:
      orders:
        columns: ["*"]
        row_filter:
          expression: "customer_id IN ("
          rule_id: "row_filter_region_scope"
""",
    )

    with pytest.raises(PermissionPolicyError, match="row filter"):
        PermissionPolicyLoader(path).load()


def test_loader_rejects_row_filter_without_rule_id(tmp_path):
    path = write_policy(
        tmp_path / "bad_filter.yaml",
        """
version: 1
roles:
  analyst:
    tables:
      orders:
        columns: ["*"]
        row_filter:
          expression: "customer_id > 0"
""",
    )

    with pytest.raises(PermissionPolicyError, match="rule_id"):
        PermissionPolicyLoader(path).load()
