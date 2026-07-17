from pathlib import Path


ROOT = Path(__file__).parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_backend_test_count_matches_current_claim():
    readme = read_text("README.md")

    assert "后端测试（678 个）" in readme
    assert "tests/             # 678 个测试" in readme
    assert "后端测试（595 个）" not in readme
    assert "tests/             # 595 个测试" not in readme
    assert "后端测试（587 个）" not in readme
    assert "tests/             # 587 个测试" not in readme
    assert "后端测试（586 个）" not in readme
    assert "tests/             # 586 个测试" not in readme
    assert "后端测试（581 个）" not in readme
    assert "tests/             # 581 个测试" not in readme
    assert "后端测试（576 个）" not in readme
    assert "tests/             # 576 个测试" not in readme
    assert "后端测试（577 个）" not in readme
    assert "tests/             # 577 个测试" not in readme
    assert "后端测试（575 个）" not in readme
    assert "tests/             # 575 个测试" not in readme
    assert "后端测试（573 个）" not in readme
    assert "tests/             # 573 个测试" not in readme
    assert "后端测试（571 个）" not in readme
    assert "tests/             # 571 个测试" not in readme
    assert "后端测试（569 个）" not in readme
    assert "tests/             # 569 个测试" not in readme
    assert "后端测试（567 个）" not in readme
    assert "后端测试（565 个）" not in readme
    assert "后端测试（563 个）" not in readme
    assert "后端测试（561 个）" not in readme
    assert "后端测试（559 个）" not in readme
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
    assert "tests/             # 567 个测试" not in readme
    assert "tests/             # 565 个测试" not in readme
    assert "tests/             # 563 个测试" not in readme
    assert "tests/             # 561 个测试" not in readme
    assert "tests/             # 559 个测试" not in readme
    assert "tests/             # 557 个测试" not in readme
    assert "tests/             # 556 个测试" not in readme
    assert "tests/             # 484 个测试" not in readme


def test_readme_frontend_test_count_matches_current_claim():
    readme = read_text("README.md")

    assert "前端单元测试（58 个）" in readme
    assert "前端 58 个单元测试" in readme
    assert "前端单元测试（54 个）" not in readme
    assert "前端 54 个单元测试" not in readme
    assert "前端单元测试（53 个）" not in readme


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
    assert "| GET | `/health/readiness` | 就绪检查（验证数据库连接、核心业务表和关键数据） |" in readme
    assert "| GET | `/health/cache` | 缓存统计（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| GET | `/health/metrics` | 综合监控指标（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| GET | `/health/ab-tests` | A/B 测试列表（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "| POST | `/health/ab-tests` | 创建 A/B 测试（启用认证时需 admin JWT 或 API Key） |" in readme
    assert "http://localhost:8000/health/readiness" in docker_compose
    assert "condition: service_healthy" in docker_compose
    assert "REQUIRED_BUSINESS_TABLES" in health_api
    assert "REQUIRED_NON_EMPTY_TABLES" in health_api
    assert "_assert_business_database_ready" in health_api
    assert "row_counts" in health_api
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


def test_readme_documents_ci_docker_image_builds():
    readme = read_text("README.md")
    ci_workflow = read_text(".github/workflows/ci.yml")

    assert "基础 CI 会真实构建后端和前端 Docker 镜像" in readme
    assert "docker-image-builds:" in ci_workflow
    assert "docker build -f backend/Dockerfile -t data-analyst-agent-backend:ci ." in ci_workflow
    assert (
        "docker build -f frontend/Dockerfile -t data-analyst-agent-frontend:ci ./frontend"
        in ci_workflow
    )


def test_readme_documents_ci_docker_compose_config_validation():
    readme = read_text("README.md")
    ci_workflow = read_text(".github/workflows/ci.yml")

    assert "基础 CI 会校验 Docker Compose 编排配置" in readme
    assert "docker compose -f docker-compose.yml config" in ci_workflow


def test_readme_documents_ci_backend_container_smoke_test():
    readme = read_text("README.md")
    ci_workflow = read_text(".github/workflows/ci.yml")

    assert "基础 CI 会启动后端容器并请求 `/health/readiness` 做 smoke test" in readme
    assert "Smoke test backend container readiness" in ci_workflow
    assert "docker compose -f docker-compose.yml up -d backend" in ci_workflow
    assert "curl --fail --silent http://localhost:8000/health/readiness" in ci_workflow
    assert "docker compose -f docker-compose.yml down -v" in ci_workflow


def test_readme_documents_ci_frontend_unit_tests():
    readme = read_text("README.md")
    ci_workflow = read_text(".github/workflows/ci.yml")

    assert "基础 CI 会运行前端单元测试和前端生产构建" in readme
    assert "npm run test --prefix frontend" in ci_workflow
    assert "npm run build --prefix frontend" in ci_workflow


def test_readme_documents_ci_frontend_e2e_tests():
    readme = read_text("README.md")
    ci_workflow = read_text(".github/workflows/ci.yml")

    assert "基础 CI 会运行 Playwright 前端 E2E 测试" in readme
    assert "frontend-e2e:" in ci_workflow
    assert "npm exec --prefix frontend playwright install --with-deps chromium" in ci_workflow
    assert "npm run test:e2e --prefix frontend" in ci_workflow


