"""生成可审计的真实模型评测运行元数据。"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from evaluation.core_path import CorePathCaseLoader


def build_run_metadata(
    *,
    provider: str,
    api_url: str,
    model: str,
    head_sha: str,
    generated_at: str | None = None,
) -> dict[str, str]:
    """只记录可公开的运行身份，不保存 API Key、查询或模型原始响应。"""
    parsed_url = urlsplit(api_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("api_url must be an absolute HTTP(S) URL")
    host = parsed_url.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parsed_url.port}" if parsed_url.port else host
    endpoint = f"{parsed_url.scheme}://{netloc}{parsed_url.path}"
    return {
        "head_sha": head_sha.strip(),
        "provider": provider.strip().lower(),
        "model": model.strip(),
        "api_endpoint": endpoint,
        "case_version": CorePathCaseLoader().load_version(),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
    }


def write_metadata(
    metadata: dict[str, str],
    json_output: str | Path,
    markdown_output: str | Path,
) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        "\n".join(
            [
                "# Real LLM Evaluation Metadata",
                "",
                f"- HEAD SHA: `{metadata['head_sha']}`",
                f"- Provider: `{metadata['provider']}`",
                f"- Model: `{metadata['model']}`",
                f"- API endpoint: `{metadata['api_endpoint']}`",
                f"- Case version: `{metadata['case_version']}`",
                f"- Generated at: `{metadata['generated_at']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成真实模型评测元数据")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "unknown"))
    parser.add_argument("--api-url", default=os.getenv("QWEN_API_URL", ""))
    parser.add_argument("--model", default=os.getenv("QWEN_MODEL", ""))
    parser.add_argument(
        "--head-sha",
        default=os.getenv("EVALUATION_HEAD_SHA", os.getenv("GITHUB_SHA", "local")),
    )
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    args = parser.parse_args(argv)

    if not args.provider.strip() or not args.api_url.strip() or not args.model.strip():
        return 2
    try:
        metadata = build_run_metadata(
            provider=args.provider,
            api_url=args.api_url,
            model=args.model,
            head_sha=args.head_sha,
        )
    except ValueError:
        return 2
    write_metadata(metadata, args.json_output, args.markdown_output)
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
