# AgentGraph 工作流测试
# 使用 mock 隔离外部依赖（LLM、数据库），测试工作流的节点调度和条件分支逻辑

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.graph import AgentGraph
from app.models.schemas import AgentState as AgentStateModel, SQLGeneratorOutput, SQLRepairOutput
from app.services.llm_observability import record_call


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
             patch("app.agents.graph.answer_generator") as mock_answer:
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

        assert len(result["llm_calls"]) == 2
        assert result["audit_report"]["llm_observability"]["call_count"] == 2
        assert result["audit_report"]["llm_observability"]["total_tokens"] == 230


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


class TestAgentGraphExecutionFailure:
    """测试 SQL 执行失败后的修复流程"""

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
            "__start__", "check_intent", "load_schema", "generate_sql",
            "validate_sql", "execute_sql", "repair_sql",
            "optimize_sql", "generate_answer", "__end__"
        }
        assert nodes == expected_nodes

        start_edges = [edge for edge in g.edges if edge.source == "__start__"]
        assert len(start_edges) == 1
        assert start_edges[0].target == "check_intent"

    def test_global_instance_exists(self):
        """验证全局实例可以正常创建"""
        from app.agents.graph import agent_graph
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
        state = AgentStateModel(question="统计订单数")

        assert state.intent_is_safe is False
        assert state.intent_rule_id is None
        assert state.intent_category is None
        assert state.intent_error is None
        assert state.generated_sql == ""
        assert state.validated_sql == ""


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
        mock_gen.generate.assert_awaited_once_with(
            "按地区拆一下",
            mock_schema,
            "上一轮分析上下文:\n- 问题: 统计销售额"
        )
        mock_store.append_turn.assert_called_once()
        assert mock_store.append_turn.call_args.args[0] == "session-1"
        assert result["session_id"] == "session-1"
        assert result["conversation_context"] == "上一轮分析上下文:\n- 问题: 统计销售额"
