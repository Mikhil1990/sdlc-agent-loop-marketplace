---
name: incident-learning
description: "Use when you need to check whether a set of changed files have caused incidents before — e.g. before or during a change-impact review, or when the user asks 'has this code broken before?' / 'any past incidents here?'. Reads postmortem markdown files from a repo's incidents/ folder and correlates their root-cause files against the given changed files via git history. Requires the repo to be onboarded (repo-root) and a incidents/ folder of postmortems (MVP: local markdown, no live incident-tool integration yet)."
disable-model-invocation: false
---

# Incident Learning

Ingests postmortems from a local markdown folder (`<repo>/incidents/*.md`) and
correlates their root-cause files against a given set of changed/related files, so
past incidents can be cited on future changes that touch the same code — the
"this broke before" signal that `change-impact` uses to raise severity and
recommend safeguards.

This skill wraps `agent_core/agents/incident_learning.py` directly — no LLM call, no
API key required. `change-impact` already runs it automatically as part of its
`agent-cli impact` pipeline; use this skill standalone when you just want the raw
incident correlation (e.g. to sanity-check which incidents would fire, or the
change-impact skill isn't applicable).

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it
is the authoritative execution contract for this repository (build/test commands, local
conventions) and, where it conflicts with anything else in this tree, this file wins.

## Postmortem format

Each `incidents/*.md` file needs YAML frontmatter followed by a markdown body:

```markdown
---
title: Payment retry storm outage
date: 2024-11-12
severity: Sev1
summary: Retry logic lacked idempotency, duplicate charges under load.
files:
  - src/Services/Ordering/OrderService.cs
  - src/Services/Payment/PaymentRetryHandler.cs
# Alternative to `files`: give the fixing/breaking commit and let the agent
# resolve touched files via `git show --name-only <commit>`.
# commit: a1b2c3d
---

## Root cause
...

## Resolution
...
```

`files` is preferred (explicit, no repo history dependency); `commit` is a fallback
for when you only know which commit fixed or introduced the issue.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/incident-learning/scripts/run_incident_learning.py \
  --repo-path /path/to/onboarded/repo \
  --files src/Services/Ordering/OrderService.cs src/Services/Ordering/OrderDto.cs
```

Optional override if postmortems live somewhere other than `<repo-path>/incidents`:

```bash
  --incidents-dir /path/to/postmortems
```

## What happens

1. Reads every `*.md` file in the incidents folder; skips files without valid
   YAML frontmatter or a `title` field (logs a warning, doesn't fail the run).
2. Resolves each incident's touched files: uses `files` from frontmatter if given,
   otherwise runs `git show --name-only <commit>` to derive them.
3. Matches those files against the given `--files` (exact path or basename match,
   to tolerate scan-root prefix differences with `codebase-map.json`).
4. Returns only incidents with at least one matched file, as JSON
   (`IncidentRecord`: `title`, `date`, `severity`, `summary`, `files`, `commit`,
   `postmortem_path`, `matched_files`).

## When there's no incidents/ folder

If `<repo-path>/incidents` doesn't exist, the script returns an empty JSON list —
that's expected for a repo with no postmortem history yet, not an error. Don't tell
the user to create one unless they're specifically setting up incident tracking.

## Output

Print the JSON and summarize in prose: which incidents matched, their severity and
date, and which of the given files triggered the match. If the result feeds into a
change-impact review, mention that explicitly rather than treating this as a
standalone final answer.

## Report the run

When this skill was run standalone (not as a sub-step of `change-impact`, which reports
its own run), record it so it reaches the hosted run history
([ADR 0032](../../../docs/decisions/0032-all-surfaces-authenticate-through-the-hosted-app.md),
[ADR 0044](../../../docs/decisions/0044-native-skill-runs-report-through-an-authenticated-ingest-endpoint.md)):

```bash
uv run agent-cli report-run \
  --action incident-learning --repo <repo dir name> --repo-path /path/to/repo \
  --status succeeded --started-at <ISO time you started the correlation>
```

Add `--report-file <path>` if you wrote the correlation summary to a file, and
`--context-file <path>` only if you also ran `agent-cli context` in this session (this
skill has no context JSON of its own). Best-effort — `report-run` always exits `0` and
spools to `~/.agent-platform/spool/runs.jsonl` on failure; never let it block the
correlation output. Tell the user whether it reported (`AGENT_PLATFORM_RUN_ID:` printed)
or spooled; if `AGENT_PLATFORM_PAT` isn't set it spools
silently — they can set it (from the web app's Settings screen) to see native runs
in `/runs`.

## Proposing a constitution guardrail from an incident

If, while reasoning about a matched incident, you conclude the codebase should carry
a new rule (e.g. "renaming a field consumed by three services should require a
cross-service check"), propose it as a human-reviewed approval rather than editing
`product-rules.md` yourself — no code path may write it without approval
([phase-3/05](../../../docs/constitution/specs/phase-3/05-policy-guardrail-flow/spec-plan.md)).
This agent stays deterministic; the RCA reasoning and the guardrail wording are yours
to produce, not a model call inside the agent:

```bash
python3 -m agent_core.cli propose-guardrail \
  --repo-path /path/to/onboarded/repo \
  --category ask_first \
  --rule-text "Renaming a field on a shared contract requires a cross-service check." \
  --source-incident incidents/2026-07-14-checkout-500s.md \
  --implicated-files src/Ordering/Domain/Order.cs \
  --rationale "Three services consumed this field; none were updated."
```

`--category` is one of `always_do` | `ask_first` | `never_do` — the vocabulary
`product-rules.md` already uses. This creates a pending `policy_guardrail` approval
in the inbox and returns its id; it does not write anything itself. Only propose a
rule when the incident clearly implies one — an incident that doesn't isn't required
to produce a guardrail.
