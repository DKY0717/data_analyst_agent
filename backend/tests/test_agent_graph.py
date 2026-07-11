# AgentGraph 工作流测试
# 使用 mock 隔离外部依赖（LLM、数据库），测试工作流的节点调度和条件分支逻辑

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.graph import AgentGraph
from app.analysis_intent.llm_parser import AnalysisIntentLLMParser
from app.analysis_intent.models import AnalysisIntent, IntentSlot
from app.models.schemas import SQLGeneratorOutput, SQLRepairOutput
from app.security.data_permission import DataPermissionResult
from app.services.llm_observability import record_call, start_trace


# ---- 测试用 fixtures ----

def make_schema_context():
    """构造模拟的 Schema 上下文"""
    return {
        "tables": {
            "orders": {
                "table_name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER", "nullable": False},
                    {"name": "total_amount", "type": "DECIMAL", "nullable": False},
                ],
                "primary_keys": ["order_id"]
            }
        }
    }


def make_query_result_success():
    """构造模拟的查询成功结果"""
    return {
        "success": True,
        "columns": ["month", "sales"],
        "rows": [["2024-01", 12840.5], ["2024-02", 14520.8]],
        "execution_time_ms": 42,
        "row_count": 2
    }


def make_query_result_failure():
    """构造模拟的查询失败结果"""
    return {
        "success": False,
        "columns": [],
        "rows": [],
        "execution_time_ms": 10,
        "error": "Table 'nonexistent' not found",
        "error_type": "CatalogException"
    }


@pytest.fixture(autouse=True)
def block_unmocked_intent_llm(monkeypatch):
    """AgentGraph 单测默认禁止真实模型调用，显式 mock 的用例仍可覆盖该边界。"""

    async def fail_fast(_self, _question):
        # 这些测试验证图编排而非外部模型；遗漏 mock 时必须立即失败降级，不能等待网络重试。
        raise RuntimeError("intent llm must be mocked in AgentGraph tests")

    monkeypatch.setattr(AnalysisIntentLLMParser, "parse", fail_fast)


@pytest.mark.asyncio
async def test_agent_graph_suite_blocks_unmocked_intent_llm():
    """回归保护：测试默认路径不能触发 OpenAI-compatible API。"""
    graph = AgentGraph()

    with patch(
        "app.analysis_intent.llm_parser.llm_client.parse_analysis_intent",
        new_callable=AsyncMock,
    ) as mock_api:
        with pytest.raises(RuntimeError, match="must be mocked"):
            await graph.llm_parser.parse("统计销售额")

    mock_api.assert_not_called()


# ---- 测试用例 ----

