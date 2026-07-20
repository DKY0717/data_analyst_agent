# 第26章 评测分片、Checkpoint 与严格汇总

> 本章预计 1～2 小时。目标是理解真实模型长任务如何在超时、取消和部分成功时保留可审计证据，同时阻止残缺结果被包装成完整成绩。

## 26.1 学习目标

> 完成本章后，你应该能够：
>
> - 手算 round-robin 分片，并证明所有 case 恰好出现一次；
> - 解释为什么第一个模型请求前就要写空 checkpoint；
> - 说明临时文件、flush、fsync 和原子替换分别解决什么问题；
> - 列出严格汇总必须校验的身份与覆盖字段；
> - 解释为什么汇总器要重新计算 summary，不能信任分片自报分数；
> - 在证据缺片时选择 fail closed，而不是计算“现有样本准确率”。

## 26.2 前置知识

> 你已经理解三套真实模型评测、GitHub Actions 矩阵，以及进程可能被超时或取消。还应记住：百分比只有在分母和样本身份明确时才有意义。

## 26.3 为什么需要这一模块

> 真实模型评测通常比普通单测慢几个数量级。若 65 条 NL2SQL case 顺序运行，并且只在最后写一次报告，那么第 64 条超时时，前 63 条的逐例证据也可能全部丢失。
>
> 只做分片仍不够。一个目录里可能混有旧提交、不同模型、不同 case 文件、重复分片或只完成一半的 checkpoint。若汇总器看到 JSON 就平均，结果会变成无法审计的“拼盘成绩”。
>
> 本项目用三层约束处理：确定性分片减少单 job 风险；增量原子 checkpoint 保留已完成结果；严格汇总在身份和覆盖不完整时拒绝生成正式全集报告。

## 26.4 输入、输出与依赖

| 阶段 | 输入 | 输出 | 失败策略 |
|---|---|---|---|
| 分片选择 | 有序 cases、index、count | 当前分片固定 case 序列 | 参数非法时调用模型前失败 |
| 增量执行 | 当前分片、evaluator | checkpoint JSON | 每条 case 后覆盖有效快照 |
| 严格汇总 | 所有 checkpoint、权威 case YAML、预期身份 | 正式全集报告 | 任一身份/覆盖问题即拒绝 |

> 核心依赖是 `ShardSpec`、`AtomicCheckpointWriter`、`run_evaluation_shard()` 与 `ShardReportAggregator`。Evaluator 只负责单 case 和 summary 公式，共享分片组件负责证据完整性。

## 26.5 执行流程

```text
读取权威 case YAML
  → 校验 case_id 非空且不重复
  → 按 position % shard_count 选择当前分片
  → 对原始 case 文件计算 SHA-256
  → 首次模型调用前写空 checkpoint
  → 每完成一条 case 就原子写新 checkpoint
  → Actions 使用 if: always() 上传现有证据
  → 汇总器扫描所有候选 checkpoint
  → 校验身份、完成状态、case 覆盖与重复
  → 按权威 YAML 顺序恢复 results
  → 用原 evaluator 公式重新计算 summary
  → 写正式报告或稳定失败诊断
```

> 这里的“恢复”是恢复证据顺序，不是从 checkpoint 自动继续发起剩余请求。当前实现会保留部分进度供分析，但重跑某个分片时仍从该分片开头开始。

## 26.6 当前代码地图

| 内容 | 路径 | 阅读重点 |
|---|---|---|
| 分片与 checkpoint | `backend/evaluation/shard_support.py` | 参数契约、round-robin、原子写入 |
| 严格汇总 | `backend/evaluation/shard_report_aggregator.py` | 身份与覆盖校验、稳定诊断 |
| NL2SQL 入口 | `backend/evaluation/evaluator.py` | 复用共享分片组件 |
| Repair 入口 | `backend/evaluation/repair_evaluator.py` | 独立 Repair 分片 |
| Correctness 入口 | `backend/evaluation/result_correctness_evaluator.py` | 黄金结果分片 |
| 分片测试 | `backend/tests/test_shard_support.py` | 初始/增量快照和写入失败 |
| 汇总测试 | `backend/tests/test_shard_report_aggregator.py` | 缺片、重复、篡改和正式报告 |

