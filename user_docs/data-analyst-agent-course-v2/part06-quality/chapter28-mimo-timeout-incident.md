# 第28章 MiMo 真实评测超时事故复盘

> 本章预计 1～2 小时。我们使用已完成的 GitHub Actions run `29634864907` 学习如何从身份、job、step、脱敏日志和严格汇总形成诚实结论。

## 28.1 学习目标

> 完成本章后，你应该能够：
>
> - 区分模型输出异常、客户端重试缺陷、step 超时、分片失败和证据不完整；
> - 准确复述 13/3/5 三套分片结果；
> - 说明最终 quality gate 为什么没有实际执行阈值计算；
> - 从重复日志反推重试循环的退出条件问题；
> - 给出不泄密、不甩锅、不夸大的事故结论和改进实验。

## 28.2 前置知识

> 你已经理解 LLM Service 的 OpenAI-compatible 响应读取、分片 checkpoint、Actions 依赖关系和严格汇总。建议先复习第 7、17、26、27 章。

## 28.3 为什么需要这一模块

> 面试项目的可信度不取决于“永远没有红灯”，而取决于你是否能保存失败证据、找到机制性原因、说清已证明与未证明的范围，并提出可验证改进。
>
> 这次运行尤其典型：真实模型 smoke、部分 NL2SQL、全部 Repair 和全部 correctness job 成功；但 5 个 NL2SQL 分片超时，全集证据不完整。只说“失败”会丢失有效证据，只说“大部分成功”又会掩盖严格门禁结论。

## 28.4 输入、输出与依赖

| 身份字段 | 已核实值 |
|---|---|
| Run | `29634864907` |
| HEAD | `8dffc1d76c514c7efe1b6e642ea1880a81989109` |
| Provider | `mimo` |
| Model | `mimo-v2.5-pro` |
| 创建时间 | 2026-07-18 06:56 UTC |
| 完成时间 | 2026-07-18 14:21 UTC |
| 最终 conclusion | failure |

> 身份由 `gh run view` 的 headSha/job 数据和 preflight 脱敏 run metadata 交叉确认。日志中的 Key 已由 GitHub mask；本章不复制 API Key、完整请求、原始业务结果或无关供应商响应。

## 28.5 执行流程

```text
确认 run 身份
  → 检查 preflight
  → 列出三套全部分片 job
  → 对失败 job 定位失败 step 与持续时间
  → 筛选脱敏空 content/timeout 日志
  → 对照基线 LLM 重试循环
  → 检查三套严格汇总 outcome
  → 检查质量阈值 step 是否真正执行
  → 写“已证明 / 未证明 / 改进假设”
```

> 这个顺序很重要。先看日志而不确认 HEAD/model，可能分析错运行；只看 job 总结而不看 step，会把聚合失败误说成阈值失败。

## 28.6 当前代码地图

| 内容 | 路径 | 与事故的关系 |
|---|---|---|
| 真实模型工作流 | `.github/workflows/real-qwen-evaluation.yml` | 13/3/5 矩阵与 75 分钟 step 上限 |
| LLM Service | `backend/app/services/llm_service.py` | 空 content 分支与重试循环 |
| LLM 观测 | `backend/app/services/llm_observability.py` | 调用次数、耗时和错误类型 |
| 分片 checkpoint | `backend/evaluation/shard_support.py` | 超时后保留部分证据 |
| 严格汇总 | `backend/evaluation/shard_report_aggregator.py` | NL2SQL 不完整时 fail closed |
| 质量门禁 | `backend/evaluation/quality_gate.py` | 只有三套聚合成功才消费报告 |
| LLM Service 测试 | `backend/tests/test_llm_service.py` | 应补重复空 content 的终止契约 |

## 28.7 关键代码理解

### 事实一：运行身份与 preflight 有效

> Run 的 HEAD 与目标提交一致，provider/model 为 `mimo` / `mimo-v2.5-pro`。Preflight job 成功，其中确定性后端测试成功，真实模型 core smoke 也成功。因此不能把事故归因于“Key 缺失”“完全无法连接模型”或“preflight 没通过”。

### 事实二：三套分片结果并不相同

| Suite | 成功分片 | 失败分片 | 可得结论 |
|---|---|---|---|
| NL2SQL 13片 | 0、1、2、3、5、7、9、11 | 4、6、8、10、12 | 8片 job 成功，5片在评测 step 失败，全集不完整 |
| SQL Repair 3片 | 0、1、2 | 无 | 三个 Repair 分片 job 完成 |
| Result Correctness 5片 | 0、1、2、3、4 | 无 | 五个 correctness 分片 job 完成 |

