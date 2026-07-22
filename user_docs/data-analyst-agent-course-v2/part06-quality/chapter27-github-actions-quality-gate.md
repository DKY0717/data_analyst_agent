# 第27章 GitHub Actions 与质量门禁

> 本章预计 1～2 小时。你将学习 CI 如何从“自动执行命令”升级为“收集身份一致、覆盖完整、达到阈值的发布决策证据”。

## 27.1 学习目标

> 完成本章后，你应该能够：
>
> - 区分普通 CI 与手动真实模型评测工作流；
> - 解释 preflight、三类分片矩阵、Artifact 下载、严格汇总和质量门禁的依赖关系；
> - 读懂 `needs`、`if: always()`、`continue-on-error` 与 `fail-fast: false` 的证据意义；
> - 区分聚合失败、阈值失败、输入错误和 job 总体失败；
> - 只读检查历史 run，不触发、重跑、取消或暴露 Secrets。

## 27.2 前置知识

> 你已经掌握测试金字塔、三类专项评测，以及第 26 章的 checkpoint 与严格汇总。GitHub Actions YAML 可以先理解为“带依赖关系的远端命令清单”。

## 27.3 为什么需要这一模块

> 本地一次绿色命令很难证明环境、提交、模型和 case 身份。CI 能把命令绑定到 Git commit，并持久化日志和 Artifact；质量门禁再把多份报告转换成明确的通过/失败决策。
>
> 但 job 绿色也只是局部事实。若 13 个 NL2SQL 分片中只有 8 个绿色，不能截取这 8 个作为全量成绩；若严格汇总失败，后面的阈值评估甚至不应该运行。工作流设计必须让失败发生后仍能保存并展示这些边界。

## 27.4 输入、输出与依赖

| 阶段 | 输入 | 输出 | 是否依赖真实模型 |
|---|---|---|---|
| 普通 CI | push/PR、源码 | 后端/前端/E2E/容器 checks | 否 |
| workflow_dispatch | provider、URL、model、enforce 开关 | 一次真实评测 run | 是 |
| Preflight | 凭据、数据库、代码 | metadata、确定性测试、real smoke | 是 |
| 分片矩阵 | 三套 case pack | shard checkpoints/artifacts | 是 |
| 严格汇总 | 下载的全部分片 | 三份正式报告或诊断 | 否 |
| 质量门禁 | 三份真实报告 + 两份确定性报告 | JSON/Markdown、退出码 | 否 |
| 安全审计导出 | 可用评测与门禁报告 | 脱敏审计摘要 | 否 |

> Secrets 只在选择 provider credential 的 step 注入，并通过 GitHub mask 机制隐藏。课程、日志摘要和 Artifact 都不应保存真实 Key。

## 27.5 执行流程

```text
手动触发 workflow_dispatch
  → preflight
      凭据选择与校验
      数据库准备
      run metadata
      确定性后端测试
      real-model smoke
  → NL2SQL matrix：13 shards
  → Repair matrix：3 shards
  → Correctness matrix：5 shards
  → quality-gate job（always）
      下载 preflight 和所有 shard artifacts
      跑确定性 Intent/Grounding 与 Permission
      分别严格汇总三套真实报告
      三套汇总全成功后才评估阈值
      导出严格安全审计
      发布 Step Summary
      always 上传最终证据
```

> 当前矩阵 `max-parallel: 2` 且 `fail-fast: false`。某个分片失败不会自动取消同一矩阵的其他分片，从而尽可能收集局部证据；这不改变严格汇总必须完整的要求。

## 27.6 当前代码地图

| 内容 | 路径 | 阅读重点 |
|---|---|---|
| 普通 CI | `.github/workflows/ci.yml` | PR/push 的确定性质量检查 |
| 真实模型工作流 | `.github/workflows/real-qwen-evaluation.yml` | preflight、矩阵和证据流 |
| 运行身份元数据 | `backend/evaluation/run_metadata.py` | HEAD/provider/model/case version |
| 严格汇总 | `backend/evaluation/shard_report_aggregator.py` | 不完整证据拒绝 |
| 质量门禁 | `backend/evaluation/quality_gate.py` | 指标来源、阈值与退出码 |
| 安全审计导出 | `backend/evaluation/security_audit_exporter.py` | 缺真实报告时 fail-on-missing |
| 工作流契约测试 | `backend/tests/test_workflow_files.py` | YAML 结构不漂移 |
| 门禁测试 | `backend/tests/test_quality_gate.py` | 缺字段、非法数值、warn/enforce |