## 26.7 关键代码理解

### 分片契约：三个参数必须成组出现

> `--shard-index`、`--shard-count` 和 `--checkpoint-output` 必须同时提供。只给其中一两个会在调用模型前 fail closed。index 从 0 开始，必须满足 `0 <= index < count`；布尔值虽然在 Python 中属于 int 子类，也被显式拒绝，避免 JSON/CLI 语义歧义。

### Round-robin：稳定覆盖，不依赖运行时长

> 选择规则是原始位置对分片总数取模：`position % count == index`，等价于 `cases[index::count]`。只要 case 顺序和 count 不变，每条 case 的归属就稳定。

```text
7 个 case：0 1 2 3 4 5 6
3 个 shard：
shard 0 → case 0, 3, 6
shard 1 → case 1, 4
shard 2 → case 2, 5
```

> Round-robin 比连续切块更可能把慢 case 分散，但它不保证耗时绝对均衡。新增、删除或重排 case 会改变后续归属，因此 checkpoint 还必须绑定 case 文件哈希。

### Checkpoint 身份：不能只看文件名

> 每个 checkpoint 的 `shard` 元数据包含 schema version、suite、HEAD SHA、provider、model、case 文件 SHA-256、分片 index/count、预期 case IDs、已完成 case IDs 和 complete 状态。文件名只是存储便利，不是可信身份。

```json
{
  "shard": {
    "schema_version": 1,
    "suite": "<nl2sql|repair|correctness>",
    "head_sha": "<commit>",
    "provider": "<provider>",
    "model": "<model>",
    "case_file_sha256": "<sha256>",
    "shard_index": 0,
    "shard_count": 3,
    "expected_case_ids": [],
    "completed_case_ids": [],
    "complete": false
  },
  "summary": {},
  "results": []
}
```

> 这只是字段示意，不是任何真实运行的完整报告，也不应在学习文档中填入 API Key、原始供应商响应或业务结果全集。

### 为什么先写空 checkpoint

> 第一个请求也可能卡住。如果先调用模型再写文件，一个超时分片可能连“自己是谁、应该运行哪些 case”都无法证明。先写空 checkpoint，至少留下分片身份、预期覆盖和 `complete: false`，随后每完成一条再更新。

### 原子写入：旧证据优于半个新 JSON

> `AtomicCheckpointWriter` 在目标文件同目录创建临时文件，写入后 flush 与 fsync，再用 replace 替换目标。若写入、取消或替换失败，只清理临时文件并保留上一版有效 checkpoint。
>
> 同目录很重要，因为跨文件系统移动未必具备原子替换语义。原子写入也不等于永不丢最后一条；它保证读者看到的是旧完整版本或新完整版本，而不是截断 JSON。

### 严格汇总：完整性先于分数

> 汇总器以当前 case YAML 为覆盖范围的唯一权威来源。它拒绝无效 JSON、缺失/重复分片编号、schema/suite/SHA/provider/model/hash/count 不一致、`complete` 不为真、预期/完成/result ID 不一致，以及缺失、未知或重复 case。
>
> 下载目录可能还有 run metadata，所以没有 `shard` 对象的普通 JSON会被忽略，而不是误认成分片。全部校验通过后，results 按权威 YAML 顺序恢复，并调用原 evaluator 的 `summarize_results()` 重新计算 summary；分片自己携带的 summary 不被直接相加或平均。
>
> 若失败，CLI 写稳定诊断 code，例如 `missing_shard_indices`、`incomplete_shard`、`metadata_mismatch` 或 `case_coverage_mismatch`，并返回非零退出码。它不会生成冒充全集的正式报告。

## 26.8 最小动手运行

> 运行分片与严格汇总的确定性测试。这些测试使用临时 case 和 checkpoint，不调用真实模型。

```powershell
pytest backend/tests/test_shard_support.py backend/tests/test_shard_report_aggregator.py -q
```

