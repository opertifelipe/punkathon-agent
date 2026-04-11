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
2. If the user is specifically asking how much they can still spend in the current week, use `calcola_budget_residuo_settimana` instead.
3. If no week is specified, use the current week.
4. Read `confronto_settimane_precedenti`, `budget` and `top_spese`.
5. For residual-budget questions, use `budget_settimanale - spese_gia_fatte` and do not bring in monthly fixed expenses unless explicitly asked.
6. Surface the few numbers that matter and end with practical next moves.

## Guardrails
- Do not silently switch to monthly analysis.
- Make it explicit when the week is partial because it is still in progress.
