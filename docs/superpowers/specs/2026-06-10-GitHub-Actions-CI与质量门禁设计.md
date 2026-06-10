# GitHub Actions CI 与质量门禁设计

## 1. 背景

当前项目已经具备：

- 124 个后端 pytest 用例。
- 可重复的前端生产构建。
- 32 条 NL2SQL 真实评测 case。
- 6 条确定性 SQL Repair 故障注入 case。
- Qwen Plus Token、耗时和安全指标基线。

但这些验证仍依赖开发者手动运行，代码提交后无法自动证明测试、前端构建和安全边界没有回退。同时，真实 Qwen 评测耗时约 5 分钟、会产生 API 成本，并且模型输出存在随机波动，不适合在每次 PR 中自动阻塞合并。

因此需要建立两层 GitHub Actions：

1. 免费、确定性、必须通过的 PR/Push CI。
2. 使用真实 Qwen Plus、手动触发、输出质量告警但不阻塞普通 PR 的评测工作流。

## 2. 目标

1. PR 和 Push 自动运行后端测试、前端构建与敏感信息扫描。
2. 确定性 CI 失败时阻塞合并。
3. 真实 Qwen Plus 评测仅手动触发，避免每次提交消耗 API 额度。
4. 真实评测生成的 Markdown/JSON 报告作为 GitHub Actions artifact 上传。
5. 在 GitHub Step Summary 中展示核心质量、Token 与耗时指标。
6. 使用独立质量门禁脚本判断报告是否低于基线阈值。
7. 真实评测低于阈值时输出清晰警告，但工作流不阻塞普通 PR。

## 3. 非目标

1. 不在 PR 自动工作流中调用真实 Qwen API。
2. 不把 `QWEN_API_KEY` 写入仓库、日志或 artifact。
3. 不自动创建、修改或读取 GitHub Secret。
4. 不实现部署、发布或 Docker 镜像推送。
5. 不在第一版加入跨 Python/Node 多版本测试矩阵。
6. 不因为一次真实 LLM 随机波动自动回滚代码。

## 4. 方案选择

### 4.1 采用方案：两个独立工作流

```text
PR / Push
  -> ci.yml
     -> Backend Tests
     -> Frontend Build
     -> Secret Scan
     -> 必须通过

Manual workflow_dispatch
  -> real-qwen-evaluation.yml
     -> Qwen Plus NL2SQL Evaluation
     -> Qwen Plus Repair Evaluation
     -> Quality Gate
     -> Upload Reports
     -> Step Summary / Warning
```

采用两个工作流可以清晰分离：

- 确定性验证与随机模型评测。
- 免费任务与产生 API 成本的任务。
- 必须阻塞的失败与只需告警的指标波动。

### 4.2 未采用方案

1. **单一工作流条件分支**：文件更少，但 Secret 权限、失败语义和日志不够清晰。
2. **每个 PR 都运行真实 Qwen**：回归发现及时，但费用、耗时和随机性不适合当前项目。
3. **只运行 pytest，不做前端与敏感信息检查**：无法证明完整工程质量。

## 5. 基础 CI 工作流

### 5.1 文件

```text
.github/workflows/ci.yml
```

### 5.2 触发条件

- `pull_request`
- 向默认分支 Push

### 5.3 权限

工作流使用最小权限：

```yaml
permissions:
  contents: read
```

不授予写仓库、写 PR、访问部署环境等权限。

### 5.4 并发取消

同一 PR 或分支有新提交时，取消旧运行：

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### 5.5 Backend Tests Job

环境：

- `ubuntu-latest`
- Python `3.11`
- pip 缓存基于 `backend/requirements.txt`

步骤：

1. Checkout。
2. Setup Python。
3. 安装 `backend/requirements.txt`。
4. 运行：

```bash
pytest backend/tests -q
```

该 job 不配置 `QWEN_API_KEY`，用于证明所有自动测试不依赖真实模型。

### 5.6 Frontend Build Job

环境：

- `ubuntu-latest`
- Node `20`
- npm 缓存基于 `frontend/package-lock.json`

步骤：

```bash
cd frontend
npm ci
npm run build
```

### 5.7 Secret Scan Job

使用仓库脚本扫描 Git 跟踪文件，不扫描 `.env`、`node_modules`、构建产物和未跟踪本地文件。

第一版检测模式：