## 27.7 关键代码理解

### 普通 CI 与真实模型 CI 分工

> `.github/workflows/ci.yml` 面向频繁 push/PR，运行确定性后端测试、前端单测/构建、Playwright E2E、Compose 配置和容器 readiness。它不应依赖付费模型 Key。
>
> `.github/workflows/real-qwen-evaluation.yml` 由 `workflow_dispatch` 手动触发，输入 provider、API URL、model 与 `enforce_thresholds`。文件名保留 qwen 是历史命名，实际工作流当前支持 MiMo 与 Qwen-compatible 配置。

### Preflight：先证明环境和身份

> Preflight 根据 provider 选择对应 Secret，写 run metadata，准备固定数据库，运行确定性后端测试、真实模型 smoke 和确定性 Intent 评测。只有 preflight 成功，NL2SQL 分片才开始。这样可以避免凭据缺失或核心连通性失败后浪费整套矩阵。

### 90/75 分钟双预算

> 每个分片 job 上限为 90 分钟，真正评测 step 上限为 75 分钟。剩余预算用于 `if: always()` 的 Artifact 上传和清理。即使评测 step 超时，checkpoint 仍有机会被保存。

> Repair 与 correctness job 使用 `always() && preflight success` 形式，即使上游 NL2SQL 或 Repair 有失败，也继续运行独立套件。这让一次 run 能留下更多诊断证据，而最终汇总仍会拒绝缺片。

### 下载失败可以继续，聚合失败不能伪装

> quality-gate job 本身 `if: always()`，Artifact 下载 step 使用 `continue-on-error: true`。原因不是忽略缺失，而是让 job 继续到严格汇总，由汇总器生成结构化缺片诊断，而不是在下载阶段只留一个通用错误。
>
> 三个聚合 step 都使用 `if: always()`，因此 NL2SQL 聚合失败后，Repair 和 correctness 仍可分别证明是否完整。真正的 `Evaluate quality gate` 只有三套聚合 outcome 都为 success 才执行。

### 门禁指标：完整报告之后才谈阈值

> `QUALITY_THRESHOLDS` 当前把安全请求执行、危险请求阻断、安全预期、Repair 端到端、结果正确性、Intent/Grounding 各层和权限四项指标都设为 1.0。这是该演示 case pack 的严格门禁，不等于对开放世界生产请求承诺 100%。
>
> `quality_gate.py` 对缺失字段、布尔伪装数字、NaN/Infinity 和非法 JSON 返回输入错误；指标低于阈值则形成 failed checks。未传 `--enforce` 时是告警模式，命令可返回 0；传入后门禁失败返回 1；输入错误返回 2。
>
> Token 与耗时只进入观察表，不是功能质量阈值。成本不可用也不能被自动解释为零成本。

### 最终证据仍要 always 上传

> 无论聚合或门禁是否成功，工作流都会尝试发布 Step Summary、导出严格安全审计并上传最终 Artifact。一次失败 run 仍应成为可学习、可审计的证据，而不是只留下红叉。

## 27.8 最小动手运行

> 在本地验证工作流 YAML 契约和门禁纯逻辑，不触发远端真实模型。

```powershell
pytest backend/tests/test_workflow_files.py backend/tests/test_quality_gate.py backend/tests/test_security_audit_exporter.py -q
```

> 只读检查某个历史 run 的身份和 job 结果，可以使用以下命令。它不会触发或修改运行。

```powershell
gh run view <run-id> --repo <owner/repo> --json headSha,status,conclusion,jobs,url
```

