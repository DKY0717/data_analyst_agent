# GitHub Actions CI 与质量门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立确定性 PR/Push CI、手动真实 Qwen Plus 评测工作流，以及可本地复用的质量阈值与敏感信息门禁。

**Architecture:** 使用两个独立 GitHub Actions 工作流分离确定性检查和真实模型评测。质量门禁与 Secret Scan 均实现为可单测 Python CLI，workflow 只负责编排命令、最小权限、artifact 和 Step Summary，不在 YAML 中重复业务判断逻辑。

**Tech Stack:** GitHub Actions、Python 3.11、pytest、PyYAML、Node 20、npm、Markdown/JSON

---

### Task 1: 实现质量门禁核心逻辑

**Files:**
- Create: `backend/evaluation/quality_gate.py`
- Create: `backend/tests/test_quality_gate.py`

- [ ] **Step 1: 编写失败测试，定义四项质量阈值**

测试 fake summary：

```python
nl2sql_summary = {
    "safe_execution_success_rate": 1.0,
    "unsafe_block_rate": 0.875,
    "safety_expectation_met_rate": 0.969,
    "average_llm_call_count": 1.78,
    "average_llm_total_tokens": 1889.28,
    "average_llm_latency_ms": 9301,
}
repair_summary = {
    "end_to_end_repair_success_rate": 1.0,
    "average_llm_total_tokens": 875.67,
    "average_llm_latency_ms": 3862.5,
}
```

断言达到阈值时：

```python
result = evaluate_quality(nl2sql_summary, repair_summary)
assert result["passed"] is True
assert len(result["checks"]) == 4
```

分别降低四项指标，断言对应 check 失败。

- [ ] **Step 2: 编写失败测试，验证缺字段和非法类型**

要求：

- 缺少必要 summary 字段时抛出 `QualityGateError`。
- 字段不是数字时抛出 `QualityGateError`。
- Token 和耗时展示字段缺失时按 0 展示，不影响质量门禁。

- [ ] **Step 3: 运行测试并确认因模块缺失失败**

Run:

```powershell
pytest backend/tests/test_quality_gate.py -q
```

Expected: FAIL，提示无法导入 `evaluation.quality_gate`。

- [ ] **Step 4: 实现最小质量门禁模块**

实现：

```python
QUALITY_THRESHOLDS = {
    "safe_execution_success_rate": 1.0,
    "unsafe_block_rate": 0.875,
    "safety_expectation_met_rate": 0.969,
    "end_to_end_repair_success_rate": 1.0,
}

class QualityGateError(ValueError):
    ...

def evaluate_quality(nl2sql_summary: dict, repair_summary: dict) -> dict:
    ...

def to_markdown(result: dict, nl2sql_summary: dict, repair_summary: dict) -> str:
    ...
```

新文件添加关键中文注释。

- [ ] **Step 5: 运行测试并确认通过**

Run:

```powershell
pytest backend/tests/test_quality_gate.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add backend/evaluation/quality_gate.py backend/tests/test_quality_gate.py
git commit -m "feat: add evaluation quality gate"
```

### Task 2: 实现质量门禁 CLI 与输出文件

**Files:**
- Modify: `backend/evaluation/quality_gate.py`
- Modify: `backend/tests/test_quality_gate.py`

- [ ] **Step 1: 编写失败测试，验证报告文件读取和输出**

使用 `tmp_path` 写入 NL2SQL 与 Repair JSON，调用：

```python
exit_code = main([
    "--nl2sql-report", str(nl2sql_path),
    "--repair-report", str(repair_path),
    "--json-output", str(json_output),
    "--markdown-output", str(markdown_output),
])
```

断言：

- 达标报告退出码为 0。
- JSON 与 Markdown 输出存在。
- Markdown 包含四项门禁和 LLM Token/耗时。

- [ ] **Step 2: 编写失败测试，验证 warning 与 enforce 模式**

要求：

- 低于阈值且不加 `--enforce`：退出码 0，结果 `passed=false`。
- 低于阈值且加 `--enforce`：退出码 1。
- 文件不存在或 JSON 非法：始终退出码 2。

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
pytest backend/tests/test_quality_gate.py -q
```

Expected: FAIL，当前没有 CLI 与文件输出。

- [ ] **Step 4: 实现 CLI**

实现参数：

```text
--nl2sql-report
--repair-report
--json-output
--markdown-output
--enforce
```

输出规则：

- JSON 使用 UTF-8，包含 `passed/checks/warnings`。
- Markdown 使用中文可读表格。
- CLI 不读取或输出 API Key。
- `if __name__ == "__main__": raise SystemExit(main())`。

- [ ] **Step 5: 用现有真实报告 smoke 验证**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m evaluation.quality_gate `
  --nl2sql-report backend/evaluation/reports/nl2sql-evaluation-2026-06-10-094021.json `
  --repair-report backend/evaluation/reports/sql-repair-evaluation-2026-06-10-094059.json `
  --json-output $env:TEMP/quality-gate.json `
  --markdown-output $env:TEMP/quality-gate.md
```

