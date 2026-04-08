---
name: movement-ingestion
description: Use this skill when the user wants to add bank movements from statement PDFs, receipt images, or natural-language transaction descriptions.
---

# Movement Ingestion

## When To Use
- The user attaches a bank statement PDF.
- The user attaches a receipt or scontrino image.
- The user writes one or more movements in natural language and wants them saved.

## Workflow
1. Read the attachment or text in the root agent.
2. Extract only reliable movements.
3. Preserve useful provenance details in `note`.
4. Save with `aggiungi_movimenti`.
5. Report duplicates handled by the tool result.

## Guardrails
- Do not delegate multimodal ingestion to subagents.
- Do not save a movement if date, amount or description are still unclear.
- For receipts, store the expense as a negative amount.
