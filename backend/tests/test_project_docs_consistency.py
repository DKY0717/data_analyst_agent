from pathlib import Path


ROOT = Path(__file__).parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_backend_test_count_matches_current_claim():
    readme = read_text("README.md")

    assert "后端测试（527 个）" in readme
    assert "tests/             # 527 个测试" in readme
    assert "tests/             # 484 个测试" not in readme


def test_llm_provider_docs_and_defaults_are_consistent():
    env_example = read_text(".env.example")
    docker_compose = read_text("docker-compose.yml")
    config = read_text("backend/app/config.py")
    agents = read_text("AGENTS.md")

    assert "QWEN_MODEL=mimo-v2.5-pro" in env_example
    assert "QWEN_MODEL=${QWEN_MODEL:-mimo-v2.5-pro}" in docker_compose
    assert 'QWEN_MODEL: str = os.getenv("QWEN_MODEL", "mimo-v2.5-pro")' in config
    assert "OpenAI-compatible LLM API" in agents
    assert "mimo-v2.5-pro" in agents
    assert "defaults to `qwen-turbo`" not in agents


def test_setup_docs_use_repeatable_seed_command_from_repo_root():
    agents = read_text("AGENTS.md")
    readme = read_text("README.md")

    assert "python -m database.seed_data" in agents
    assert "cd backend\npython -m database.seed_data" not in agents
    assert "python ../database/seed_data.py" in readme
