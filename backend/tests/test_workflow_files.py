from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def load_workflow(name):
    path = WORKFLOW_DIR / name
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def workflow_triggers(workflow):
    # PyYAML 1.1 会把无引号的 on 解析为布尔值 True。
    return workflow.get("on", workflow.get(True, {}))


def workflow_commands(workflow):
    return "\n".join(
        str(step.get("run", ""))
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    )


def test_base_ci_has_deterministic_pull_request_checks():
    path, workflow = load_workflow("ci.yml")
    raw = path.read_text(encoding="utf-8")
    triggers = workflow_triggers(workflow)
    commands = workflow_commands(workflow)

    assert "pull_request" in triggers
    assert "push" in triggers
    assert workflow["permissions"]["contents"] == "read"
    assert set(workflow["jobs"]) == {
        "backend-tests",
        "backend-tests-pg",
        "docker-image-builds",
        "frontend-build",
        "secret-scan",
    }
    assert "pytest backend/tests -q" in commands
    assert "python -m evaluation.intent_evaluator" in commands
    assert "python -m evaluation.intent_grounding_evaluator" in commands
    assert "python -m evaluation.permission_evaluator --json" in commands
    assert "npm ci" in commands
    assert "npm run build" in commands
    assert "git ls-files -z" in commands
    assert "python -m evaluation.evaluator" not in commands
    assert "MIMO_API_KEY" not in raw
    assert "secrets.QWEN_API_KEY" not in raw
    # 基础 CI 只跑确定性检查；真实模型评测由手动 Real Qwen workflow 承担。
    assert "pull_request_target" not in raw


def test_base_ci_builds_docker_images_from_compose_contexts():
    path, workflow = load_workflow("ci.yml")
    raw = path.read_text(encoding="utf-8")
    job = workflow["jobs"]["docker-image-builds"]
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])

    assert job["name"] == "Docker image builds"
    assert job["runs-on"] == "ubuntu-latest"
    assert any(step.get("uses") == "actions/checkout@v6" for step in job["steps"])
    # 这里锁定 docker-compose.yml 中的真实 build context，避免镜像构建链路只停留在文档承诺。
    assert "docker build -f backend/Dockerfile -t data-analyst-agent-backend:ci ." in commands
    assert (
        "docker build -f frontend/Dockerfile -t data-analyst-agent-frontend:ci ./frontend"
        in commands
    )
    assert "backend/Dockerfile" in raw
    assert "frontend/Dockerfile" in raw


def test_real_qwen_workflow_is_manual_and_uploads_reports_always():
    path, workflow = load_workflow("real-qwen-evaluation.yml")
    raw = path.read_text(encoding="utf-8")
    triggers = workflow_triggers(workflow)
    commands = workflow_commands(workflow)
    job = workflow["jobs"]["real-qwen-evaluation"]
    evaluation_commands = {
        "python -m evaluation.intent_evaluator",
        "python -m evaluation.evaluator",
        "python -m evaluation.repair_evaluator",
        "python -m evaluation.result_correctness_evaluator",
        "python -m evaluation.intent_grounding_evaluator",
        "python -m evaluation.permission_evaluator",
        "python -m evaluation.quality_gate",
    }
    evaluation_steps = [
        step
        for step in job["steps"]
        if any(command in str(step.get("run", "")) for command in evaluation_commands)
    ]
    summary_steps = [
        step for step in job["steps"] if "$GITHUB_STEP_SUMMARY" in str(step.get("run", ""))
    ]
    upload_steps = [
        step
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]

    assert set(triggers) == {"workflow_dispatch"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert {"qwen_model", "enforce_thresholds"} <= set(inputs)
    assert workflow["permissions"]["contents"] == "read"
    assert "secrets.QWEN_API_KEY" in raw
    assert "QWEN_API_KEY" not in job.get("env", {})
    assert "pull_request_target" not in raw
    assert "python -m evaluation.evaluator" in commands
    assert "python -m evaluation.intent_evaluator" in commands
    assert "python -m evaluation.repair_evaluator" in commands
    assert "python -m evaluation.result_correctness_evaluator" in commands
    assert "python -m evaluation.intent_grounding_evaluator" in commands
    assert "python -m evaluation.permission_evaluator --write-report" in commands
    assert "python -m evaluation.quality_gate" in commands
    assert "--correctness-report" in commands
    assert "--intent-grounding-report" in commands
    assert "--permission-report" in commands
    assert "PERMISSION_REPORT=" in commands
    assert "python -m scripts.prepare_evaluation_database" in commands
    assert commands.index("python -m scripts.prepare_evaluation_database") < commands.index(
        "python -m evaluation.evaluator"
    )
    assert commands.index("python -m evaluation.evaluator") < commands.index(
        "python -m evaluation.result_correctness_evaluator"
    )
    assert commands.index(
        "python -m evaluation.result_correctness_evaluator"
    ) < commands.index("python -m evaluation.intent_grounding_evaluator")
    assert commands.index(
        "python -m evaluation.intent_grounding_evaluator"
    ) < commands.index("python -m evaluation.permission_evaluator")
    assert commands.index(
        "python -m evaluation.permission_evaluator"
    ) < commands.index("python -m evaluation.quality_gate")
    # runner.temp 在 job 级 env 尚不可用；报告目录必须等 runner 分配后在 step 级注入。
    assert "EVALUATION_REPORT_DIR" not in job.get("env", {})
    assert all(
        step.get("env", {}).get("EVALUATION_REPORT_DIR")
        == "${{ runner.temp }}/qwen-evaluation"
        for step in [*evaluation_steps, *summary_steps]
    )
    assert "$GITHUB_STEP_SUMMARY" in commands
    assert len(upload_steps) == 1
    assert upload_steps[0]["if"] == "always()"
