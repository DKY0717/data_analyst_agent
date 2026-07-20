# 第16章 认证、数据权限与行级过滤
> 本章预计 2 小时，学习“谁可以查询什么”。
## 16.1 学习目标
> 能区分认证、角色、表列权限和行级 SQL 改写。
## 16.2 前置知识
> 需要理解 API 依赖、SQL AST 和业务表。
## 16.3 为什么需要这一模块
> SQL 安全只能判断语句危险性，不能判断 analyst 是否有权查看客户姓名。
## 16.4 输入、输出与依赖
> 输入是身份、角色、SQL 和 query scope；输出是允许、阻断或授权后的 SQL。
## 16.5 执行流程
```text
Credential → Principal/Role → Table/Column Policy → Row Filter → Authorized SQL
```
## 16.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Auth | `backend/app/security/auth.py` |
| Permission | `backend/app/security/data_permission.py` |
| Policy | `backend/app/security/data_permissions.yaml` |
## 16.7 关键代码理解
> 权限列需要按查询范围解析；行级约束由确定性代码改写 SQL，不能只写进 Prompt。
## 16.8 最小动手运行
```bash
pytest backend/tests/test_auth.py backend/tests/test_data_permission_guard.py -q
```
## 16.9 故障注入实验
> 比较 analyst 与 admin 查询客户姓名的结果和审计规则。
## 16.10 调试路径与常见误判
> 前端角色标签不是安全边界；真正判定必须在服务器端。
## 16.11 独立编码练习
> 为 support 角色新增一条练习策略和允许/拒绝测试草案。
## 16.12 测试或评测验证
> 运行离线权限 evaluator，观察允许、阻断和 SQL 改写指标。
## 16.13 面试复述题
> 行级过滤为什么不能完全交给 LLM？
## 16.14 掌握度检查与下一章
> 能解释身份到授权 SQL 的路径。下一章学习失败隔离与重试。
