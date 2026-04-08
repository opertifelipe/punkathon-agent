---
name: goal-insights
description: Use this skill when the user asks for weekly or monthly insights tied to their saved financial goal and wants clear, goal-oriented next actions.
---

# Goal Insights

## When To Use
- The user asks how they are doing relative to their goal.
- The user wants weekly or monthly insights based on `obiettivo`.
- The user wants to know if they are in line, at risk, or off track.

## Workflow
1. Use `genera_insight_settimanali` or `genera_insight_mensili`.
2. If the user does not specify the period, choose the tool that matches the request wording; otherwise state your assumption.
3. If the goal is missing, say so explicitly and keep the answer diagnostic.
4. Use categories focus and budget residual to justify every recommendation.

## Guardrails
- Do not fabricate a goal or savings target.
- Do not expose the internal `risparmio` field.
