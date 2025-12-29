---
description: Check the status of a planning session without blocking.
---

# Check Session Status

Check status of session: **$ARGUMENTS**

## Steps

1. Run `thunk status --session $ARGUMENTS`
2. Report to the user:
   - Current turn number
   - Current phase (drafting, peer_review, synthesizing, user_review, approved)
   - Path to current plan file if in user_review
   - Whether there are unanswered questions