class TestAgentGraphHappyPath:
    """测试正常流程：Schema → SQL 生成 → 校验 → 执行 → 答案"""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """正常流程：所有节点顺利执行，最终返回 answer"""
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT strftime(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales FROM orders GROUP BY month",
            tables=["orders"],
            columns=["order_date", "total_amount"],
            explanation="按月统计销售额"
        )
        mock_query_result = make_query_result_success()

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": mock_sql_output.sql + " LIMIT 1000",
                "reason": None
            }
            mock_runner.execute.return_value = mock_query_result
            mock_optimizer.optimize.return_value = ["建议避免 SELECT *，只选择分析需要的字段"]
            mock_answer.generate = AsyncMock(return_value="2024年上半年销售额呈上升趋势")

            result = await graph.run("统计2024年每月销售额")

        assert result["answer"] == "2024年上半年销售额呈上升趋势"
        assert result["is_sql_safe"] is True
        assert result["execution_success"] is True
        assert result["retry_count"] == 0
        assert result["query_result"]["row_count"] == 2
        assert result["optimization_suggestions"] == ["建议避免 SELECT *，只选择分析需要的字段"]
        assert result["intent_is_safe"] is True
        assert result["audit_report"]["events"][0]["stage"] == "intent"
        assert result["audit_report"]["events"][0]["status"] == "success"
        assert result["audit_report"]["final_sql"].endswith("LIMIT 1000")
        assert {event["stage"] for event in result["audit_report"]["events"]} >= {
            "generation", "guard", "execution", "answer"
        }
        mock_optimizer.optimize.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_pipeline_collects_llm_calls_in_audit_report(self):
        graph = AgentGraph()
        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT COUNT(*) FROM orders",
            tables=["orders"],
            columns=[],
            explanation="统计订单数",
        )

        async def parse_with_metrics(*args):
            record_call(
                {
                    "stage": "parse_analysis_intent",
                    "model": "qwen-plus",
                    "input_tokens": 60,
                    "output_tokens": 10,
                    "total_tokens": 70,
                    "latency_ms": 200,
                    "attempt_count": 1,
                    "estimated_cost": None,
                    "success": True,
                    "error_type": None,
                }
            )
            return AnalysisIntent(
                metrics=[IntentSlot(concept="order_count", confidence=0.95)],
                overall_confidence=0.95,
            )

        async def generate_with_metrics(*args):
            record_call(
                {
                    "stage": "generate_sql",
                    "model": "qwen-plus",
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "latency_ms": 500,
                    "attempt_count": 1,
                    "estimated_cost": None,
                    "success": True,
                    "error_type": None,
                }
            )
            return mock_sql_output

        async def answer_with_metrics(*args):
            record_call(
                {
                    "stage": "generate_answer",
                    "model": "qwen-plus",
                    "input_tokens": 80,
                    "output_tokens": 30,
                    "total_tokens": 110,
                    "latency_ms": 300,
                    "attempt_count": 1,
                    "estimated_cost": None,
                    "success": True,
                    "error_type": None,
                }
            )
            return "订单总数已统计"

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.intent_guard") as mock_intent_guard, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer, \
             patch.object(
                 graph.llm_parser,
                 "parse",
                 new=AsyncMock(side_effect=parse_with_metrics),
             ):
            mock_loader.get_full_schema.return_value = mock_schema
            mock_intent_guard.validate.return_value = {
                "is_safe": True,
                "rule_id": None,
                "reason": None,
                "category": None,
            }
            mock_gen.generate = AsyncMock(side_effect=generate_with_metrics)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": "SELECT COUNT(*) FROM orders LIMIT 1000",
                "reason": None,
            }
            mock_runner.execute.return_value = make_query_result_success()
            mock_optimizer.optimize.return_value = []
            mock_answer.generate = AsyncMock(side_effect=answer_with_metrics)

            result = await graph.run("统计订单数")

        assert [call["stage"] for call in result["llm_calls"]] == [
            "parse_analysis_intent",
            "generate_sql",
            "generate_answer",
        ]
        assert result["audit_report"]["llm_observability"]["call_count"] == 3
        assert result["audit_report"]["llm_observability"]["total_tokens"] == 300


class TestAgentGraphValidationFailure:
    """测试 SQL 校验失败后必须直接终止"""

    @pytest.mark.asyncio
    async def test_validate_failure_does_not_enter_repair(self):
        """Guard 拒绝的 SQL 不得交给修复代理改写为其他查询"""
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="DELETE FROM orders",
            tables=["orders"],
            columns=[],
            explanation="危险 SQL"
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.intent_guard") as mock_intent_guard, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.sql_repair_agent") as mock_repair, \
             patch("app.agents.graph.query_runner") as mock_runner:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_intent_guard.validate.return_value = {
                "is_safe": True,
                "rule_id": None,
                "reason": None,
                "category": None,
            }
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": False,
                "sanitized_sql": "DELETE FROM orders",
                "reason": "禁止的语句类型: DELETE",
            }
            mock_repair.repair = AsyncMock()

            result = await graph.run("删除所有订单")

        assert result["is_sql_safe"] is False
        assert result["retry_count"] == 0
        assert result["answer"] is None
        mock_repair.repair.assert_not_called()
        mock_runner.execute.assert_not_called()


