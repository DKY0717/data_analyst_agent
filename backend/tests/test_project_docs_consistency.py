from pathlib import Path


ROOT = Path(__file__).parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_backend_test_count_matches_current_claim():
    readme = read_text("README.md")

    assert "后端测试（559 个）" in readme
    assert "tests/             # 559 个测试" in readme
    assert "后端测试（557 个）" not in readme
    assert "后端测试（556 个）" not in readme
    assert "后端测试（553 个）" not in readme
    assert "后端测试（552 个）" not in readme
    assert "后端测试（551 个）" not in readme
    assert "后端测试（547 个）" not in readme
    assert "后端测试（546 个）" not in readme
    assert "后端测试（544 个）" not in readme
    assert "后端测试（543 个）" not in readme
    assert "后端测试（541 个）" not in readme
    assert "后端测试（540 个）" not in readme
    assert "后端测试（534 个）" not in readme
    assert "后端测试（527 个）" not in readme
    assert "tests/             # 557 个测试" not in readme
    assert "tests/             # 556 个测试" not in readme
    assert "tests/             # 484 个测试" not in readme


def test_readme_frontend_test_count_matches_current_claim():
    readme = read_text("README.md")

    assert "前端单元测试（54 个）" in readme
    assert "前端 54 个单元测试" in readme
    assert "前端单元测试（53 个）" not in readme
    assert "前端单元测试（51 个）" not in readme


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


def test_password_login_docs_and_defaults_are_safe():
    readme = read_text("README.md")
    env_example = read_text(".env.example")
    config = read_text("backend/app/config.py")
    auth_router = read_text("backend/app/api/auth_router.py")
    auth = read_text("backend/app/security/auth.py")

    assert "AUTH_PASSWORD_LOGIN_ENABLED" in readme
    assert "# AUTH_PASSWORD_LOGIN_ENABLED=false" in env_example
    assert 'AUTH_PASSWORD_LOGIN_ENABLED: bool = _get_bool("AUTH_PASSWORD_LOGIN_ENABLED", False)' in config
    assert 'admin_pass = "admin123"' not in auth_router
    assert "?api_key=<query_param>" not in auth


def test_llm_service_header_matches_openai_compatible_default():
    llm_service = read_text("backend/app/services/llm_service.py")

    assert "OpenAI-compatible LLM API" in llm_service
    assert "Qwen API (DashScope)" not in llm_service


def test_readiness_endpoint_is_documented_and_used_by_docker_healthcheck():
    readme = read_text("README.md")
    docker_compose = read_text("docker-compose.yml")
    health_api = read_text("backend/app/api/health.py")

    assert "| GET | `/health` | 存活检查 |" in readme
    assert "| GET | `/health/readiness` | 就绪检查（验证数据库连接） |" in readme
    assert "| GET | `/health/cache` | 缓存统计（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| GET | `/health/metrics` | 综合监控指标（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| GET | `/health/ab-tests` | A/B 测试列表（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| POST | `/health/ab-tests` | 创建 A/B 测试（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "http://localhost:8000/health/readiness" in docker_compose
    assert "condition: service_healthy" in docker_compose
    assert "require_management_user" in health_api


def test_cors_defaults_are_localhost_only_and_documented():
    readme = read_text("README.md")
    env_example = read_text(".env.example")
    config = read_text("backend/app/config.py")
    main = read_text("backend/app/main.py")

    assert "CORS_ALLOW_ORIGINS" in readme
    assert "CORS_ALLOW_ORIGINS=" in env_example
    assert "CORS_ALLOW_ORIGINS: list[str]" in config
    assert 'allow_origins=settings.CORS_ALLOW_ORIGINS' in main
    assert 'allow_origins=["*"]' not in main


def test_frontend_docker_proxy_contract_is_documented_and_locked():
    readme = read_text("README.md")
    agent_api = read_text("frontend/src/api/agent.js")
    vite_config = read_text("frontend/vite.config.js")
    nginx_config = read_text("frontend/nginx.conf")
    docker_compose = read_text("docker-compose.yml")

    assert "Docker 前端通过 Nginx 将 `/api` 和 `/health` 同源代理到后端容器" in readme
    assert "baseURL: '/api'" in agent_api
    assert "fetch('/api/chat/query/stream'" in agent_api
    assert "process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'" in vite_config
    assert "location /api/" in nginx_config
    assert "location /health" in nginx_config
    assert "proxy_pass http://backend:8000;" in nginx_config
    assert "condition: service_healthy" in docker_compose


def test_backend_docker_image_bootstraps_persistent_duckdb_demo_database():
    readme = read_text("README.md")
    docker_compose = read_text("docker-compose.yml")
    dockerfile = read_text("backend/Dockerfile")

    assert "Docker 后端启动时会在空 DuckDB 数据卷中自动建表并写入演示数据" in readme
    assert "context: ." in docker_compose
    assert "dockerfile: backend/Dockerfile" in docker_compose
    assert "DATABASE_URL=duckdb:////app/data/database.duckdb" in docker_compose
    assert "WORKDIR /app/backend" in dockerfile
    assert "COPY backend/requirements.txt ./backend/requirements.txt" in dockerfile
    assert "COPY backend ./backend" in dockerfile
    assert "COPY database ./database" in dockerfile
    assert "python -m app.db.demo_bootstrap" in dockerfile
    assert "python -m uvicorn app.main:app" in dockerfile
