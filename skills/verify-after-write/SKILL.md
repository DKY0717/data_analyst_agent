---
name: verify-after-write
description: Use after writing any new code file - run minimal verification to ensure the code actually works before moving on
---

# Verify After Write

## Overview

After writing new code, ALWAYS run minimal verification to ensure it works. Never assume code is correct without testing it.

## The Rule

After creating or modifying a code file:
1. At minimum: import the module and check for syntax/import errors
2. For functions: run a basic call with sample input
3. For classes: instantiate and call key methods
4. For more complex code: write a proper pytest test

## Verification Levels

### Level 1: Import Check (minimum for every file)
```bash
cd backend && python -c "from app.utils.exceptions import *; print('OK')"
```
Catches: syntax errors, import errors, circular dependencies

### Level 2: Smoke Test (for functions/classes)
```bash
cd backend && python -c "
from app.utils.exceptions import AppException, LLMError
try:
    raise LLMError('test')
except AppException:
    print('Exception hierarchy OK')
"
```
Catches: logic errors, wrong inheritance, missing methods

### Level 3: pytest (for testable logic)
```bash
cd backend && pytest tests/test_sql_guard.py -v
```
Catches: edge cases, integration issues, regression

## When to Use Which Level

| Code Type | Minimum Level |
|-----------|--------------|
| Exception classes | Level 1 + Level 2 |
| Config / settings | Level 1 |
| Utility functions | Level 2 |
| Business logic | Level 3 |
| API endpoints | Level 3 |
| Database queries | Level 3 |

## Process

```
Write code
  → Run verification (appropriate level)
  → Pass? → Commit
  → Fail? → Fix → Re-verify → Commit
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "It should work" | Should ≠ does. Run it. |
| "I'll test later" | Later never comes. Test now. |
| "It's simple, no need to test" | Simple code has simple bugs. Test anyway. |
| "I wrote it carefully" | Careful writing ≠ correct code. Verify. |

## No Exceptions

- Not for "simple" files
- Not for "just config"
- Not for "just exceptions"
- Every file gets verified before commit
