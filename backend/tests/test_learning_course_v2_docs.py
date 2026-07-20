"""全新学习课程 v2 的结构、导航和安全契约测试。"""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COURSE_ROOT = PROJECT_ROOT / "user_docs" / "data-analyst-agent-course-v2"
BASELINE_SHA = "8dffc1d76c514c7efe1b6e642ea1880a81989109"

# 固定章节清单同时约束导航和文件布局，避免首页宣称 32 章但实际缺页。
EXPECTED_CHAPTERS = (
    "part01-foundations/chapter01-project-architecture.md",
    "part01-foundations/chapter02-python-async-and-models.md",
    "part01-foundations/chapter03-sql-duckdb-domain.md",
    "part01-foundations/chapter04-environment-config-debugging.md",
    "part02-minimum-nl2sql/chapter05-database-schema-loader.md",
    "part02-minimum-nl2sql/chapter06-fastapi-boundaries.md",
    "part02-minimum-nl2sql/chapter07-openai-compatible-llm.md",
    "part02-minimum-nl2sql/chapter08-minimum-nl2sql-pipeline.md",
    "part03-agent/chapter09-analysis-intent.md",
    "part03-agent/chapter10-semantic-and-metadata.md",
    "part03-agent/chapter11-grounding-and-clarification.md",
    "part03-agent/chapter12-langgraph-state-and-routing.md",
    "part03-agent/chapter13-repair-optimizer-multiturn.md",
    "part04-safety/chapter14-intent-and-sql-guards.md",
    "part04-safety/chapter15-sandbox-limit-timeout.md",
    "part04-safety/chapter16-auth-permission-row-filter.md",
    "part04-safety/chapter17-retry-failure-isolation.md",
    "part04-safety/chapter18-audit-and-observability.md",
    "part05-product/chapter19-query-sse-cache.md",
    "part05-product/chapter20-vue-pinia-workbench.md",
    "part05-product/chapter21-chart-export-audit-ui.md",
    "part05-product/chapter22-docker-nginx-readiness.md",
    "part06-quality/chapter23-test-pyramid.md",
    "part06-quality/chapter24-nl2sql-intent-permission-evaluation.md",
    "part06-quality/chapter25-repair-and-result-correctness.md",
    "part06-quality/chapter26-sharding-checkpoint-aggregation.md",
    "part06-quality/chapter27-github-actions-quality-gate.md",
    "part06-quality/chapter28-mimo-timeout-incident.md",
    "part07-mastery/chapter29-add-business-metric.md",
    "part07-mastery/chapter30-debugging-lab.md",
    "part07-mastery/chapter31-rebuild-mini-agent.md",
    "part07-mastery/chapter32-interview-defense.md",
)
REQUIRED_OVERVIEW_FILES = {
    "README.md",
    "_sidebar.md",
    "index.html",
    "CURRENT-CODE-MAP.md",
    "STUDY-CHECKLIST.md",
    "INTERVIEW-QUESTIONS.md",
    "TROUBLESHOOTING.md",
    "CHANGELOG.md",
}
REQUIRED_CHAPTER_SECTIONS = (
    "学习目标",
    "前置知识",
    "为什么需要",
    "输入、输出与依赖",
    "执行流程",
    "当前代码地图",
    "关键代码理解",
    "最小动手运行",
    "故障注入实验",
    "调试路径与常见误判",
    "独立编码练习",
    "测试或评测验证",
    "面试复述题",
    "掌握度检查与下一章",
)
FORBIDDEN_PLACEHOLDERS = re.compile(
    r"\b(?:TODO|TBD|FIXME)\b|其余类似|剩余同理|后续再补|待完善",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]{16,}|QWEN_API_KEY\s*=\s*[^\s`]+)"
)


def _read(relative_path: str) -> str:
    return (COURSE_ROOT / relative_path).read_text(encoding="utf-8")


def test_v2_course_has_independent_complete_file_layout() -> None:
    assert COURSE_ROOT.is_dir()
    actual_overviews = {path.name for path in COURSE_ROOT.iterdir() if path.is_file()}
    assert REQUIRED_OVERVIEW_FILES <= actual_overviews

    actual_chapters = {
        path.relative_to(COURSE_ROOT).as_posix()
        for path in COURSE_ROOT.glob("part*/chapter*.md")
    }
    assert actual_chapters == set(EXPECTED_CHAPTERS)


def test_v2_sidebar_links_resolve_and_cover_all_chapters() -> None:
    sidebar = _read("_sidebar.md")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", sidebar)
    local_links = {link.split("#", 1)[0] for link in links if not link.startswith("http")}

    for link in local_links:
        assert (COURSE_ROOT / link).is_file(), f"侧边栏链接不存在: {link}"
    assert set(EXPECTED_CHAPTERS) <= local_links


def test_v2_chapters_follow_learning_contract() -> None:
    for relative_path in EXPECTED_CHAPTERS:
        content = _read(relative_path)
        assert content.startswith("# 第"), f"章节一级标题格式错误: {relative_path}"
        for section in REQUIRED_CHAPTER_SECTIONS:
            assert section in content, f"{relative_path} 缺少教学结构: {section}"
        assert "> " in content, f"章节缺少引用块解释: {relative_path}"
        assert content.count("```") % 2 == 0, f"代码围栏没有闭合: {relative_path}"
        assert FORBIDDEN_PLACEHOLDERS.search(content) is None, f"章节包含占位内容: {relative_path}"


def test_v2_markdown_has_no_placeholders_or_sensitive_values() -> None:
    for markdown in COURSE_ROOT.rglob("*.md"):
        content = markdown.read_text(encoding="utf-8")
        assert content.count("```") % 2 == 0, f"代码围栏没有闭合: {markdown}"
        assert FORBIDDEN_PLACEHOLDERS.search(content) is None, f"文档包含占位内容: {markdown}"
        assert SENSITIVE_VALUE.search(content) is None, f"文档疑似包含敏感值: {markdown}"


def test_v2_baseline_is_consistent() -> None:
    for relative_path in ("README.md", "CURRENT-CODE-MAP.md", "CHANGELOG.md"):
        assert BASELINE_SHA in _read(relative_path), f"基线提交不一致: {relative_path}"


def test_v2_code_map_references_existing_project_paths() -> None:
    content = _read("CURRENT-CODE-MAP.md")
    paths = re.findall(
        r"`((?:backend|frontend|database|docs|\.github)/[^`]+?)`",
        content,
    )
    assert paths, "CURRENT-CODE-MAP 必须引用当前项目路径"

    for relative_path in paths:
        target = PROJECT_ROOT / relative_path.rstrip("/")
        assert target.exists(), f"代码地图引用的路径不存在: {relative_path}"


def test_v2_does_not_depend_on_legacy_course() -> None:
    legacy_path = "user_docs/data-analyst-agent-course/"
    for markdown in COURSE_ROOT.rglob("*.md"):
        assert legacy_path not in markdown.read_text(encoding="utf-8")


def test_v2_docsify_entry_enables_reading_features() -> None:
    html = _read("index.html")
    for marker in (
        "loadSidebar: true",
        "search:",
        "pagination:",
        "copyCode:",
        "docsify.min.js",
        "docsify-mermaid",
        'securityLevel: "strict"',
        'lang="zh-CN"',
    ):
        assert marker in html
