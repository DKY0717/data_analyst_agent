# 危险意图评测报告

- 生成时间：2026-06-25-204340
- 总用例数：37
- 危险意图阻断率：100.0%
- 安全意图通过率：100.0%
- 误杀率：0.0%
- 预期规则匹配率：100.0%
- 质量门禁：通过

## 规则命中统计

| 规则 | 命中数 |
|---|---:|
| block_credential_access_intent | 5 |
| block_destructive_intent | 8 |
| block_security_bypass_intent | 4 |
| block_sensitive_export_intent | 3 |
| block_system_access_intent | 5 |

## 误杀与漏拦截明细

| Case | 分类 | 预期安全 | 实际安全 | 预期规则 | 实际规则 | 通用原因 |
|---|---|---|---|---|---|---|
| 无 | 无 | 无 | 无 | 无 | 无 | 无 |