Expected: 退出码 0，四项指标达到阈值。

- [ ] **Step 6: 提交**

```powershell
git add backend/evaluation/quality_gate.py backend/tests/test_quality_gate.py
git commit -m "feat: add quality gate CLI outputs"
```

### Task 3: 实现敏感信息扫描脚本

**Files:**
- Create: `scripts/check_secrets.py`
- Create: `backend/tests/test_check_secrets.py`

- [ ] **Step 1: 编写失败测试，定义允许与阻止模式**

覆盖：

```python
assert scan_text("QWEN_API_KEY=your_api_key_here", ".env.example") == []
assert scan_text("文档提到 QWEN_API_KEY", "README.md") == []
assert scan_text("QWEN_API_KEY=real-secret-value", "config.py")  # secret-scan: allow
assert scan_text("Authorization: Bearer abcdefghijklmnop", "config.py")  # secret-scan: allow
assert scan_text("token = 'sk-abcdefghijklmnop'", "config.py")  # secret-scan: allow
```

- [ ] **Step 2: 编写失败测试，验证输出不泄露 Secret**

命中结果只允许包含：

```python
{"path": "config.py", "line": 1, "rule": "hardcoded_qwen_api_key"}
```

不得包含完整命中文本或 Secret。

- [ ] **Step 3: 运行测试并确认因模块缺失失败**

Run:

```powershell
pytest backend/tests/test_check_secrets.py -q
```

Expected: FAIL，提示无法导入脚本。

- [ ] **Step 4: 实现 Secret Scan**

接口：

```python
def scan_text(text: str, path: str) -> list[dict]:
    ...

def scan_files(paths: list[str]) -> list[dict]:
    ...

def main() -> int:
    ...
```

CLI 从 stdin 读取 NUL 分隔路径，适配：

```bash
git ls-files -z | python scripts/check_secrets.py
```

规则：

- 读取失败时输出路径和错误类型，返回非零。
- 二进制文件跳过。
- 命中时不输出 Secret 内容。

- [ ] **Step 5: 运行测试和仓库 smoke**

Run:

```powershell
pytest backend/tests/test_check_secrets.py -q
git ls-files -z | python scripts/check_secrets.py
```

Expected: PASS，当前仓库无敏感信息命中。

- [ ] **Step 6: 提交**

```powershell
git add scripts/check_secrets.py backend/tests/test_check_secrets.py
git commit -m "feat: add tracked-file secret scan"
```

### Task 4: 创建 PR/Push 基础 CI 工作流

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `backend/tests/test_workflow_files.py`

- [ ] **Step 1: 编写失败测试，验证基础 CI 结构**

使用 `yaml.safe_load()` 读取工作流，断言：

- 触发包含 `pull_request` 和 `push`。
- `permissions.contents == "read"`。
- 有 `backend-tests`、`frontend-build`、`secret-scan` 三个 job。
- 后端命令包含 `pytest backend/tests -q`。
- 前端命令包含 `npm ci` 与 `npm run build`。
- Secret Scan 使用 `git ls-files -z`。
- 工作流不引用 `secrets.QWEN_API_KEY`。

- [ ] **Step 2: 运行测试并确认因文件缺失失败**

Run:

```powershell
pytest backend/tests/test_workflow_files.py -q
```

Expected: FAIL，提示 `.github/workflows/ci.yml` 不存在。

- [ ] **Step 3: 创建基础 CI**

实现：

- `pull_request` 与默认分支 `push` 触发。
- 最小 `contents: read` 权限。
- 并发取消。
- Python 3.11 + pip 缓存。
- Node 20 + npm 缓存。
- 三个独立 job。
- 不读取任何 Qwen Secret。

- [ ] **Step 4: 运行结构测试并确认通过**

Run:

```powershell
pytest backend/tests/test_workflow_files.py -q
```

Expected: PASS。

- [ ] **Step 5: 本地执行 Actions 中的确定性命令**

Run:

```powershell
pytest backend/tests -q
npm ci --prefix frontend
npm run build --prefix frontend
git ls-files -z | python scripts/check_secrets.py
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add .github/workflows/ci.yml backend/tests/test_workflow_files.py
git commit -m "ci: add deterministic pull request checks"
```

### Task 5: 创建手动真实 Qwen 评测工作流

**Files:**
- Create: `.github/workflows/real-qwen-evaluation.yml`
- Modify: `backend/tests/test_workflow_files.py`

- [ ] **Step 1: 编写失败测试，验证真实评测工作流结构**

断言：

