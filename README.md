# Structured notes → review queue

An original, AI-assisted n8n demonstration using synthetic structured meeting exports. It prepares task, calendar and email **proposal records** for review. All proposals remain `pending_human_review`.

This is a capability sample, not a client deployment. It does not extract action items from free-form notes, call an LLM, authenticate a reviewer, send email, change a calendar or connect to Notion. No credentials or real household/customer data are included.

## What it demonstrates

- Validate required fields and UTC timestamps, including impossible dates and reversed event times.
- Keep source references and input positions with the resulting records.
- Account for exact repeats explicitly.
- Quarantine every member of a conflicting source-ID group, avoiding a first/last-write winner.
- Continue processing other records when individual records are invalid.
- Keep instruction-like and HTML-looking note content as literal JSON data.
- Produce the same result for an identical input without external effects.

Eight synthetic rows should produce **three pending proposals, one duplicate and four rejected rows**: two conflicting rows and two invalid rows. Additional cases replay the batch, reverse its order, reject an invalid batch shape and reject missing-timezone/equal/reversed calendar times.

Duplicate handling applies to this input batch only. Re-running the workflow produces the queue again; there is no persistent deduplication store, concurrency protection or authenticated approval gate.

## Inspect or reproduce

`workflow.json` is importable into n8n. Leave it inactive and run its Manual Trigger to inspect each node. It has only a Manual Trigger and JavaScript Code nodes.

The manual-only GitHub Actions workflow uses the official n8n **2.43.6** image on a standard hosted Linux runner. It pulls the versioned image, records its digest, then imports and executes the fixture in one disposable container with external networking disabled and no published ports. No service is left running.

The independent verifier reads actual n8n execution data, checks that every expected node ran, and checks the final fixture accounting and proposal records. An exit code or workflow-definition export alone is insufficient.

The workflow uses no paid API, model, artifact upload, Actions cache, larger runner or self-hosted runner. GitHub documents standard hosted execution in public repositories as free; logs and job summaries do not count as artifact storage. Runtime tools retain their own licenses.

## Validation status

A [real hosted execution](https://github.com/adamayub4-hue/n8n-structured-review-demo/actions/runs/38833133929) passed on 16 October 2026: all four native n8n nodes completed successfully, **17 acceptance checks across five cases passed**, and the independent verifier checked the actual execution data. [Saved result](verified-result.json). The baseline produced three pending proposals, one duplicate and four exceptions; the three timestamp edge records were also rejected.

The [earlier run](https://github.com/adamayub4-hue/n8n-structured-review-demo/actions/runs/38832601948) failed to capture evidence because the CLI logging level suppressed its JSON output. Changing only that level to `info` resolved it; the workflow and verifier assertions were unchanged. The failure remains visible.

To reproduce on the hosted runner: open **Actions → Verify real n8n execution → Run workflow**, select `main`, and read the job summary. The expected final status is `verified_native_execution`; a failed run does not establish success.

## Moving toward a real integration

A paid deployment needs its own agreed input schema, privacy boundaries, durable idempotency, authenticated review, provider permissions, acceptance tests and operating instructions. These are not supplied by the synthetic demonstration.

References: [n8n CLI](https://docs.n8n.io/deploy/host-n8n/configure-n8n/use-the-command-line/), [official release](https://github.com/n8n-io/n8n/releases/tag/n8n%402.43.6), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