> “8/13”是分片 job 数，不是 NL2SQL case 准确率。失败分片的 Artifact 仍可能包含部分 checkpoint；在严格汇总拒绝前，不能把成功分片结果外推到全部 65 个 case。

### 事实三：五个 NL2SQL step 都触达 75 分钟外层上限

> 失败的是 `Run real NL2SQL shard` step，随后 `Upload NL2SQL shard evidence` 仍成功。这与 workflow 的 75 分钟评测 step、90 分钟 job 和 `if: always()` 上传设计一致。
>
> 以 shard 4 为例，脱敏日志在数十分钟内反复出现“reasoning 有长度、content 为空”，最后由 Actions 报告该 step 在 75 分钟后超时。reasoning 不能作为 SQL Generator 或 Answer Generator 的结构化正文，因此系统拒绝把它当成功输出是正确的；问题在于重试没有形成有效截止。

### 事实四：这是供应商异常响应与客户端循环缺陷的组合

> 基线 `llm_service.py` 使用两个预算：普通 `attempt` 和 429 `rate_limit_retries`。循环条件是“普通预算未尽 **或** 429 预算未尽”；空 content + reasoning 分支执行 `continue`，会增加 attempt，却不会增加 429 计数。

```text
while attempt < max_retries OR rate_limit_retries < max_rate_limit_retries:
    attempt += 1
    if content 为空且 reasoning 非空:
        continue  # 429 计数仍为 0
```

> 当普通 attempt 超过 `max_retries` 后，只要 429 计数仍小于 8，`or` 条件依旧为真；而空 content 分支又不推进 429 计数，所以该响应模式下循环缺少内部终止条件。日志中远超普通重试次数的重复空 content 与这一控制流一致。
>
> 因此根因不能只写“MiMo 太慢”，也不能只写“客户端 bug”。更准确的表述是：MiMo 多次返回 reasoning 非空但业务 content 为空，触发了客户端一个未受普通重试预算约束的分支，尾延迟不断累积，最终由 GitHub Actions 75 分钟外层截止终止。

### 事实五：最终是聚合失败，阈值门禁被跳过

> 最终 job `Strict aggregation and quality gate` 失败。内部步骤显示：NL2SQL 严格汇总失败；Repair 与 correctness 严格汇总成功；`Evaluate quality gate` 因三套聚合 outcome 条件不满足而 skipped。
>
> 所以不能说“质量指标低于阈值导致失败”。准确说法是“NL2SQL 全集证据不完整，严格汇总 fail closed，阈值计算没有获得三份完整输入而未执行”。严格安全审计也因缺少完整真实报告而失败，最终 Artifact 与 Summary 仍被上传。

> 同一最终 job 中，确定性 Intent/Grounding 的 `slot_match_rate` 与 `all_expectations_met_rate` 为 1.0，权限的 `allowed_decision_accuracy` 与 `blocked_rule_accuracy` 为 1.0。它们证明固定确定性 case 通过，不替代缺失的真实 NL2SQL 证据。

## 28.8 最小动手运行

> 以下命令只读查看历史 run 的身份和紧凑 job 列表，不会触发、重跑或取消 Actions。

```powershell
gh run view 29634864907 --repo DKY0717/data_analyst_agent --json headSha,status,conclusion,jobs,url
```

> 只筛选 job 名与结论时，可以使用 `--jq`。如果本机没有 GitHub CLI 登录或网络权限，保留本章已核实证据，不要为了“跑通命令”修改工作流或重新触发真实评测。

```powershell
gh run view 29634864907 --repo DKY0717/data_analyst_agent --json jobs --jq '.jobs[] | [.name,.conclusion] | @tsv'
```

## 28.9 故障注入实验

> 使用 HTTP Mock 连续返回合法 JSON，但令 `message.reasoning_content` 非空、`message.content` 为空。为实验本身设置很短的 `asyncio.wait_for` 外层截止，避免复现时真的无限等待。

```python
# 练习伪代码：不要复制真实凭据或发外网请求
responses = [empty_content_with_reasoning()] * 20
result = await asyncio.wait_for(call_fake_llm(responses), timeout=0.2)
```

