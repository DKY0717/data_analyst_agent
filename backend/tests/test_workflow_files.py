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
    assert "python -m evaluation.intent_evaluator" in commands
    assert "npm ci" in commands
    assert "npm run build" in commands
    assert "git ls-files -z" in commands
    assert "secrets.QWEN_API_KEY" not in raw
    assert "pull_request_target" not in raw


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
    assert "python -m evaluation.quality_gate" in commands
    assert "python scripts/prepare_evaluation_database.py" in commands
    assert commands.index("python scripts/prepare_evaluation_database.py") < commands.index(
        "python -m evaluation.evaluator"
    )
    assert commands.index("python -m evaluation.evaluator") < commands.index(
        "python -m evaluation.result_correctness_evaluator"
    )
    assert commands.index(
        "python -m evaluation.result_correctness_evaluator"
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
