---
description: Continue a planning session after user edits. Starts the next turn with agent refinement.
---

# Continue Planning Session

Continue planning session: **$ARGUMENTS**

## Steps

1. Run `thunk continue --session $ARGUMENTS`
2. Run `thunk wait --session $ARGUMENTS` to wait for agents
3. When complete, tell the user:
   - The new turn number
   - The path to the updated plan file
   - They can edit again and `/thunk:continue`, or `/thunk:approve` if satisfied
