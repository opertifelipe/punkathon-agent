---
name: fixed-expense-analysis
description: Use this skill when the user asks for monthly fixed expenses, structural costs, or wants the fixed-cost estimate derived from macrocategory data.
---

# Fixed Expense Analysis

## When To Use
- The user asks how much they spend in fixed monthly costs.
- The user wants to know which recurring fixed items are weighing on the budget.
- The user wants the monthly fixed-cost estimate based on `macrocategoria`.
- The user says things like `dammi le spese fisse`, `quali sono le spese fisse` or `fammi vedere i costi fissi`.

## Workflow
1. Map the request to `MacroCategoriaSpesa = Spese Fisse`.
2. Use `analizza_spese_fisse` or `calcola_spese_fisse_mensili`.
3. Read `spese_fisse_da_macrocategoria`.
4. Use the total from the previous complete month as the canonical monthly fixed-cost value.
5. Point out which fixed items are structural and which are review candidates.
6. If you mention the profile field, explain that it is synchronized with the same previous-complete-month total used for budget.

## Guardrails
- Do not confuse fixed costs with essential-only fixed costs.
- If you mention the profile field, explain that it mirrors the previous complete month's `Spese Fisse` total.
- If the previous complete month is not available, state that clearly.