> 不要把 `<run-id>` 和 `<owner/repo>` 原样复制执行；替换成你有权查看的仓库和运行。学习本课程的事故案例时，第 28 章会给出已核实的具体运行。

## 27.9 故障注入实验

> 使用 `test_quality_gate.py` 的临时报告思路，依次构造四种输入：缺少报告文件、summary 缺必要指标、指标低于阈值、全部满足。记录预期退出码和是否生成 Markdown。

```text
报告/JSON无效        → 输入错误，exit 2
必要指标缺失         → 输入错误，exit 2
低于阈值且 warn 模式 → 生成失败检查，exit 0
低于阈值且 enforce   → 生成失败检查，exit 1
全部满足             → passed
```

> 再阅读 workflow：假设 NL2SQL 聚合失败，判断 Repair 聚合、correctness 聚合、Evaluate quality gate、Publish summary、Upload final evidence 哪些仍会执行。不要修改或重跑远端 Actions。

## 27.10 调试路径与常见误判

> 调试顺序应为：先核对 run `headSha` 与输入身份，再看 preflight，然后看所有矩阵 job 和评测 step，再看 Artifact 是否上传、checkpoint 是否 complete、三套严格汇总，最后才看质量阈值。
>
> 常见误判一：job 名叫“Strict aggregation and quality gate”且失败，就说“指标低于阈值”。实际上可能是聚合先失败，Evaluate quality gate 被跳过。
>
> 常见误判二：`continue-on-error` 表示忽略错误。这里它只是把诊断责任后移到严格汇总，让缺失证据得到稳定 code。
>
> 常见误判三：`if: always()` 表示步骤成功。它只表示无论上游结果都尝试执行，该步骤仍可能失败。
>
> 常见误判四：Artifact 上传成功等于评测成功。上传的可能是 `complete: false` checkpoint 或失败诊断。
>
> 常见误判五：所有阈值 1.0 就代表生产准确率 100%。阈值只适用于固定 case pack、固定数据、固定代码和指定模型。

## 27.11 独立编码练习

> 选择一个新指标，例如“参考查询 Guard 通过率”，先不要修改正式门禁。写出四类测试设计：报告缺失、字段缺失、值低于阈值、值达到阈值。再回答它应该来自哪份 summary，是否属于发布阻断指标。

```text
metric: <稳定字段名>
source: <哪份报告>
threshold: <值与理由>
missing behavior: fail closed
warn/enforce behavior: <说明>
```

> 练习重点是先定义证据契约，再改工作流；否则 YAML、CLI 和报告字段很容易漂移。

## 27.12 测试或评测验证

> 本章验证覆盖普通 CI 的关键 job、真实模型 workflow inputs、矩阵数量、90/75 分钟预算、always 上传、下载容错、严格汇总命令，以及门禁的指标/退出码。

```powershell
pytest backend/tests/test_workflow_files.py backend/tests/test_quality_gate.py backend/tests/test_security_audit_exporter.py -q
```

> 本地 YAML 测试通过只能证明工作流定义符合契约；真实 Actions 是否成功仍需只读查看特定 run 的 SHA、jobs、logs 和 Artifact。

## 27.13 面试复述题

> **问题：质量门禁和普通 pytest 有什么本质区别？**
>
> 合格回答：pytest 主要验证确定性代码契约；质量门禁消费绑定 HEAD/provider/model/case 的多套完整评测报告，先由严格汇总证明覆盖完整，再检查安全、Repair、正确性、Grounding 和权限阈值，最后以 CI 退出码形成发布决策。
>
> **追问：为什么上游失败后还继续汇总和上传？**
>
> 应回答：为了保留局部证据和稳定诊断，区分哪套完整、哪套缺片；但最终结论仍 fail closed，不能把继续收集证据误解为通过。

## 27.14 掌握度检查与下一章

> 如果你能从一个 run 的红叉准确区分“哪个分片失败、哪套聚合失败、阈值是否实际执行、最终保留了什么证据”，就算掌握本章。
>
> 下一章用 run `29634864907` 实战：它不是简单的“MiMo 不行”，而是供应商空内容、客户端重试边界和 CI 外层超时共同形成的事故。
