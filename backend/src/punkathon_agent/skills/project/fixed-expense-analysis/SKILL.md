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
4. Separate the macrocategory-based fixed estimate from the essential-fixed profile estimate if both are present.
5. Point out which fixed items are structural and which are review candidates.
6. Do not auto-explain any gap with the profile unless the user explicitly asks for that comparison.

## Guardrails
- Do not confuse fixed costs with essential-only fixed costs.
- If you mention the profile field, call it `spese fisse essenziali`, never just `spese fisse`.
- If there are no complete months available, state that clearly.
