---
name: comment-key-steps
description: Use when writing any new code in this project - requires Chinese comments at key steps so the user can learn from the code
---

# Comment Key Steps

## Overview

The user is learning while building this project. Every new code file MUST have Chinese comments at key steps explaining the logic, not just what the code does.

## The Rule

When writing new code:
1. Add Chinese comments at every key logical step
2. Explain WHY this code exists, not just WHAT it does
3. Use `#` inline comments for short explanations
4. Use block comments for complex logic or design decisions
5. Do NOT comment obvious lines (imports, variable assignments with clear names)

## What "Key Steps" Means

Comment these:
- Why a class/function exists (its purpose in the system)
- Why a specific approach was chosen over alternatives
- How a piece of code fits into the larger pipeline
- Non-obvious behavior (magic numbers, edge case handling, workarounds)
- Security or safety implications
- Error handling strategy choices

Do NOT comment these:
- Obvious imports
- Simple variable assignments with clear names
- Standard patterns (e.g., `if __name__ == "__main__"`)
- Self-explanatory function calls

## Comment Style

Use Chinese for all comments. Keep them concise.

```python
# Good - explains WHY and HOW it fits the system
# SQL Guard 使用 SQLGlot 解析 SQL AST，只允许 SELECT/WITH 语句通过
def validate_sql(sql: str) -> bool:
    ...

# Good - explains non-obvious choice
# 使用指数退避重试，避免 API 限流时频繁请求
await asyncio.sleep(2 ** attempt)

# Bad - just restating the code
# 调用 validate_sql 函数
validate_sql(sql)

# Bad - obvious comment
# 定义变量 x
x = 10
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "Code is self-explanatory" | Self-explanatory to you, not to a learner |
| "Comments clutter the code" | Good comments clarify, not clutter |
| "I'll add comments later" | Later never comes. Comment as you write |
| "This is simple, no comment needed" | Simple to you ≠ simple to a learner |

## No Exceptions

- Not for "simple" files
- Not for "utility" code
- Not for "config" files
- Every new file gets comments at key steps