class TestAgentGraphAuthorization:
    """测试 SQL Guard 之后的数据权限检查节点"""

    @pytest.mark.asyncio
    async def test_permission_block_does_not_execute_or_repair(self):
        graph = AgentGraph()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT c.customer_name FROM customers c",
            tables=["customers"],
            columns=["customer_name"],
            explanation="查询客户姓名",
        )
        permission_result = DataPermissionResult(
            is_allowed=False,
            reason="当前角色无权访问字段: customers.customer_name",
            blocked_rule="block_unauthorized_column",
            audit_events=[
                {
                    "stage": "authorization",
                    "action": "authorize_sql",
                    "status": "blocked",
                    "message": "当前角色无权访问字段: customers.customer_name",
                    "rule_id": "block_unauthorized_column",
                    "details": {"table": "customers", "column": "customer_name"},
                }
            ],
            referenced_tables=["customers"],
            referenced_columns=["customers.customer_name"],
            authorized_sql="",
            row_filters_applied=[],
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.data_permission_guard") as mock_permission, \
             patch("app.agents.graph.sql_repair_agent") as mock_repair, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.session_store") as mock_session_store:

            mock_session_store.get_context.return_value = ""
            mock_loader.get_full_schema.return_value = make_schema_context()
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": "SELECT c.customer_name FROM customers c LIMIT 1000",
                "reason": None,
            }
            mock_permission.authorize.return_value = permission_result
            mock_repair.repair = AsyncMock()

            result = await graph.run(
                "查询客户姓名",
                session_id="session-permission-block",
                auth_user={"user_id": "user:analyst", "auth_method": "jwt", "roles": ["analyst"]},
            )

        assert result["status"] == "blocked"
        assert result["permission_allowed"] is False
        assert result["permission_error"] == "当前角色无权访问字段: customers.customer_name"
        assert "数据权限策略阻断" in result["answer"]
        assert result["audit_report"]["blocked_rules"] == ["block_unauthorized_column"]
        mock_permission.authorize.assert_called_once_with(
            "SELECT c.customer_name FROM customers c LIMIT 1000",
            {"user_id": "user:analyst", "auth_method": "jwt", "roles": ["analyst"]},
            make_schema_context(),
        )
        mock_runner.execute.assert_not_called()
        mock_repair.repair.assert_not_called()
        mock_session_store.append_turn.assert_not_called()

    @pytest.mark.asyncio
    async def test_permission_success_executes_after_sql_guard(self):
        graph = AgentGraph()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT SUM(total_amount) AS sales FROM orders",
            tables=["orders"],
            columns=["total_amount"],
            explanation="统计销售额",
        )
        permission_result = DataPermissionResult(
            is_allowed=True,
            reason="SQL 通过数据权限检查",
            blocked_rule=None,
            audit_events=[
                {
                    "stage": "authorization",
                    "action": "authorize_sql",
                    "status": "success",
                    "message": "SQL 通过数据权限检查",
                    "rule_id": None,
                    "details": {"tables": ["orders"]},
                }
            ],
            referenced_tables=["orders"],
            referenced_columns=["orders.total_amount"],
            authorized_sql="SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000",
            row_filters_applied=[],
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.data_permission_guard") as mock_permission, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer:

            mock_loader.get_full_schema.return_value = make_schema_context()
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": "SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000",
                "reason": None,
            }
            mock_permission.authorize.return_value = permission_result
            mock_runner.execute.return_value = make_query_result_success()
            mock_optimizer.optimize.return_value = []
            mock_answer.generate = AsyncMock(return_value="销售额已统计")

            result = await graph.run("统计销售额")

        assert result["execution_success"] is True
        assert result["permission_allowed"] is True
        assert {event["stage"] for event in result["audit_report"]["events"]} >= {
            "guard", "authorization", "execution"
        }
        mock_permission.authorize.assert_called_once()
        mock_runner.execute.assert_called_once_with(
            "SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000"
        )

    @pytest.mark.asyncio
    async def test_permission_authorized_sql_replaces_validated_sql_before_execution(self):
        graph = AgentGraph()
        permission_result = DataPermissionResult(
            is_allowed=True,
            reason="SQL 通过数据权限检查",
            blocked_rule=None,
            audit_events=[
                {
                    "stage": "authorization",
                    "action": "authorize_sql",
                    "status": "success",
                    "message": "SQL 通过数据权限检查",
                    "rule_id": "row_filter_applied",
                    "details": {
                        "row_filters_applied": [
                            {"table": "orders", "rule_id": "row_filter_region_scope"}
                        ],
                    },
                }
            ],
            referenced_tables=["orders"],
            referenced_columns=["orders.total_amount"],
            authorized_sql=(
                "SELECT SUM(total_amount) FROM orders "
                "WHERE customer_id IN (SELECT customer_id FROM customers WHERE region_id IN (1, 2)) "
                "LIMIT 1000"
            ),
            row_filters_applied=[{"table": "orders", "rule_id": "row_filter_region_scope"}],
        )

        with patch("app.agents.graph.intent_guard") as mock_intent, \
             patch.object(graph.rule_parser, "parse") as mock_rule_parse, \
             patch.object(graph.llm_parser, "parse", new_callable=AsyncMock) as mock_llm_parse, \
             patch("app.agents.graph.schema_grounder") as mock_grounder, \
             patch("app.agents.graph.clarification_engine") as mock_clarification, \
             patch("app.agents.graph.schema_loader") as mock_schema, \
             patch("app.agents.graph.sql_generator") as mock_generator, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.data_permission_guard") as mock_permission, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer:

            mock_intent.validate.return_value = {
                "is_safe": True,
                "reason": None,
                "rule_id": None,
                "category": None,
            }
            mock_rule_parse.return_value = AnalysisIntent(question="统计销售额")
            mock_llm_parse.side_effect = RuntimeError("skip llm")
            mock_grounder.ground.return_value = {"schema_route": {"selected_tables": ["orders"]}}
            mock_clarification.check.return_value = None
            mock_schema.get_full_schema.return_value = {
                "tables": {"orders": {"columns": [{"name": "total_amount"}]}}
            }
            mock_generator.generate = AsyncMock(return_value=SQLGeneratorOutput(
                sql="SELECT SUM(total_amount) FROM orders",
                tables=["orders"],
                columns=["total_amount"],
                explanation="sum",
            ))
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": "SELECT SUM(total_amount) FROM orders LIMIT 1000",
                "reason": None,
                "audit_events": [],
                "limit_injected": True,
            }
            mock_permission.authorize.return_value = permission_result
            mock_runner.execute.return_value = {
                "success": True,
                "columns": ["sales"],
                "rows": [[100]],
                "row_count": 1,
                "execution_time_ms": 5,
            }
            mock_optimizer.optimize.return_value = []
            mock_answer.generate = AsyncMock(return_value="销售额为 100")

            result = await graph.run(
                "统计销售额",
                session_id="session-row-filter",
                auth_user={"user_id": "demo:analyst", "auth_method": "jwt", "roles": ["analyst"]},
            )

        mock_runner.execute.assert_called_once_with(permission_result.authorized_sql)
        assert result["validated_sql"] == permission_result.authorized_sql
        assert result["audit_report"]["final_sql"] == permission_result.authorized_sql
        assert result["audit_report"]["blocked_rules"] == []

    @pytest.mark.asyncio
    async def test_run_accepts_auth_user_and_includes_it_in_initial_state(self):
        graph = AgentGraph()

        async def echo_state(state):
            state["audit_events"] = []
            return state

        graph.graph = MagicMock()
        graph.graph.ainvoke = AsyncMock(side_effect=echo_state)

        result = await graph.run(
            "统计销售额",
            auth_user={"user_id": "user:demo", "auth_method": "jwt", "roles": ["analyst"]},
        )

        assert result["auth_user"] == {
            "user_id": "user:demo",
            "auth_method": "jwt",
            "roles": ["analyst"],
        }
        assert result["permission_allowed"] is True
        assert result["permission_error"] is None

    def test_clarification_expired_state_has_dev_auth_defaults(self):
        graph = AgentGraph()

        state = graph._build_expired_clarification_state("销售额", "session-1")

        assert state["auth_user"] is None
        assert state["permission_allowed"] is True
        assert state["permission_error"] is None


