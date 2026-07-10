"""零基础学习教程的结构契约测试。"""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COURSE_ROOT = PROJECT_ROOT / "user_docs" / "data-analyst-agent-course"
EXPECTED_CHAPTER_COUNT = 19
REQUIRED_SCAFFOLD_FILES = {
    "README.md",
    "_sidebar.md",
    "index.html",
    "CHANGELOG.md",
    "CODE-MAP.md",
}
REQUIRED_CHAPTER_HEADINGS = {
    "本章目标",
    "问题场景",
    "代码地图",
    "动手验证",
    "常见错误",
    "本章小结",
    "练习",
}
FORBIDDEN_PLACEHOLDERS = re.compile(
    r"\b(?:TODO|TBD|FIXME)\b|其余类似|剩余同理|后续再补",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _chapter_files() -> list[Path]:
    # 只统计正式章文件，避免把首页、映射表和更新日志误计为课程正文。
    return sorted(COURSE_ROOT.glob("part*/chapter*.md"))


def _declared_progress(readme: str) -> tuple[str, int]:
    # 首页进度是读者可见的事实，测试用它约束实际章节数，避免导航提前宣称完成。
    match = re.search(r"课程状态：(建设中|已完成)（(\d+)/19）", readme)
    assert match is not None, "README 必须声明课程状态和已完成章节数"
    return match.group(1), int(match.group(2))


def test_course_scaffold_files_exist() -> None:
    assert COURSE_ROOT.is_dir()
    actual = {path.name for path in COURSE_ROOT.iterdir() if path.is_file()}
    assert REQUIRED_SCAFFOLD_FILES <= actual


def test_readme_progress_matches_existing_chapters() -> None:
    status, declared_count = _declared_progress(_read(COURSE_ROOT / "README.md"))
    actual_count = len(_chapter_files())

    assert declared_count == actual_count
    assert actual_count <= EXPECTED_CHAPTER_COUNT
    if status == "已完成":
        assert actual_count == EXPECTED_CHAPTER_COUNT
    else:
        assert actual_count < EXPECTED_CHAPTER_COUNT


def test_sidebar_local_links_resolve() -> None:
    sidebar = _read(COURSE_ROOT / "_sidebar.md")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", sidebar)
    assert links, "侧边栏至少应包含课程首页链接"

    for link in links:
        if link.startswith(("http://", "https://", "#")):
            continue
        target = (COURSE_ROOT / link.split("#", 1)[0]).resolve()
        assert target.is_file(), f"侧边栏链接不存在: {link}"


def test_existing_chapters_follow_learning_template() -> None:
    for chapter in _chapter_files():
        content = _read(chapter)
        assert content.startswith("# "), f"章节缺少一级标题: {chapter}"
        for heading in REQUIRED_CHAPTER_HEADINGS:
            assert heading in content, f"{chapter} 缺少章节结构: {heading}"
        assert content.count("```") % 2 == 0, f"代码围栏没有闭合: {chapter}"
        assert FORBIDDEN_PLACEHOLDERS.search(content) is None, f"章节包含占位内容: {chapter}"


def test_course_markdown_has_no_forbidden_placeholders_or_broken_fences() -> None:
    for markdown in COURSE_ROOT.rglob("*.md"):
        content = _read(markdown)
        assert FORBIDDEN_PLACEHOLDERS.search(content) is None, f"文档包含占位内容: {markdown}"
        assert content.count("```") % 2 == 0, f"代码围栏没有闭合: {markdown}"


def test_code_map_references_existing_project_paths() -> None:
    content = _read(COURSE_ROOT / "CODE-MAP.md")
    # 只提取以项目一级目录开头的反引号路径，命令和通配目录不参与存在性判断。
    paths = re.findall(
        r"`((?:backend|frontend|database|docs|scripts|\.github)/[^`]+?)`",
        content,
    )
    assert paths, "CODE-MAP 必须引用真实项目路径"

    for relative_path in paths:
        if relative_path.endswith("/"):
            target = PROJECT_ROOT / relative_path.rstrip("/")
        else:
            target = PROJECT_ROOT / relative_path
        assert target.exists(), f"CODE-MAP 引用的路径不存在: {relative_path}"


def test_docsify_entry_enables_required_reading_features() -> None:
    html = _read(COURSE_ROOT / "index.html")
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
