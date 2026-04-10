---
name: monthly-spending-analysis
description: Use this skill when the user asks for spending in a specific month, the current month, or wants to compare the month against previous months.
---

# Monthly Spending Analysis

## When To Use
- The user asks for spending in a specific month.
- The user asks for the current month without providing a month.
- The user wants a monthly recap or a comparison with previous months.

## Workflow
1. Use `analizza_spese_mese`.
2. If no month is specified, use the current month.
3. If the user asks a semantic question about a merchant, product, or keyword in the current month, use `ottieni_movimenti_mese_corrente` and infer matches semantically from the returned descriptions.
4. Read `confronto_mesi_precedenti`, `budget` and `spese_per_categoria`.
5. Highlight deltas versus history only when they are supported by data.

## Guardrails
- Do not blur weekly and monthly numbers.
- Do not use SQL LIKE/contains on `descrizione` for semantic month questions.
- If there are too few historical months, say that the comparison is weak.