class TestAgentGraphExecutionFailure:
    """测试 SQL 执行失败后的修复流程"""

    @pytest.mark.asyncio
    async def test_execute_node_keeps_diagnostic_internal_and_audit_message_generic(self):
        """Repair 可用详细诊断，但对外审计事件不能复制数据库错误原文。"""
        graph = AgentGraph()
        diagnostic = "Catalog Error: secret_table does not exist"

        with patch("app.agents.graph.query_runner") as mock_runner:
            mock_runner.execute.return_value = {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": 3,
                "error": "查询执行失败",
                "diagnostic_error": diagnostic,
                "error_type": "CatalogException",
                "execution_mode": "sandbox",
            }

            result = await graph._execute_sql(
                {
                    "question": "查询订单",
                    "validated_sql": "SELECT * FROM orders LIMIT 1000",
                    "audit_events": [],
                }
            )

        assert result["execution_error"] == diagnostic
        assert result["audit_events"][0]["message"] == "查询执行失败"
        assert result["audit_events"][0]["details"]["execution_mode"] == "sandbox"
        assert diagnostic not in repr(result["audit_events"])

    @pytest.mark.asyncio
    async def test_execute_fail_then_repair_success(self):
        """校验通过 → 执行失败 → 修复 → 校验 → 执行成功"""
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT * FROM nonexistent_table",
            tables=["nonexistent_table"],
            columns=[],
            explanation="查询不存在的表"
        )
        mock_repair_output = SQLRepairOutput(
            repaired_sql="SELECT * FROM orders",
            repair_reason="修正了表名"
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.sql_repair_agent") as mock_repair, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)

            # 两次校验都通过
            mock_guard.validate.side_effect = [
                {"is_safe": True, "sanitized_sql": "SELECT * FROM nonexistent_table LIMIT 1000", "reason": None},
                {"is_safe": True, "sanitized_sql": "SELECT * FROM orders LIMIT 1000", "reason": None}
            ]

            # 第一次执行失败，第二次执行成功
            mock_runner.execute.side_effect = [
                make_query_result_failure(),
                make_query_result_success()
            ]

            mock_repair.repair = AsyncMock(return_value=mock_repair_output)
            mock_optimizer.optimize.return_value = ["建议只选择需要展示的列"]
            mock_answer.generate = AsyncMock(return_value="查询成功")

            result = await graph.run("查询所有订单")

        assert result["answer"] == "查询成功"
        assert result["retry_count"] == 1
        assert result["execution_success"] is True
        assert result["optimization_suggestions"] == ["建议只选择需要展示的列"]


class TestAgentGraphMaxRetries:
    """测试重试耗尽的情况"""

    @pytest.mark.asyncio
    async def test_validation_fails_max_retries(self):
        """校验失败后立即终止，不消耗修复重试次数"""
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="DROP TABLE orders",
            tables=["orders"],
            columns=[],
            explanation="危险 SQL"
        )
        mock_repair_output = SQLRepairOutput(
            repaired_sql="DROP TABLE orders",
            repair_reason="无法修复"
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.intent_guard") as mock_intent_guard, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.sql_repair_agent") as mock_repair:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_intent_guard.validate.return_value = {
                "is_safe": True,
                "rule_id": None,
                "reason": None,
                "category": None,
            }
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": False,
                "sanitized_sql": "DROP TABLE orders",
                "reason": "禁止的语句类型: DROP"
            }
            mock_repair.repair = AsyncMock(return_value=mock_repair_output)

            result = await graph.run("删除订单表")

        # Guard 拒绝后立即终止，没有 answer，也不调用修复代理。
        assert result["retry_count"] == 0
        assert result["answer"] is None
        assert result["is_sql_safe"] is False
        mock_repair.repair.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_fails_max_retries(self):
        """执行一直失败，重试耗尽后终止"""
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT * FROM bad_query",
            tables=["bad_query"],
            columns=[],
            explanation="有问题的查询"
        )
        mock_repair_output = SQLRepairOutput(
            repaired_sql="SELECT * FROM bad_query",
            repair_reason="未能修复"
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.sql_repair_agent") as mock_repair, \
             patch("app.agents.graph.query_runner") as mock_runner:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": "SELECT * FROM bad_query LIMIT 1000",
                "reason": None
            }
            mock_runner.execute.return_value = make_query_result_failure()
            mock_repair.repair = AsyncMock(return_value=mock_repair_output)

            result = await graph.run("查询 bad_query")

        assert result["retry_count"] == 3
        assert result["answer"] is None
        assert result["execution_success"] is False