> 在未修复基线逻辑下，预期由外层 timeout 终止，而不是在 `max_retries` 后得到稳定 LLM 错误。这个实验应使用替身，并在结束后恢复所有临时改动。
>
> 再设计修复后的期望：空 content 应有独立且有限的预算；到达上限后记录 `LLMResponseError` 或专门错误类型；观测中包含实际 attempt；绝不能把 reasoning 当作 content。

## 28.10 调试路径与常见误判

> 推荐排查链：401/凭据 → preflight smoke → HTTP status → 响应结构 → content/reasoning → 内部重试预算 → 单请求 deadline → step/job timeout → checkpoint complete → strict aggregation。
>
> 常见误判一：超时等于 SQL 能力错误。超时分片没有形成完整结果，不能判断其中未完成 case 的 SQL 对错。
>
> 常见误判二：8/13 分片成功等于准确率 61.5%。分片包含的 case 数和难度不同，且失败不是随机缺失；这是 job 完成比例，不是业务准确率。
>
> 常见误判三：Repair 3/3 成功说明整个 Agent 通过。Repair 是独立固定故障套件，不能填补 NL2SQL 生成证据。
>
> 常见误判四：最终 quality-gate job 失败等于阈值未达标。本次阈值 step 实际 skipped，失败先发生在 NL2SQL 严格汇总。
>
> 常见误判五：reasoning 有内容就可以解析。项目结构化任务消费 `message.content`；reasoning 既不保证 JSON 契约，也不应作为用户答案泄露。

## 28.11 独立编码练习

> 为这次事故写三项改进提案，每项都必须包含机制、测试和成功指标。建议覆盖：统一总尝试预算、单请求/单 case deadline、基于历史耗时的分片策略。

```text
提案 A：空 content 有限预算
机制：所有可重试响应都消耗统一总预算
测试：连续 N 次 empty content 后稳定失败
指标：attempt <= 配置上限；不依赖 Actions 外层超时

提案 B：单 case deadline
机制：每个 case 包裹可取消的截止时间
测试：Fake LLM 永不返回时仍写部分 checkpoint
指标：最坏 case 耗时受控；后续 case/诊断策略明确

提案 C：耗时感知分片
机制：用历史时长估计把慢 case 分散
测试：固定 duration fixture 下最大分片总时长下降
指标：p95 分片时长下降，覆盖与身份契约不变
```

> 还要说明副作用：更短 deadline 可能增加假失败；减少重试可能降低偶发恢复率；动态分片必须仍可复现并绑定分片计划版本。

## 28.12 测试或评测验证

> 先验证现有 LLM Service、观测、分片、汇总和工作流契约。不要在本地测试命令中启用真实模型环境变量。

```powershell
pytest backend/tests/test_llm_service.py backend/tests/test_llm_observability.py backend/tests/test_shard_support.py backend/tests/test_shard_report_aggregator.py backend/tests/test_workflow_files.py -q
```

> 对修复提案的最低新增回归是“连续空 content 永远不能超过明确预算”。只有代码修复、确定性回归通过，并重新产生同一 case pack 的完整真实 Artifact 后，才能更新真实模型结论。

## 28.13 面试复述题

> **问题：你会如何准确描述这次 MiMo 运行？**
>
> 合格回答：在 HEAD `8dffc1d...`、provider/model 为 MiMo `mimo-v2.5-pro` 的 run `29634864907` 中，preflight 成功；NL2SQL 13 个分片有 8 个成功、5 个在 75 分钟 step 上限超时；Repair 3/3、correctness 5/5 job 成功。空 content + reasoning 响应触发了客户端未被普通预算截断的重试路径。NL2SQL 严格汇总因证据不完整失败，阈值门禁被跳过，所以不能宣称真实模型全量通过。
>
> **追问：这是模型问题还是代码问题？**
>
> 应回答：两者共同作用。异常响应来自供应商行为，但客户端必须对任何可重试响应设置总预算和 deadline；工程责任是让外部异常可控、可观测、可恢复，而不是无限等待或把 reasoning 冒充 content。

## 28.14 掌握度检查与下一章

> 如果你能在不看本章的情况下复述身份、8/13、3/3、5/5、五个超时分片、组合根因和“门禁 skipped 而非阈值失败”，就算掌握本章。
>
> 下一部分进入独立能力训练：从新增一个业务指标开始，完整走过语义、Grounding、SQL、权限、评测和文档更新链路。
