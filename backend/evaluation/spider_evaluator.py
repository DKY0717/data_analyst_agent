# Spider NL2SQL 评测运行器
# 使用 Spider 数据集评测 Agent 的 SQL 生成能力

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.agents.graph import get_agent_graph
from evaluation.report_writer import ReportWriter


SPIDER_DIR = Path(__file__).parent.parent.parent / "data" / "spider"
CASES_FILE = Path(__file__).parent / "cases" / "spider_nl2sql_cases.yaml"


class SpiderEvaluator:
    """Spider 数据集评测器

    流程：
    1. 加载 Spider 评测用例
    2. 对每个用例，使用 Agent 生成 SQL
    3. 与参考 SQL 对比，计算准确率
    """

    def __init__(self, agent_runner=None, cases_file=None):
        self.agent_runner = agent_runner or get_agent_graph().run
        self.cases_file = Path(cases_file) if cases_file else CASES_FILE

    def load_cases(self) -> List[Dict[str, Any]]:
        """加载 Spider 评测用例"""
        with open(self.cases_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)["cases"]

    async def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """评测单个用例"""
        question = case["question"]
        reference_sql = case.get("reference_sql", "")
        db_id = case.get("db_id", "")
        difficulty = case.get("difficulty", "unknown")
        category = case.get("category", "unknown")

        try:
            # 使用 Agent 生成 SQL
            final_state = await self.agent_runner(question)

            generated_sql = final_state.get("validated_sql") or final_state.get("generated_sql") or ""
            execution_success = bool(final_state.get("execution_success"))
            guard_passed = bool(final_state.get("is_sql_safe"))
            retry_count = final_state.get("retry_count", 0)

            return {
                "case_id": case["id"],
                "question": question,
                "db_id": db_id,
                "difficulty": difficulty,
                "category": category,
                "reference_sql": reference_sql,
                "generated_sql": generated_sql,
                "generation_success": bool(generated_sql),
                "guard_passed": guard_passed,
                "execution_success": execution_success,
                "retry_count": retry_count,
                "sql_match": self._compare_sql(reference_sql, generated_sql),
            }
        except Exception as e:
            return {
                "case_id": case["id"],
                "question": question,
                "db_id": db_id,
                "difficulty": difficulty,
                "category": category,
                "reference_sql": reference_sql,
                "generated_sql": "",
                "generation_success": False,
                "guard_passed": False,
                "execution_success": False,
                "retry_count": 0,
                "sql_match": False,
                "error": str(e),
            }

    def _compare_sql(self, reference: str, generated: str) -> bool:
        """简单比较两个 SQL（标准化后比较）"""
        if not reference or not generated:
            return False
        ref_norm = self._normalize_sql(reference)
        gen_norm = self._normalize_sql(generated)
        return ref_norm == gen_norm

    def _normalize_sql(self, sql: str) -> str:
        """标准化 SQL 用于比较"""
        import re
        sql = sql.strip().rstrip(";")
        sql = re.sub(r"\s+", " ", sql)
        sql = sql.lower()
        return sql

    async def evaluate_all(self, max_cases: int = 50) -> Dict[str, Any]:
        """评测所有用例"""
        cases = self.load_cases()[:max_cases]
        results = []

        for i, case in enumerate(cases):
            print(f"评测进度: {i+1}/{len(cases)} - {case['question'][:50]}...")
            result = await self.evaluate_case(case)
            results.append(result)
            if i < len(cases) - 1:
                await asyncio.sleep(3)

        return {
            "summary": self.summarize_results(results),
            "results": results,
        }

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评测指标"""
        total = len(results)
        if total == 0:
            return {"total_cases": 0}

        generation_success = sum(1 for r in results if r["generation_success"])
        guard_passed = sum(1 for r in results if r["guard_passed"])
        execution_success = sum(1 for r in results if r["execution_success"])
        sql_match = sum(1 for r in results if r["sql_match"])

        # 按难度统计
        by_difficulty = {}
        for r in results:
            d = r["difficulty"]
            if d not in by_difficulty:
                by_difficulty[d] = {"total": 0, "success": 0, "match": 0}
            by_difficulty[d]["total"] += 1
            if r["execution_success"]:
                by_difficulty[d]["success"] += 1
            if r["sql_match"]:
                by_difficulty[d]["match"] += 1

        # 按类别统计
        by_category = {}
        for r in results:
            c = r["category"]
            if c not in by_category:
                by_category[c] = {"total": 0, "success": 0}
            by_category[c]["total"] += 1
            if r["execution_success"]:
                by_category[c]["success"] += 1

        return {
            "total_cases": total,
            "generation_success_rate": generation_success / total,
            "guard_pass_rate": guard_passed / total,
            "execution_success_rate": execution_success / total,
            "sql_match_rate": sql_match / total,
            "by_difficulty": by_difficulty,
            "by_category": by_category,
        }


async def main():
    """运行 Spider 评测"""
    evaluator = SpiderEvaluator()
    report = await evaluator.evaluate_all(max_cases=200)

    # 输出摘要
    summary = report["summary"]
    print("\n=== Spider NL2SQL 评测结果 ===")
    print(f"总用例数: {summary['total_cases']}")
    print(f"SQL 生成成功率: {summary['generation_success_rate']:.1%}")
    print(f"Guard 通过率: {summary['guard_pass_rate']:.1%}")
    print(f"执行成功率: {summary['execution_success_rate']:.1%}")
    print(f"SQL 匹配率: {summary['sql_match_rate']:.1%}")

    print("\n按难度分布:")
    for diff, stats in summary["by_difficulty"].items():
        print(f"  {diff}: {stats['success']}/{stats['total']} 成功, {stats['match']}/{stats['total']} 匹配")

    # 保存报告
    report_path = Path(__file__).parent / "reports" / "spider_evaluation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