class TestAgentGraphEdgeCases:
    """测试边界情况"""

    def test_graph_structure(self):
        """验证图的节点和边结构正确"""
        graph = AgentGraph()
        g = graph.graph.get_graph()
        nodes = set(g.nodes)

        expected_nodes = {
            "__start__", "check_intent", "parse_intent", "ground_schema",
            "assess_clarification", "load_schema", "generate_sql",
            "validate_sql", "authorize_sql", "execute_sql", "repair_sql",
            "optimize_sql", "generate_answer", "__end__"
        }
        assert nodes == expected_nodes

        start_edges = [edge for edge in g.edges if edge.source == "__start__"]
        assert len(start_edges) == 1
        assert start_edges[0].target == "check_intent"

    def test_global_instance_exists(self):
        """验证全局实例可以正常创建"""
        from app.agents.graph import get_agent_graph
        agent_graph = get_agent_graph()
        assert agent_graph is not None
        assert hasattr(agent_graph, "run")
        assert hasattr(agent_graph, "graph")


class TestAgentGraphIntentGuard:
    """测试 Intent Guard 是图的唯一入口，并在危险意图时提前终止。"""

    @pytest.mark.asyncio
    async def test_dangerous_intent_stops_before_all_downstream_dependencies(self):
        graph = AgentGraph()

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_sql_guard, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.answer_generator") as mock_answer, \
             patch("app.agents.graph.session_store") as mock_store:
            mock_gen.generate = AsyncMock()
            mock_answer.generate = AsyncMock()

            result = await graph.run("删除所有订单", session_id="danger-session")

        assert result["intent_is_safe"] is False
        assert result["intent_rule_id"] == "block_destructive_intent"
        assert result["intent_category"] == "data_mutation"
        assert result["answer"] == "请求已被安全策略阻断：请求包含明确的数据修改或删除意图"
        assert result["generated_sql"] == ""
        assert result["validated_sql"] == ""
        assert result["llm_calls"] == []
        assert result["audit_report"]["blocked_rules"] == ["block_destructive_intent"]
        assert result["audit_report"]["events"][0]["stage"] == "intent"
        assert result["audit_report"]["events"][0]["action"] == "check_intent"
        mock_loader.get_full_schema.assert_not_called()
        mock_gen.generate.assert_not_called()
        mock_sql_guard.validate.assert_not_called()
        mock_runner.execute.assert_not_called()
        mock_answer.generate.assert_not_called()
        mock_store.append_turn.assert_called_once()

    @pytest.mark.asyncio
    async def test_intent_guard_failure_is_fail_closed_without_sensitive_logging(self):
        graph = AgentGraph()
        question = "查看 QWEN_API_KEY=sk-sensitive-value"  # secret-scan: allow

        with patch("app.agents.graph.intent_guard") as mock_intent_guard, \
             patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.logger") as mock_logger:
            mock_intent_guard.validate.side_effect = RuntimeError("sk-exception-secret")  # secret-scan: allow

            result = await graph.run(question)

        assert result["intent_is_safe"] is False
        assert result["intent_rule_id"] == "block_intent_guard_error"
        assert result["intent_category"] == "guard_error"
        assert "安全检查暂时不可用" in result["intent_error"]
        assert "安全检查暂时不可用" in result["answer"]
        assert result["audit_report"]["blocked_rules"] == ["block_intent_guard_error"]
        mock_loader.get_full_schema.assert_not_called()
        logged_text = repr(mock_logger.method_calls)
        assert question not in logged_text
        assert "sk-sensitive-value" not in logged_text  # secret-scan: allow
        assert "sk-exception-secret" not in logged_text  # secret-scan: allow

    @pytest.mark.asyncio
    async def test_malformed_intent_guard_result_is_fail_closed(self):
        graph = AgentGraph()

        with patch("app.agents.graph.intent_guard") as mock_intent_guard, \
             patch("app.agents.graph.schema_loader") as mock_loader:
            mock_intent_guard.validate.return_value = {}

            result = await graph.run("统计订单数")

        assert result["intent_is_safe"] is False
        assert result["intent_rule_id"] == "block_intent_guard_error"
        assert result["intent_category"] == "guard_error"
        mock_loader.get_full_schema.assert_not_called()

    def test_pydantic_agent_state_defaults_intent_fields_and_empty_sql(self):
        from app.agents.state import AgentState
        state = AgentState(
            question="统计订单数",
            intent_is_safe=False,
            intent_rule_id=None,
            intent_category=None,
            intent_error=None,
            session_id=None,
            conversation_context=None,
            status="completed",
            schema_context=None,
            analysis_intent=None,
            grounding_result=None,
            clarification_request=None,
            generated_sql="",
            validated_sql="",
            is_sql_safe=False,
            validation_error=None,
            execution_success=False,
            query_result=None,
            execution_error=None,
            retry_count=0,
            answer=None,
            optimization_suggestions=[],
            audit_events=[],
            audit_report=None,
            llm_calls=[],
        )

        assert state["intent_is_safe"] is False
        assert state["intent_rule_id"] is None
        assert state["intent_category"] is None
        assert state["intent_error"] is None
        assert state["generated_sql"] == ""
        assert state["validated_sql"] == ""