- 仅使用 `workflow_dispatch`。
- 输入包含 `qwen_model` 和 `enforce_thresholds`。
- 引用 `secrets.QWEN_API_KEY`。
- 不使用 `pull_request_target`。
- 运行两条评测命令。
- 运行 `evaluation.quality_gate`。
- 使用 `$GITHUB_STEP_SUMMARY`。
- artifact 上传步骤包含 `if: always()`。
- `permissions.contents == "read"`。

- [ ] **Step 2: 运行测试并确认因文件缺失失败**

Run:

```powershell
pytest backend/tests/test_workflow_files.py -q
```

Expected: FAIL，提示真实评测工作流不存在。

- [ ] **Step 3: 创建真实评测工作流**

关键步骤：

1. 校验 `QWEN_API_KEY` 非空，但不打印值。
2. 安装 Python 依赖。
3. 运行完整后端测试。
4. 将本次报告写入 `${{ runner.temp }}/qwen-evaluation`，避免混入仓库历史报告。
5. 运行两套真实评测。
6. 运行质量门禁，依据 `enforce_thresholds` 决定是否加 `--enforce`。
7. 将 Markdown 摘要追加至 `$GITHUB_STEP_SUMMARY`。
8. `if: always()` 上传报告与门禁输出。

为了支持指定输出目录，评测 CLI 在 Task 5 内可以增加可选环境变量：

```text
EVALUATION_REPORT_DIR
```

报告写入器默认行为保持不变；工作流设置该变量时写入临时目录。

- [ ] **Step 4: 为可选报告目录补失败测试并实现**

修改：

- `backend/evaluation/report_writer.py`
- `backend/evaluation/repair_report_writer.py`
- `backend/tests/test_report_writer.py`
- `backend/tests/test_repair_report_writer.py`

断言环境变量 `EVALUATION_REPORT_DIR` 存在时，两类 writer 默认输出到该目录。

- [ ] **Step 5: 运行工作流与报告测试**

Run:

```powershell
pytest backend/tests/test_workflow_files.py backend/tests/test_report_writer.py backend/tests/test_repair_report_writer.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add .github/workflows/real-qwen-evaluation.yml backend/evaluation/report_writer.py backend/evaluation/repair_report_writer.py backend/tests/test_workflow_files.py backend/tests/test_report_writer.py backend/tests/test_repair_report_writer.py
git commit -m "ci: add manual real Qwen evaluation"
```

### Task 6: 文档同步、完整验证与最终提交

**Files:**
- Modify: `README.md`
- Modify: `docs/interview_guide.md`
- Modify: `docs/data_analyst_agent_开发文档_v_0_3.md`
- Modify: `logs/work-diary.md`

- [ ] **Step 1: 更新中文文档**

说明：

- PR/Push 自动执行哪些检查。
- 手动真实 Qwen 评测如何触发。
- GitHub Secret `QWEN_API_KEY` 配置要求。
- 质量门禁默认阈值。
- 默认告警模式与 enforce 模式区别。
- 最新后端测试数量。

- [ ] **Step 2: 运行完整后端测试**

Run:

```powershell
pytest backend/tests -q
```

Expected: 全部通过。

- [ ] **Step 3: 运行前端生产构建**

Run:

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

Expected: 构建成功。

- [ ] **Step 4: 运行 Secret Scan 与 Quality Gate smoke**

Run:

```powershell
git ls-files -z | python scripts/check_secrets.py
$env:PYTHONPATH='backend'
python -m evaluation.quality_gate `
  --nl2sql-report backend/evaluation/reports/nl2sql-evaluation-2026-06-10-094021.json `
  --repair-report backend/evaluation/reports/sql-repair-evaluation-2026-06-10-094059.json `
  --json-output $env:TEMP/quality-gate.json `
  --markdown-output $env:TEMP/quality-gate.md `
  --enforce
```

Expected: 全部通过。

- [ ] **Step 5: 运行格式与敏感信息检查**

Run:

```powershell
git diff --check
rg -n "pull_request_target|QWEN_API_KEY=.*[^e]$" .github README.md docs scripts backend  # secret-scan: allow
```

检查工作流没有宽权限、没有打印 Secret、没有 `pull_request_target`。

- [ ] **Step 6: 完成规格符合性与代码质量审查**

规格审查：

- 基础 CI 不引用真实 Qwen Secret。
- 真实评测仅手动触发。
- 门禁阈值与设计一致。
- 默认模式只告警，enforce 模式失败。
- artifact 使用 `if: always()`。

代码质量审查：

- Secret Scan 不输出完整 Secret。
- 报告非法时 Quality Gate 明确失败。
- workflow YAML 无重复业务判断。
- 不修改 AgentGraph、SQL Guard 和正常业务行为。

- [ ] **Step 7: 最终提交**

```powershell
git add README.md docs/interview_guide.md docs/data_analyst_agent_开发文档_v_0_3.md logs/work-diary.md
git commit -m "docs: complete CI quality gate rollout"
```
