# 权限评测运行器
# 用确定性 SQL + 角色组合验证 Data Permission Guard，而不是依赖 LLM 或数据库。

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.security.data_permission import DataPermissionGuard
from evaluation.permission_report_writer import PermissionReportWriter


@dataclass(frozen=True)
class PermissionEvaluationCase:
    case_id: str
    description: str
    roles: list[str]
    sql: str
    expected_allowed: bool
    expected_blocked_rule: str | None
    expect_row_filter: bool
    expect_authorized_sql_changed: bool
    policy_path: str | None = None


def ecommerce_schema() -> dict[str, Any]:
    """构造评测用最小 Schema，避免依赖真实数据库和 seed 状态。"""
    return {
        "tables": {
            "regions": {"columns": [{"name": "region_id"}, {"name": "region_name"}]},
            "customers": {
                "columns": [
                    {"name": "customer_id"},
                    {"name": "customer_name"},
                    {"name": "gender"},
                    {"name": "age"},
                    {"name": "region_id"},
                    {"name": "register_date"},
                ]
            },
            "orders": {
                "columns": [
                    {"name": "order_id"},
                    {"name": "customer_id"},
                    {"name": "order_date"},
                    {"name": "status"},
                    {"name": "total_amount"},
                ]
            },
            "order_items": {
                "columns": [
                    {"name": "item_id"},
                    {"name": "order_id"},
                    {"name": "product_id"},
                    {"name": "quantity"},
                    {"name": "unit_price"},
                ]
            },
            "payments": {
                "columns": [
                    {"name": "payment_id"},
                    {"name": "order_id"},
                    {"name": "payment_method"},
                    {"name": "payment_status"},
                    {"name": "paid_amount"},
                    {"name": "paid_at"},
                ]
            },
            "refunds": {
                "columns": [
                    {"name": "refund_id"},
                    {"name": "order_id"},
                    {"name": "refund_amount"},
                    {"name": "refund_reason"},
                    {"name": "refund_date"},
                ]
            },
        }
    }


def default_cases() -> list[PermissionEvaluationCase]:
    missing_policy = Path(__file__).parent / "cases" / "__missing_permission_policy.yaml"
    return [
        PermissionEvaluationCase(
            case_id="analyst_order_row_filter",
            description="analyst 查询订单指标时必须注入区域行级过滤。",
            roles=["analyst"],
            sql="SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000",
            expected_allowed=True,
            expected_blocked_rule=None,
            expect_row_filter=True,
            expect_authorized_sql_changed=True,
        ),
        PermissionEvaluationCase(
            case_id="admin_order_no_filter",
            description="admin 查询订单指标不应被行级过滤改写。",
            roles=["admin"],
            sql="SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000",
            expected_allowed=True,
            expected_blocked_rule=None,
            expect_row_filter=False,
            expect_authorized_sql_changed=False,
        ),
        PermissionEvaluationCase(
            case_id="analyst_customer_name_blocked",
            description="analyst 不能访问客户姓名字段。",
            roles=["analyst"],
            sql="SELECT customer_name FROM customers LIMIT 1000",
            expected_allowed=False,
            expected_blocked_rule="block_unauthorized_column",
            expect_row_filter=False,
            expect_authorized_sql_changed=False,
        ),
        PermissionEvaluationCase(
            case_id="admin_customer_name_allowed",
            description="admin 可以读取客户姓名和注册日期。",
            roles=["admin"],
            sql="SELECT customer_name, register_date FROM customers LIMIT 1000",
            expected_allowed=True,
            expected_blocked_rule=None,
            expect_row_filter=False,
            expect_authorized_sql_changed=False,
        ),
        PermissionEvaluationCase(
            case_id="support_payments_blocked",
            description="support 不能访问 payments 表。",
            roles=["support"],
            sql="SELECT paid_amount FROM payments LIMIT 1000",
            expected_allowed=False,
            expected_blocked_rule="block_unauthorized_table",
            expect_row_filter=False,
            expect_authorized_sql_changed=False,
        ),
        PermissionEvaluationCase(
            case_id="missing_policy_fail_closed",
            description="配置的策略文件缺失时必须 fail-closed。",
            roles=["analyst"],
            sql="SELECT total_amount FROM orders LIMIT 1000",
            expected_allowed=False,
            expected_blocked_rule="block_permission_policy_error",
            expect_row_filter=False,
            expect_authorized_sql_changed=False,
            policy_path=str(missing_policy),
        ),
    ]