class TestAgentGraphClarification:
    """测试主动澄清会暂停执行，并由会话存储保存可恢复候选。"""

    @pytest.mark.asyncio
    async def test_parse_intent_only_outputs_structured_intent(self):
        graph = AgentGraph()
        rule_intent = AnalysisIntent(
            missing_slots=["metric"],
            overall_confidence=0.0,
        )

        with patch.object(graph, "rule_parser") as mock_rule, \
             patch.object(graph, "llm_parser") as mock_llm:
            mock_rule.parse.return_value = rule_intent
            mock_llm.parse = AsyncMock(side_effect=Exception("LLM unavailable"))

            result = await graph._parse_intent(
                {"question": "帮我分析一下", "audit_events": []}
            )

        assert result["analysis_intent"]["missing_slots"] == ["metric"]
        assert "grounding" not in result["analysis_intent"]
        assert "clarification" not in result["analysis_intent"]
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_parse_intent_preserves_failed_llm_call_when_falling_back_to_rules(self):
        """LLM 意图解析失败也必须进入请求轨迹，便于解释降级原因。"""
        graph = AgentGraph()
        rule_intent = AnalysisIntent(
            metrics=[IntentSlot(concept="order_count", confidence=0.9)],
            overall_confidence=0.9,
        )

        async def fail_with_metrics(*args):
            record_call(
                {
                    "stage": "parse_analysis_intent",
                    "model": "qwen-plus",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": 50,
                    "attempt_count": 1,
                    "estimated_cost": None,
                    "success": False,
                    "error_type": "TimeoutError",
                }
            )
            raise TimeoutError("intent parser timeout")

        start_trace()
        with patch.object(graph, "rule_parser") as mock_rule, \
             patch.object(
                 graph.llm_parser,
                 "parse",
                 new=AsyncMock(side_effect=fail_with_metrics),
             ):
            mock_rule.parse.return_value = rule_intent
            result = await graph._parse_intent(
                {"question": "统计订单数", "audit_events": []}
            )

        assert result["analysis_intent"]["metrics"][0]["concept"] == "order_count"
        assert result["llm_calls"] == [
            {
                "stage": "parse_analysis_intent",
                "model": "qwen-plus",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency_ms": 50,
                "attempt_count": 1,
                "estimated_cost": None,
                "success": False,
                "error_type": "TimeoutError",
            }
        ]

    def test_ground_schema_adds_grounding_without_deciding_clarification(self):
        graph = AgentGraph()
        state = {
            "analysis_intent": AnalysisIntent(
                metrics=[],
                dimensions=[],
                missing_slots=["metric"],
                overall_confidence=0.0,
            ).model_dump(),
            "audit_events": [],
        }

        result = graph._ground_schema(state)

        assert result["grounding_result"]["schema_route"]["selected_tables"] == []
        assert result["analysis_intent"]["grounding"] == result["grounding_result"]
        assert "clarification" not in result["analysis_intent"]

    def test_assess_clarification_decides_pause_after_grounding(self):
        graph = AgentGraph()
        state = {
            "question": "帮我分析一下",
            "session_id": "session-clarify",
            "conversation_context": "",
            "analysis_intent": AnalysisIntent(
                missing_slots=["metric"],
                overall_confidence=0.0,
            ).model_dump(),
            "grounding_result": {"schema_route": {"selected_tables": []}},
            "audit_events": [],
        }

        result = graph._assess_clarification(state)

        assert result["status"] == "clarification_required"
        assert result["clarification_request"]["options"][0]["candidate_id"].startswith("metric_")
        assert result["analysis_intent"]["grounding"] == state["grounding_result"]
        assert result["analysis_intent"]["clarification"] == result["clarification_request"]

    @pytest.mark.asyncio
    async def test_clarification_required_stops_before_schema_and_sql_generation(self):
        graph = AgentGraph()
        rule_intent = AnalysisIntent(missing_slots=["metric"], overall_confidence=0.0)

        with patch.object(graph, "rule_parser") as mock_rule, \
             patch.object(graph, "llm_parser") as mock_llm, \
             patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.session_store") as mock_store:
            mock_rule.parse.return_value = rule_intent
            mock_llm.parse = AsyncMock(side_effect=Exception("LLM unavailable"))
            mock_store.get_context.return_value = ""
            mock_store.save_pending_clarification = MagicMock()
            mock_gen.generate = AsyncMock()

            result = await graph.run("帮我分析一下", session_id="session-clarify")

        assert result["status"] == "clarification_required"
        assert result["answer"] == "您想分析什么指标？例如：销售额、订单数、退款率等。"
        assert result["clarification_request"]["clarification_id"].startswith("clarify_")
        assert result["generated_sql"] == ""
        assert result["validated_sql"] == ""
        mock_loader.get_full_schema.assert_not_called()
        mock_gen.generate.assert_not_called()
        mock_store.save_pending_clarification.assert_called_once()
        assert mock_store.append_turn.call_count == 0

    @pytest.mark.asyncio
    async def test_clarification_response_reuses_resolved_question(self):
        graph = AgentGraph()
        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT SUM(total_amount) AS sales FROM orders",
            tables=["orders"],
            columns=["total_amount"],
            explanation="按用户澄清后的销售额指标统计",
        )

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer, \
             patch("app.agents.graph.session_store") as mock_store, \
             patch.object(graph, "rule_parser") as mock_rule, \
             patch.object(graph, "llm_parser") as mock_llm:
            mock_store.resolve_pending_clarification.return_value = {
                "resolved_question": "帮我分析一下。用户澄清：销售额（metric_sales_amount）",
            }
            mock_store.get_context.return_value = ""
            mock_rule.parse.return_value = AnalysisIntent(
                metrics=[],
                missing_slots=[],
                overall_confidence=0.95,
            )
            mock_llm.parse = AsyncMock(side_effect=Exception("LLM unavailable"))
            mock_loader.get_full_schema.return_value = mock_schema
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": mock_sql_output.sql + " LIMIT 1000",
                "reason": None,
            }
            mock_runner.execute.return_value = make_query_result_success()
            mock_optimizer.optimize.return_value = []
            mock_answer.generate = AsyncMock(return_value="销售额已统计")

            result = await graph.run(
                "销售额",
                session_id="session-clarify",
                clarification_response={
                    "clarification_id": "clarify_metric_001",
                    "candidate_id": "metric_sales_amount",
                },
            )

        mock_store.resolve_pending_clarification.assert_called_once_with(
            "session-clarify",
            "clarify_metric_001",
            candidate_id="metric_sales_amount",
            text=None,
        )
        assert mock_gen.generate.call_args.args[0] == "帮我分析一下。用户澄清：销售额（metric_sales_amount）"
        assert result["question"] == "帮我分析一下。用户澄清：销售额（metric_sales_amount）"
        assert result["status"] == "completed"

    def test_clarification_requires_session_id_for_recovery(self):
        graph = AgentGraph()
        intent = AnalysisIntent(missing_slots=["metric"], overall_confidence=0.0)

        assert graph._should_request_clarification(
            {"question": "帮我分析一下", "session_id": None},
            intent,
        ) is False