- `QWEN_API_KEY=` 后跟非占位值。<!-- secret-scan: allow -->
- `Authorization: Bearer`。
- 常见 `sk-` 格式密钥。
- DashScope API Key 的明显硬编码模式。

`.env.example` 中的 `your_api_key_here` 必须允许通过。

扫描命中时：

1. 输出文件路径和规则名称。
2. 不输出完整疑似密钥内容。
3. 返回非零退出码，阻塞 PR。

## 6. 真实 Qwen Plus 评测工作流

### 6.1 文件

```text
.github/workflows/real-qwen-evaluation.yml
```

### 6.2 触发条件

仅允许：

```yaml
workflow_dispatch
```

支持可选输入：

- `qwen_model`：默认 `qwen-plus`。
- `enforce_thresholds`：默认 `false`。

`enforce_thresholds=false` 时，指标低于阈值只告警；设置为 `true` 时，质量门禁失败会使手动工作流失败，适合版本发布前使用。

### 6.3 Secret 与权限

环境变量：

```yaml
QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
QWEN_MODEL: ${{ inputs.qwen_model }}
```

规则：

1. Secret 缺失时立即失败，并提示管理员配置 Secret。
2. 工作流日志不得打印 Secret。
3. artifact 不得包含 `.env`。
4. 权限仍为 `contents: read`。

### 6.4 执行流程

1. Checkout。
2. Setup Python 3.11。
3. 安装后端依赖。
4. 运行完整后端测试。
5. 清理本次工作区内旧的临时评测输出目录。
6. 运行：

```bash
cd backend
python -m evaluation.evaluator
python -m evaluation.repair_evaluator
```

7. 找到本次最新 NL2SQL 与 Repair JSON/Markdown 报告。
8. 运行质量门禁脚本。
9. 把核心指标写入 `$GITHUB_STEP_SUMMARY`。
10. 无论门禁是否告警，上传本次四个报告 artifact。

### 6.5 Artifact

Artifact 名称包含：

- 模型名。
- Git commit 短 SHA。
- 工作流 run number。

Artifact 只包含本次生成的：

- NL2SQL JSON。
- NL2SQL Markdown。
- Repair JSON。
- Repair Markdown。
- 质量门禁 JSON 摘要。

## 7. 质量门禁脚本

### 7.1 文件

```text
backend/evaluation/quality_gate.py
backend/tests/test_quality_gate.py
```

### 7.2 职责

1. 读取 NL2SQL 和 Repair JSON 报告。
2. 校验必要 summary 字段存在且类型合法。
3. 使用固定阈值判断核心指标。
4. 输出结构化 JSON 摘要。
5. 输出适合 GitHub Step Summary 的 Markdown。
6. 根据 CLI 参数决定只告警还是返回非零退出码。

脚本只读取已有报告，不调用 LLM。

### 7.3 默认阈值

阈值取自 2026-06-10 真实 Qwen Plus 基线：

| 指标 | 默认阈值 |
|---|---:|
| 正常分析执行成功率 | `>= 1.0` |
| 危险请求阻断率 | `>= 0.875` |
| 安全预期命中率 | `>= 31/32（0.96875）` |
| Repair 端到端成功率 | `>= 1.0` |

说明：

- 阈值通过代码常量或明确配置定义，并有单元测试。
- 降低阈值必须显式修改代码和测试，不能在 workflow YAML 中悄悄覆盖。
- 第一版不对 Token 和耗时设置失败阈值，只在 Summary 展示，因为真实网络与模型延迟波动较大。

### 7.4 输出结构

JSON 示例：

```json
{
  "passed": false,
  "checks": [
    {
      "metric": "unsafe_block_rate",
      "actual": 0.75,
      "threshold": 0.875,
      "passed": false
    }
  ],
  "warnings": [
    "危险请求阻断率低于基线阈值"
  ]
}
```

Markdown Summary 包含：

- commit、模型名和运行时间。
- 四项质量门禁指标。
- NL2SQL 平均调用数、Token、LLM 耗时。
- Repair 平均 Token、LLM 耗时。
- 未通过项目与处理建议。

### 7.5 CLI

建议接口：

```bash
python -m evaluation.quality_gate \
  --nl2sql-report path/to/nl2sql.json \
  --repair-report path/to/repair.json \
  --json-output path/to/quality-gate.json \
  --markdown-output path/to/quality-gate.md \
  --enforce
```

规则：

- 默认不加 `--enforce`：低于阈值时输出警告但退出码为 0。
- 加 `--enforce`：低于阈值或报告非法时退出码非 0。
- 报告文件不存在或 JSON 非法时始终退出非 0，因为无法完成评测。

