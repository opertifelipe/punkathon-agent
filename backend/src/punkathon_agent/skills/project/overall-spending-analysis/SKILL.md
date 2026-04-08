---
name: overall-spending-analysis
description: Use this skill when the user wants a full-history analysis across the entire dataset, including main categories, trends and structural spend patterns.
---

# Overall Spending Analysis

## When To Use
- The user asks for a general analysis of all available data.
- The user wants to understand long-term patterns across the dataset.
- The user asks where money usually goes over time.

## Workflow
1. Use `analizza_spese_complessive`.
2. Read the monthly and weekly series only to support a clear conclusion.
3. Use `calcola_spese_fisse_mensili` if the historical picture needs a fixed-versus-variable split.
4. Keep the response high signal: totals, heavy categories, structural patterns, next moves.

## Guardrails
- Do not present the whole dataset as if it were just the current month.
- Call out when the historical window is short.
