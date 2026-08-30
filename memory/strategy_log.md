# Strategy log

Append-only running log the agent writes to after every draft pick, waiver
move, trade decision, or lineup change — one entry per action, newest at the
bottom. This is the agent's own memory of *why* it did what it did, so a
future run (which starts with no memory of this one) can stay consistent
rather than contradict its own earlier reasoning or forget a plan it made.

Format for each entry:

```
## 2026-09-04 16:07 ET — Draft pick 3 (round 1, pick 3)
Picked: <player>, <position>, <team>
Why: <2-4 sentences of actual reasoning — ADP context, team need, injury
news found via research, etc.>
Alternatives considered: <who else was close>
```

---