## 8. 敏感信息扫描脚本

### 8.1 文件

```text
scripts/check_secrets.py
backend/tests/test_check_secrets.py
```

### 8.2 设计

脚本接收待扫描文件列表。GitHub Actions 使用：

```bash
git ls-files -z | python scripts/check_secrets.py
```

这样只扫描 Git 跟踪文件，不会读取 CI Secret、`.env` 或本地未跟踪文件。

脚本输出：

- 命中文件路径。
- 规则名称。
- 行号。

脚本不输出完整命中文本，避免 Secret 再次进入日志。

### 8.3 排除与允许值

允许：

- `.env.example` 中的 `QWEN_API_KEY=your_api_key_here`。<!-- secret-scan: allow -->
- 文档中仅出现变量名 `QWEN_API_KEY`。
- 文档中作为说明出现 `Authorization` 或 `Bearer` 单词，但没有真实凭据。

阻止：

- `QWEN_API_KEY=` 后出现非占位值。<!-- secret-scan: allow -->
- `Authorization: Bearer <token>`。
- 疑似真实 `sk-...` Token。

## 9. 测试策略

### 9.1 Quality Gate 测试

使用固定 fake 报告覆盖：

1. 所有指标达到阈值。
2. 正常分析执行率下降。
3. 危险请求阻断率下降。
4. Repair 成功率下降。
5. 缺少必要 summary 字段。
6. JSON 文件非法。
7. 默认告警模式退出成功。
8. `--enforce` 模式返回失败。
9. Markdown 与 JSON 输出包含正确指标。

### 9.2 Secret Scan 测试

覆盖：

1. `.env.example` 占位值允许通过。
2. 文档中变量名允许通过。
3. 硬编码 Qwen API Key 被拦截。
4. Bearer Token 被拦截。
5. `sk-` Token 被拦截。
6. 输出不包含完整 Secret。

### 9.3 Workflow 验证

1. 使用 YAML 解析器验证两个工作流语法。
2. 本地运行 workflow 中的后端测试命令。
3. 本地运行 workflow 中的前端构建命令。
4. 本地运行 Secret Scan。
5. 使用现有真实报告验证质量门禁告警模式与 enforce 模式。

## 10. 错误处理

1. 后端测试或前端构建失败：基础 CI 失败并阻塞 PR。
2. Secret Scan 命中：基础 CI 失败，但日志不输出 Secret。
3. 手动真实评测缺少 Secret：工作流立即失败。
4. Qwen 调用失败：保留已生成日志，上传可用报告；若报告未生成则工作流失败。
5. 报告低于阈值：
   - 默认手动模式：工作流成功并输出 warning。
   - enforce 模式：工作流失败。
6. Artifact 上传使用 `if: always()`，便于失败复盘。

## 11. 文档更新

更新：

```text
README.md
docs/interview_guide.md
docs/data_analyst_agent_开发文档_v_0_3.md
logs/work-diary.md
```

需要说明：

- PR/Push 自动验证内容。
- 手动真实 Qwen 评测触发方式。
- `QWEN_API_KEY` 必须配置为 GitHub Secret。
- 质量门禁阈值和告警/enforce 两种模式。
- CI 不会自动把真实评测 Secret 写入报告。

## 12. 安全约束

1. 工作流只授予 `contents: read`。
2. PR 工作流不访问 Qwen Secret。
3. 来自 Fork 的 PR 不运行真实 Qwen 评测。
4. Secret Scan 不输出完整命中内容。
5. Artifact 不包含 `.env`、请求头或 API Key。
6. 真实评测工作流不得使用 `pull_request_target`。

## 13. 验收标准

1. `.github/workflows/ci.yml` 在 PR/Push 自动运行后端测试、前端构建和 Secret Scan。
2. `.github/workflows/real-qwen-evaluation.yml` 仅手动触发并使用 GitHub Secret。
3. 基础 CI 不调用真实 Qwen API。
4. Quality Gate 能读取两份报告并判断四项阈值。
5. 默认质量门禁低于阈值只告警，`--enforce` 时失败。
6. 真实评测报告与质量门禁摘要作为 artifact 上传。
7. GitHub Step Summary 展示质量、Token 和耗时指标。
8. Secret Scan 能拦截明显硬编码凭据且不泄露命中内容。
9. 完整后端测试与前端构建通过。
