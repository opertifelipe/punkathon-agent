---
name: weekly-spending-analysis
description: Use this skill when the user asks for a weekly spending review, a specific week analysis, or wants to understand where money went in the current week.
---

# Weekly Spending Analysis

## When To Use
- The user asks for spending in a specific week.
- The user asks for the current week without providing a week.
- The user wants a weekly recap, overspending check or quick weekly diagnosis.

## Workflow
1. Use `analizza_spese_settimana`.
2. If no week is specified, use the current week.
3. Read `confronto_settimane_precedenti`, `budget` and `top_spese`.
4. Surface the few numbers that matter and end with practical next moves.

## Guardrails
- Do not silently switch to monthly analysis.
- Make it explicit when the week is partial because it is still in progress.
