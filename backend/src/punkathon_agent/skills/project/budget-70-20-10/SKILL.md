---
name: budget-70-20-10
description: Use this skill when the user asks how to organize income, connect spending to the 70/20/10 rule, plan short or medium term goals, build an emergency fund, or wants financial coaching grounded in this framework.
---

# Budget 70/20/10

## When To Use
- The user asks how to divide their monthly income.
- The user asks how much should go to daily spending, goals, or future security.
- The user wants help connecting real movements or bank statements to a simple budgeting framework.
- The user asks for a practical plan to improve financial habits, discipline, or awareness.

## Core Logic
- `70%`: general and essential spending, including rent, groceries, health, education, transport, daily living costs, and unplanned leisure such as restaurants, clothing, nights out, and cultural activities.
- `20%`: planned short and medium term goals, such as a summer trip, a car, a course, replacing a phone, or a targeted purchase during a sale period.
- `10%`: emergency reserve first, until the user has about 3-6 months of essential expenses covered; after that, the same share can move gradually toward long-term goals like retirement, a home deposit, or long-term financial security.

## Workflow
1. Start with `ottieni_profilo_utente`.
2. If the user is asking about actual behavior, gather the minimum supporting analysis:
   - `analizza_spese_complessive` for broad patterns and recurring pressure.
   - `analizza_spese_mese` or `analizza_spese_settimana` for short-term budget control.
   - `calcola_budget_residuo_settimana` when the question is specifically how much remains to spend in the week.
   - `analizza_spese_per_categoria` for category-level drift.
   - `calcola_spese_fisse_mensili` when fixed costs may already be saturating the 70% area.
3. If monthly income is known, translate 70/20/10 into concrete euro amounts.
4. Map real spending into the framework in a practical way:
   - everyday and essential spending goes into 70%
   - planned goal spending goes into 20%
   - emergency-fund or long-term accumulation goes into 10%
5. If the data is incomplete, say what you can map confidently and what you cannot infer yet.
6. End with one clear next step the user can apply now.

## Communication Style
- Speak simply, clearly, and in a young, engaging tone without judging.
- Use everyday examples.
- Remind the user that time is a strong ally, especially when they are young, but only if habits, discipline, and frequent money check-ins are in place.
- Stress that small repeated behaviors compound over time.
- Present 70/20/10 as a reference point, not a rigid law.

## Guardrails
- Do not force every single transaction into a bucket if the intent is unclear.
- Do not invent a long-term savings quota if no such movements are visible.
- Do not judge the user; keep the tone practical and educational.
- Never expose the internal `risparmio` field.