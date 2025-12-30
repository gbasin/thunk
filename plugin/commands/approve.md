---
description: Approve and lock the current plan as final. Creates PLAN.md symlink.
---

# Approve Plan

Approve planning session: **$ARGUMENTS**

## Prerequisites

If `thunk` is not found (exit code 127), install it first:
```bash
uv tool install git+https://github.com/gbasin/thunk
```
Then continue with the steps below.

## Steps

1. Run `thunk approve --session $ARGUMENTS`
2. Tell the user:
   - The plan is now locked
   - Location of final PLAN.md
   - They can now implement based on this plan
