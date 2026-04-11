---
name: personal-finance-coach
description: Use this skill when the user asks for practical advice on how to improve money management, reduce overspending, rebalance their budget, or solve a specific spending problem using their profile, behavior, and stored financial data.
---

# Personal Finance Coach

## When To Use
- The user asks how to manage their money better overall.
- The user asks where they can cut spending or how to save more without vague generic tips.
- The user wants help with a specific spending problem grounded in their own data.
- The user asks for a practical action plan based on current habits, fixed costs, recent spending, or budget pressure.

## Workflow
1. Start with `ottieni_profilo_utente`.
2. Pick the supporting analysis that matches the request:
   - `analizza_spese_complessive` for general behavior and long-term patterns.
   - `analizza_spese_per_categoria` for a specific category problem or cost-cutting target.
   - `analizza_spese_settimana` or `analizza_spese_mese` for short-term budget control.
   - `calcola_budget_residuo_settimana` when the user asks how much they can still spend this week.
   - `calcola_spese_fisse_mensili` when structural fixed costs may be blocking progress.
   - `genera_insight_settimanali` or `genera_insight_mensili` when the user wants advice relative to a saved goal.
3. Base every recommendation on real signals: budget residual, heavy categories, recurring charges, fixed-versus-variable mix, and drift versus history.
4. If a missing profile field materially weakens the recommendation, say exactly what is missing and ask only for the minimum needed.
5. Finish with a short prioritized action plan that explains why each move matters for this user.

## Guardrails
- Do not give generic personal-finance platitudes detached from the stored data.
- Do not invent savings potential; when impact is uncertain, frame it as an estimate.
- Keep tax, debt restructuring, legal, or investment guidance high level; this skill is for spending and budgeting advice grounded in the user's data.
- Never expose the internal `risparmio` field.
