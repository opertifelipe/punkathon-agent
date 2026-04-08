---
name: category-spending-analysis
description: Use this skill when the user asks how much they spent in one or more categories, wants recurring items inside a category, or wants category-focused cost reduction ideas.
---

# Category Spending Analysis

## When To Use
- The user asks for spending by category.
- The user asks how much they spent in `Abbonamenti`, `Ristoranti`, `Bar`, `Spese Mediche` or any other supported category.
- The user wants to know which recurring charges inside a category deserve a review.

## Workflow
1. Use `analizza_spese_per_categoria`.
2. If the user explicitly asks for a week or month, pass the correct period selector.
3. If the user does not specify the period, declare which default you are using.
4. Read `dettaglio_categorie` and `voci_da_rivedere`.
5. Keep the answer grounded in totals, recurrence and actual movements.

## Guardrails
- Do not merge distinct categories unless the user asks for that.
- Do not invent category mappings outside the supported schema.
- If the result is thin, say so directly.
