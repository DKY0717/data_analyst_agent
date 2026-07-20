# 第12章 LangGraph 状态、节点与路由
> 本章预计 2 小时，建立完整 Agent 状态机。
## 12.1 学习目标
> 能画出十二节点、条件边、终止点和 Repair 回流。
## 12.2 前置知识
> 需要理解前面形成的意图、Grounding、SQL 和结果对象。
## 12.3 为什么需要这一模块
> 工作流包含暂停、阻断、执行失败和重试，单个长函数难以表达和测试这些状态转换。
## 12.4 输入、输出与依赖
> 输入是初始 AgentState；节点返回局部更新；图根据状态选择下一条边。
## 12.5 执行流程
```text
Guard → Intent → Grounding → Clarify? → Generate → Validate → Authorize → Execute → Repair?/Optimize → Answer
```
## 12.6 当前代码地图
| 内容 | 路径 |
|---|---|
| State | `backend/app/agents/state.py` |
| Graph | `backend/app/agents/graph.py` |
| Progress | `backend/app/agents/progress_notifier.py` |
## 12.7 关键代码理解
> 先读节点注册和条件边，再读节点内部。进度通知独立出来，避免编排逻辑混入传输细节。
## 12.8 最小动手运行
```bash
pytest backend/tests/test_agent_graph.py backend/tests/test_progress_notifier.py -q
```
## 12.9 故障注入实验
> 使用 Fake 节点令执行失败，观察图进入 Repair 而不是直接 Answer。
## 12.10 调试路径与常见误判
> state 字段存在不等于本轮有效；必须结合 status、错误阶段和路由条件判断。
## 12.11 独立编码练习
> 画出一个只有五节点的练习图，并加入安全阻断终止边。
## 12.12 测试或评测验证
> 为成功、澄清、阻断和修复四条路径各找一个测试。
## 12.13 面试复述题
> LangGraph 带来的价值是“更自主”还是“更可控”？
## 12.14 掌握度检查与下一章
> 能不看源码画出主要状态流。下一章学习失败恢复与多轮。
