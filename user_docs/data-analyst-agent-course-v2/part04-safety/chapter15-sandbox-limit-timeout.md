# 第15章 查询沙箱、LIMIT 与超时
> 本章预计 1～2 小时，学习即使安全 SQL 也要控制资源。
## 15.1 学习目标
> 能解释只读执行、LIMIT 注入、结果上限和查询超时。
## 15.2 前置知识
> 需要完成第14章 SQL Guard。
## 15.3 为什么需要这一模块
> SELECT 也可能读取巨量数据、调用高成本函数或长时间占用连接。
## 15.4 输入、输出与依赖
> 输入是已校验 SQL；输出是有限结果或结构化执行错误；依赖 sandbox 和 QueryRunner。
## 15.5 执行流程
```text
Validated SQL → Read-only Context → Timeout/LIMIT → Rows or Error
```
## 15.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Sandbox | `backend/app/db/sandbox.py` |
| Runner | `backend/app/db/query_runner.py` |
## 15.7 关键代码理解
> LIMIT 要通过 AST 判断而非字符串搜索；超时后要释放资源并返回可分类错误。
## 15.8 最小动手运行
```bash
pytest backend/tests/test_query_runner.py backend/tests/test_sql_guard.py -q
```
## 15.9 故障注入实验
> 在隔离测试中构造超时或超大结果，观察资源边界，不操作真实业务库。
## 15.10 调试路径与常见误判
> LLM 请求超时、评测 case 超时和数据库查询超时属于不同层。
## 15.11 独立编码练习
> 设计一个包含耗时、行数、列名和错误类型的执行结果模型。
## 15.12 测试或评测验证
> 找出 LIMIT 已存在、字符串中含 LIMIT 和无 LIMIT 三类测试。
## 15.13 面试复述题
> 为什么“只允许 SELECT”仍不足以保护数据库？
## 15.14 掌握度检查与下一章
> 能说明查询资源边界。下一章进入身份和数据权限。