def test_security_audit_export_docs_explain_default_and_strict_modes():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")

    for document in (readme, guide, packet):
        assert "未提供真实评测输入" in document
        assert "--fail-on-missing-real-reports" in document

    assert "输入完整性" in readme
    assert "严格交付检查" in readme
    assert "security-audit-*.md" in packet


def test_real_model_workflow_docs_include_strict_auditable_artifact():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")
    workflow = read_text(".github/workflows/real-qwen-evaluation.yml")

    assert "python -m evaluation.security_audit_exporter" in workflow
    assert "--fail-on-missing-real-reports" in workflow
    assert "security-audit-*.md/json" in readme
    assert "真实模型 workflow" in readme
    assert "security-audit-*.md/json" in guide
    assert "真实模型 workflow" in guide
    assert "security-audit-*.md/json" in packet
    assert "真实模型 workflow" in packet


def test_interview_evidence_script_is_documented():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")
    script = read_text("scripts/interview_evidence.py")

    for document in (readme, guide, packet):
        assert "python scripts/interview_evidence.py" in document
        assert "--run-id <github_run_id>" in document

    assert "build_evidence_checklist" in script
    assert "security-audit-*.md/json" in script


def test_interview_demo_preflight_script_is_documented():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")
    script = read_text("scripts/interview_demo_preflight.py")

    for document in (readme, guide, packet):
        assert "python scripts/interview_demo_preflight.py --strict" in document
        assert "面试演示预检" in document

    assert "evaluate_preflight" in script
    assert "AUTH_DEMO_ENABLED=true" in script
    assert "JWT_SECRET" in script


def test_core_path_polish_docs_are_documented():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")
    core_cases = read_text("backend/evaluation/cases/core_path_cases.yaml")
    preflight = read_text("scripts/interview_demo_preflight.py")

    for document in (readme, guide, packet):
        assert "core_path_cases.yaml" in document
        assert "python -m evaluation.core_path_runner" in document
        assert "核心路径" in document

    assert "monthly_sales_demo" in core_cases
    assert "dangerous_delete_demo" in core_cases
    assert "删除订单表" in preflight


def test_interview_guide_matches_current_project_evidence():
    guide = read_text("docs/interview_guide.md")

    assert "678 个后端测试" in guide
    assert "v1.8" in guide
    assert "HTTP transport/结构化解析" in guide
    assert "58 个前端单测" in guide
    assert "17 个 E2E" in guide
    assert "前端单元测试" in guide
    assert "Playwright 前端 E2E" in guide
    assert "demo/secure Compose" in guide
    assert "readiness smoke" in guide
    assert "15 条可执行核心路径" in guide
    assert "595 个后端测试" not in guide
    assert "54 个前端单测" not in guide
    assert "587 个后端测试" not in guide
    assert "586 个后端测试" not in guide
    assert "581 个后端测试" not in guide
    assert "576 个后端测试" not in guide
    assert "577 个后端测试" not in guide
    assert "575 个后端测试" not in guide
    assert "573 个后端测试" not in guide
    assert "556 个后端测试" not in guide
    assert "571 个后端测试" not in guide


def test_resume_packet_matches_current_project_evidence():
    packet = read_text("docs/resume_project_packet.md")

    assert "678 个后端测试" in packet
    assert "58 个前端单测" in packet
    assert "17 个 E2E" in packet
    assert "Playwright 前端 E2E" in packet
    assert "demo/secure Compose" in packet
    assert "readiness smoke" in packet
    assert "15 条可执行核心路径" in packet
    assert "595 个后端测试" not in packet
    assert "54 个前端单测" not in packet
    assert "587 个后端测试" not in packet
    assert "586 个后端测试" not in packet
    assert "581 个后端测试" not in packet
    assert "576 个后端测试" not in packet
    assert "577 个后端测试" not in packet
    assert "575 个后端测试" not in packet
    assert "573 个后端测试" not in packet
    assert "556 个后端测试" not in packet
    assert "571 个后端测试" not in packet


def test_v17_docs_define_migration_secure_profile_and_quality_boundaries():
    readme = read_text("README.md")
    guide = read_text("docs/interview_guide.md")
    packet = read_text("docs/resume_project_packet.md")
    development = read_text("docs/data_analyst_agent_开发文档_v_1_7.md")

    assert "Alembic 只管理 PostgreSQL" in readme
    assert "docker-compose.secure.yml" in readme
    assert "75% 覆盖率门槛" in readme
    assert "81.10%" in readme
    assert "HEAD SHA" in guide
    assert "DuckDB 用固定脚本重建" in guide
    assert "Alembic 只管理 PostgreSQL" in packet
    assert development.count("python -m alembic -c backend/alembic.ini upgrade head") == 2
    assert "python -m alembic -c backend/alembic.ini downgrade base" in development
    assert "确定性测试通过不等于真实模型" in development
