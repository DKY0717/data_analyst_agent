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
    assert set(workflow["jobs"]) == {"backend-tests", "frontend-build", "secret-scan"}
    assert "pytest backend/tests -q" in commands
    assert "npm ci" in commands
    assert "npm run build" in commands
    assert "git ls-files -z" in commands
    assert "secrets.QWEN_API_KEY" not in raw
    assert "pull_request_target" not in raw
