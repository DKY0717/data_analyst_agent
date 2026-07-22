"""真实模型运行元数据测试。"""

import json

from evaluation.run_metadata import build_run_metadata, main


def test_metadata_binds_commit_provider_model_endpoint_case_version_and_time():
    metadata = build_run_metadata(
        provider="MiMo",
        api_url=(
            "https://user:password@example.test/v1/chat/completions"
            "?token=must-not-persist"
        ),
        model="mimo-v2.5-pro",
        head_sha="abc123",
        generated_at="2026-07-10T12:00:00+00:00",
    )

    assert metadata == {
        "head_sha": "abc123",
        "provider": "mimo",
        "model": "mimo-v2.5-pro",
        "api_endpoint": "https://example.test/v1/chat/completions",
        "case_version": "1.7",
        "generated_at": "2026-07-10T12:00:00+00:00",
    }
    assert "token" not in repr(metadata)
    assert "password" not in repr(metadata)


def test_metadata_cli_writes_json_and_markdown(tmp_path, capsys):
    json_path = tmp_path / "run-metadata.json"
    markdown_path = tmp_path / "run-metadata.md"

    exit_code = main(
        [
            "--provider",
            "qwen",
            "--api-url",
            "https://dashscope.example/v1/chat/completions",
            "--model",
            "qwen-plus",
            "--head-sha",
            "deadbeef",
            "--json-output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8"))["head_sha"] == "deadbeef"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Provider: `qwen`" in markdown
    assert "Model: `qwen-plus`" in markdown
    assert json.loads(capsys.readouterr().out)["case_version"] == "1.7"


def test_metadata_cli_rejects_non_http_endpoint(tmp_path):
    exit_code = main(
        [
            "--provider",
            "custom",
            "--api-url",
            "file:///private/config",
            "--model",
            "model",
            "--json-output",
            str(tmp_path / "metadata.json"),
            "--markdown-output",
            str(tmp_path / "metadata.md"),
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "metadata.json").exists()