> 再只读定位关键实现，不必从头读完整文件。

```powershell
rg -n "class ShardSpec|class AtomicCheckpointWriter|def run_evaluation_shard" backend/evaluation/shard_support.py
rg -n "def aggregate|def _validate_checkpoint|missing_shard_indices" backend/evaluation/shard_report_aggregator.py
```

## 26.9 故障注入实验

> 在测试临时目录中构造完整两分片，再依次做四种篡改：删除 shard 1、复制 shard 0、把 model 改成其他值、把 `complete` 改成 false。每次都应得到稳定诊断，且不产生正式全集报告。

```text
删除分片       → missing_shard_indices
复制编号       → duplicate_shard_index
模型/SHA不符   → metadata_mismatch
部分完成       → incomplete_shard
改写case IDs   → case_coverage_mismatch
```

> 实验只改临时 fixture，不要删除真实 Artifact 或修改 GitHub Actions 运行。

## 26.10 调试路径与常见误判

> 先确定 suite、HEAD、provider/model、case hash 和 shard count，再看每个 checkpoint 的 expected/completed IDs 与 complete，最后才看 summary。反过来先读百分比，最容易被残缺分母误导。
>
> 常见误判一：8 个绿色 job 就等于 8/13 case。一个分片通常包含多个 case，job 数和 case 数不是同一个分母。
>
> 常见误判二：有 Artifact 就是完整证据。`if: always()` 会上传超时后留下的部分 checkpoint，Artifact 上传成功只证明文件被保存，不证明分片 complete。
>
> 常见误判三：把各分片百分比简单平均。如果分片 case 数不同，平均会失真；更重要的是旧模型或旧 case 可能混入。正确做法是校验身份、合并逐例结果、再重算摘要。
>
> 常见误判四：checkpoint 等于自动断点续跑。当前实现是增量保全证据，不是请求级 resume 调度器。

## 26.11 独立编码练习

> 用 10 个虚拟 case 和 4 个分片，手算每个分片 ID，并回答新增一个 case 到列表开头会影响哪些归属。然后为 checkpoint 写出最小身份字段，不需要复制生产代码。

```text
输入：case_0 ... case_9，shard_count=4
输出：
shard 0 → ?
shard 1 → ?
shard 2 → ?
shard 3 → ?
```

> 加分题：解释为什么 case 文件哈希要基于原始字节，而不是只记录文件名或 case 数量。

## 26.12 测试或评测验证

> 验收至少覆盖：非法边界、分片参数缺项、稳定覆盖、初始空 checkpoint、逐 case checkpoint、空分片、原子替换失败保留旧 JSON、重复/缺失 ID、缺片、重复片、身份篡改、覆盖篡改和汇总重排。

```powershell
pytest backend/tests/test_shard_support.py backend/tests/test_shard_report_aggregator.py -q
```

> 这组测试证明证据机制的确定性契约，不证明某次真实模型运行拥有完整分片。真实运行必须读取对应 Artifact 和严格汇总结论。

## 26.13 面试复述题

> **问题：为什么严格汇总必须 fail closed？**
>
> 合格回答：缺失分片不是随机缺失，往往正是慢 case 或失败 case；只对现有结果算分会产生幸存者偏差。本项目校验 HEAD、provider/model、case hash、分片身份和完整 case 覆盖，通过后按权威顺序合并并重算 summary，否则只输出稳定诊断。
>
> **追问：原子 checkpoint 解决了什么，没解决什么？**
>
> 应回答：它避免取消/崩溃时暴露半写 JSON，并保留上一版有效证据；它不能保证最后一个未写完 case 不丢，也不自动从剩余 case 继续执行。

## 26.14 掌握度检查与下一章

> 如果你能证明 round-robin 的唯一覆盖，并能从一个 checkpoint 判断它是否有资格参与汇总，就算掌握本章。
>
> 下一章把这些组件放进 GitHub Actions：为什么上游分片失败后仍要下载 Artifact、运行严格汇总并发布失败证据。
