import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "check_secrets.py"
SPEC = importlib.util.spec_from_file_location("check_secrets", SCRIPT_PATH)
check_secrets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_secrets)
scan_files = check_secrets.scan_files
scan_text = check_secrets.scan_text


def test_scan_text_allows_placeholders_and_variable_mentions():
    assert scan_text("QWEN_API_KEY=your_api_key_here", ".env.example") == []
    assert scan_text("文档提到 QWEN_API_KEY", "README.md") == []
    assert scan_text("QWEN_API_KEY=${QWEN_API_KEY}", "docker-compose.yml") == []
    assert scan_text("QWEN_API_KEY=replace-me-secure-profile", "ci.yml") == []
    assert scan_text("QWEN_API_KEY=你的密钥", "guide.md") == []
    assert scan_text("printf 'QWEN_API_KEY=%s' \"$API_KEY\"", "ci.yml") == []
    assert (
        scan_text(
            'QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")',
            "config.py",
        )
        == []
    )


def test_scan_text_detects_supported_secret_patterns():
    assert scan_text("QWEN_API_KEY=real-secret-value", "config.py") == [  # secret-scan: allow
        {"path": "config.py", "line": 1, "rule": "hardcoded_qwen_api_key"}
    ]
    assert scan_text("Authorization: Bearer abcdefghijklmnop", "config.py") == [  # secret-scan: allow
        {"path": "config.py", "line": 1, "rule": "bearer_token"}
    ]
    assert scan_text("token = 'sk-abcdefghijklmnop'", "config.py") == [  # secret-scan: allow
        {"path": "config.py", "line": 1, "rule": "sk_token"}
    ]


def test_scan_text_rejects_non_placeholder_unicode_secret():
    assert scan_text("QWEN_API_KEY=真实密钥甲乙丙丁", "config.py") == [  # secret-scan: allow
        {"path": "config.py", "line": 1, "rule": "hardcoded_qwen_api_key"}
    ]


def test_scan_text_honors_explicit_line_allow_marker():
    text = "QWEN_API_KEY=example-for-test  # secret-scan: allow"  # secret-scan: allow

    assert scan_text(text, "example.py") == []


def test_scan_files_does_not_return_secret_content(tmp_path):
    secret = "never-print-this-secret-value"
    source = tmp_path / "config.py"
    source.write_text(f"QWEN_API_KEY={secret}", encoding="utf-8")  # secret-scan: allow

    findings = scan_files([str(source)])

    assert findings == [
        {
            "path": str(source),
            "line": 1,
            "rule": "hardcoded_qwen_api_key",
        }
    ]
    assert secret not in repr(findings)


def test_scan_files_skips_binary_files(tmp_path):
    binary = tmp_path / "image.bin"
    binary.write_bytes(b"\x00QWEN_API_KEY=hidden-in-binary")  # secret-scan: allow

    assert scan_files([str(binary)]) == []


def test_scan_files_skips_paths_deleted_from_worktree(tmp_path):
    assert scan_files([str(tmp_path / "deleted.txt")]) == []