class PermissionEvaluationRunner:
    """运行权限安全回归用例，输出稳定摘要供 CI 和面试演示使用。"""

    def __init__(
        self,
        cases: list[PermissionEvaluationCase] | None = None,
        guard: DataPermissionGuard | None = None,
        schema: dict[str, Any] | None = None,
    ):
        self.cases = cases or default_cases()
        self.guard = guard or DataPermissionGuard()
        self.schema = schema or ecommerce_schema()

    def evaluate_all(self) -> dict[str, Any]:
        results = [self._evaluate_case(case) for case in self.cases]
        summary = self._summarize(results)
        return {"summary": summary, "results": results}

    def _evaluate_case(self, case: PermissionEvaluationCase) -> dict[str, Any]:
        previous_policy_path = os.environ.get("DATA_PERMISSION_POLICY_PATH")
        try:
            # 每条 case 显式设置策略来源，避免外部环境变量影响权限评测结果。
            if case.policy_path is None:
                os.environ.pop("DATA_PERMISSION_POLICY_PATH", None)
            else:
                os.environ["DATA_PERMISSION_POLICY_PATH"] = case.policy_path

            result = self.guard.authorize(
                case.sql,
                {
                    "user_id": f"eval:{case.case_id}",
                    "auth_method": "evaluation",
                    "roles": case.roles,
                },
                self.schema,
            )
            actual_row_filter = bool(result.row_filters_applied)
            actual_sql_changed = result.authorized_sql != case.sql if result.is_allowed else False
            return self._case_result(
                case,
                actual_allowed=result.is_allowed,
                actual_blocked_rule=result.blocked_rule,
                actual_row_filter=actual_row_filter,
                actual_sql_changed=actual_sql_changed,
                row_filters_applied=result.row_filters_applied,
                error_type=None,
            )
        except Exception as exc:
            return self._case_result(
                case,
                actual_allowed=False,
                actual_blocked_rule=None,
                actual_row_filter=False,
                actual_sql_changed=False,
                row_filters_applied=[],
                error_type=type(exc).__name__,
            )
        finally:
            if previous_policy_path is None:
                os.environ.pop("DATA_PERMISSION_POLICY_PATH", None)
            else:
                os.environ["DATA_PERMISSION_POLICY_PATH"] = previous_policy_path

    def _case_result(
        self,
        case: PermissionEvaluationCase,
        actual_allowed: bool,
        actual_blocked_rule: str | None,
        actual_row_filter: bool,
        actual_sql_changed: bool,
        row_filters_applied: list[dict[str, Any]],
        error_type: str | None,
    ) -> dict[str, Any]:
        decision_matched = actual_allowed == case.expected_allowed
        rule_matched = actual_blocked_rule == case.expected_blocked_rule
        row_filter_matched = actual_row_filter == case.expect_row_filter
        sql_change_matched = actual_sql_changed == case.expect_authorized_sql_changed
        # 单 case 门禁要求四类预期全部命中，且没有异常兜底。
        passed = (
            decision_matched
            and rule_matched
            and row_filter_matched
            and sql_change_matched
            and error_type is None
        )
        return {
            "case_id": case.case_id,
            "description": case.description,
            "roles": case.roles,
            "expected_allowed": case.expected_allowed,
            "actual_allowed": actual_allowed,
            "decision_matched": decision_matched,
            "expected_blocked_rule": case.expected_blocked_rule,
            "actual_blocked_rule": actual_blocked_rule,
            "rule_matched": rule_matched,
            "expect_row_filter": case.expect_row_filter,
            "actual_row_filter": actual_row_filter,
            "row_filter_matched": row_filter_matched,
            "expect_authorized_sql_changed": case.expect_authorized_sql_changed,
            "actual_authorized_sql_changed": actual_sql_changed,
            "authorized_sql_change_matched": sql_change_matched,
            "row_filters_applied": row_filters_applied,
            "error_type": error_type,
            "passed": passed,
        }

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(results)
        return {
            "total_cases": total,
            "allowed_decision_accuracy": PermissionEvaluationRunner._rate(
                results, "decision_matched"
            ),
            "blocked_rule_accuracy": PermissionEvaluationRunner._rate(results, "rule_matched"),
            "row_filter_expectation_accuracy": PermissionEvaluationRunner._rate(
                results, "row_filter_matched"
            ),
            "authorized_sql_change_accuracy": PermissionEvaluationRunner._rate(
                results, "authorized_sql_change_matched"
            ),
            "passed": bool(total) and all(item["passed"] for item in results),
        }

    @staticmethod
    def _rate(results: list[dict[str, Any]], field: str) -> float:
        if not results:
            return 0.0
        return sum(1 for item in results if item[field]) / len(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic permission evaluation")
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    parser.add_argument("--write-report", action="store_true", help="write JSON and Markdown reports")
    parser.add_argument("--output-dir", help="directory for written reports")
    parser.add_argument("--timestamp", help="timestamp suffix for written reports")
    args = parser.parse_args(argv)
    report = PermissionEvaluationRunner().evaluate_all()
    if args.write_report:
        # CI 需要持久化机器可读和面试可读报告，输出目录遵循现有 evaluation writer 规则。
        PermissionReportWriter(output_dir=args.output_dir, timestamp=args.timestamp).write(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