class TestAgentGraphConversationContext:
    """测试多轮会话上下文在 AgentGraph 中的传递和回写"""

    @pytest.mark.asyncio
    async def test_run_passes_session_context_to_sql_generator_and_saves_turn(self):
        graph = AgentGraph()

        mock_schema = make_schema_context()
        mock_sql_output = SQLGeneratorOutput(
            sql="SELECT region_name, SUM(total_amount) AS sales FROM orders GROUP BY region_name",
            tables=["orders", "regions"],
            columns=["region_name", "total_amount"],
            explanation="基于上一轮销售额按地区拆分"
        )
        mock_query_result = make_query_result_success()

        with patch("app.agents.graph.schema_loader") as mock_loader, \
             patch("app.agents.graph.sql_generator") as mock_gen, \
             patch("app.agents.graph.sql_guard") as mock_guard, \
             patch("app.agents.graph.query_runner") as mock_runner, \
             patch("app.agents.graph.sql_optimizer") as mock_optimizer, \
             patch("app.agents.graph.answer_generator") as mock_answer, \
             patch("app.agents.graph.session_store") as mock_store:

            mock_loader.get_full_schema.return_value = mock_schema
            mock_store.get_context.return_value = "上一轮分析上下文:\n- 问题: 统计销售额"
            mock_gen.generate = AsyncMock(return_value=mock_sql_output)
            mock_guard.validate.return_value = {
                "is_safe": True,
                "sanitized_sql": mock_sql_output.sql + " LIMIT 1000",
                "reason": None
            }
            mock_runner.execute.return_value = mock_query_result
            mock_optimizer.optimize.return_value = []
            mock_answer.generate = AsyncMock(return_value="已按地区拆分销售额")

            result = await graph.run("按地区拆一下", session_id="session-1")

        mock_store.get_context.assert_called_once_with("session-1")
        call_args = mock_gen.generate.call_args
        assert call_args[0][0] == "按地区拆一下"
        assert call_args[0][1] == mock_schema
        assert call_args[0][2] == "上一轮分析上下文:\n- 问题: 统计销售额"
        mock_store.append_turn.assert_called_once()
        assert mock_store.append_turn.call_args.args[0] == "session-1"
        assert result["session_id"] == "session-1"
        assert result["conversation_context"] == "上一轮分析上下文:\n- 问题: 统计销售额"
