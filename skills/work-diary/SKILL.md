---
name: work-diary
description: Use when starting or ending a work session - maintain a Chinese work diary at logs/work-diary.md for continuity across models
---

# Work Diary

## Overview

Maintain a work diary at `logs/work-diary.md` in Chinese. This ensures any model can pick up where the last session left off.

## The Rule

- **At session start:** Read the diary to understand current progress
- **After each task:** Update the diary with what was done
- **At session end:** Summarize what's pending and what's next

## Diary Structure

Each entry should include:

```markdown
## YYYY-MM-DD — 第N次会话

### 完成的工作
- Task N: 任务名称 ✅
  - 具体做了什么
  - Commit hash
  - 遇到的问题（如有）

### 遗留问题
- 任何未解决的问题或用户反馈

### 当前进度
- ✅ 已完成的任务
- ⏳ 进行中的任务
- ⏸️ 待开始的任务

### 下一步
- 接下来要做什么
- 需要注意什么

### 用户偏好
- 用户的特殊要求或习惯
```

## What to Record

- 每个完成的 task 及 commit hash
- 用户指出的错误或反馈
- 创建/修改的文件列表
- 遗留问题和解决方案
- 用户的偏好和要求

## What NOT to Record

- 详细的代码实现（看 git log）
- 每个小步骤的细节
- 临时的调试过程

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll update the diary later" | Later never comes. Update immediately. |
| "This is obvious from git log" | Git log doesn't capture user feedback and decisions. |
| "The diary is getting long" | Long diary > no diary. Keep entries concise but complete. |
