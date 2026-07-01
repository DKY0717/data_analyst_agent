import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "interview_evidence.py"
SPEC = importlib.util.spec_from_file_location("interview_evidence", SCRIPT_PATH)
interview_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(interview_evidence)


def test_build_evidence_checklist_includes_local_and_remote_evidence_commands():
    markdown = interview_evidence.build_evidence_checklist()

    assert "# Data Analyst Agent 面试证据包" in markdown
    assert "pytest backend -q" in markdown
    assert "npm run test:e2e --prefix frontend" in markdown
    assert "python -m evaluation.security_audit_exporter --write-report" in markdown
    assert "gh run list --workflow real-qwen-evaluation.yml" in markdown
    assert "security-audit-*.md/json" in markdown


def test_build_evidence_checklist_with_run_id_includes_download_command():
    markdown = interview_evidence.build_evidence_checklist(run_id="28518980982")

    assert "gh run view 28518980982 --json status,conclusion,url" in markdown
    assert "gh run download 28518980982" in markdown
    assert "real-qwen-evaluation-28518980982" in markdown
    assert "artifacts/real-qwen-evaluation-28518980982" in markdown


def test_build_evidence_checklist_uses_custom_artifact_dir():
    markdown = interview_evidence.build_evidence_checklist(
        run_id="123",
        artifact_dir="tmp/evidence",
    )

    assert "--dir tmp/evidence" in markdown
    assert "tmp/evidence" in markdown


def test_main_writes_markdown_output(tmp_path):
    output_path = tmp_path / "evidence.md"

    exit_code = interview_evidence.main(
        ["--run-id", "123", "--output", str(output_path)]
    )

    assert exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "gh run download 123" in markdown
    assert "面试证据包" in markdown
