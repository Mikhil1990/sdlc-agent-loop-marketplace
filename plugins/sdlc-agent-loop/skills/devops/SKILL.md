---
name: devops
description: "Use when the user wants an org's CI/CD pipelines (GitHub Actions, Azure Pipelines, AWS CodePipeline) read and narrated, a failed pipeline run re-run, or a new pipeline authored for a repo. Read + propose only: it reads pipeline state, and for a re-run or a new pipeline it emits a reviewable ChangeProposal + a draft PR for a human to apply — it never triggers a pipeline or deploys one. The re-run/author gate is the org's SRE/Ops approver."
disable-model-invocation: false
---

# DevOps Agent (pipeline read + re-run proposal + pipeline authoring)

One of Track C's two solution-proposers ([ADR 0061](../../../docs/decisions/0061-cloud-operations-is-three-agents-two-solution-proposers-and-one-problem-finder.md) §1,
specs phase-b/23 unit R8 + phase-b/24 unit R9). It **reads** an org's CI pipelines and
recent runs and **proposes** a re-run or a new pipeline file. It never triggers a run,
never deploys, issues no mutating call ([ADR 0057](../../../docs/decisions/0057-cloud-operations-is-a-read-and-propose-track-the-org-iam-is-the-write-gate.md)).

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it is the authoritative execution contract for this repository (build/test commands, local conventions) and, where it conflicts with anything else in this tree, this file wins.

## Prerequisites

- `agent-cli` installed from the pinned release ref (see [the plugin README § Prerequisites](../../README.md#prerequisites)).
- A **read** credential the customer has granted, resolved through the same paths the rest
  of the platform uses — never a broader credential:
  - GitHub Actions: the GitHub App installation token already used for PR comments
    (`GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` / `GITHUB_APP_INSTALLATION_ID`), or
    `GITHUB_TOKEN` with `actions:read`.
  - Azure Pipelines: the tenant's ADO PAT with **Build (read)** scope (`ADO_PAT`,
    `ADO_ORG_URL`, `ADO_PROJECT`).
  - AWS CodePipeline: R6's `AGENT_AWS_*` read credential (`ReadOnlyAccess` covers it);
    `uv sync --extra aws-mgmt`.

## Step 1 — read the pipelines

```bash
uv run agent-cli pipeline-audit --system github --repo-path /path/to/repo
uv run agent-cli pipeline-audit --system github --question "which deploy pipelines failed this week" --repo-path /path/to/repo
```

`--dry-run` prints the narration without writing a run or an Activity report. Without
`--dry-run` the digest persists via `create_audit_report(kind="pipeline")` and shows in
**Activity** (a run type, not an approval).

## Step 1.5 — admit the `deployment_view` packet (unit D13, ADR 0103 §6)

**BREAKING.** Steps 2 and 3 below post a `ChangeProposal` that opens a `cloud_change`
approval, and both now require `--packet-id` naming a signed `deployment_view` packet —
the read the `infrastructure` skill's `agent-cli infra-audit --cloud ...` produces and a
human with the `sre_ops` slot signs. Admit it first so a refusal surfaces before any
proposal is built:

```bash
uv run agent-cli admit-packet --packet-id <id> --expected-type deployment_view
```

A non-zero exit means the packet is missing, unsigned, the wrong type, or the hosted app
is unreachable — relay the diagnostic verbatim and stop; there is no override flag. The
Infrastructure agent produces this packet and consumes none itself — do not ask it to run
this check. Neither does the SRE agent, which opens no approval and proposes nothing
([ADR 0061](../../../docs/decisions/0061-cloud-operations-is-three-agents-two-solution-proposers-and-one-problem-finder.md)
§1).

## Step 2 — propose a re-run (never trigger one)

```bash
uv run agent-cli pipeline-rerun-proposal --system github --run <run id> --packet-id <id> --repo-path /path/to/repo
```

This prints a `ChangeProposal` whose **Commands** section is the literal re-run invocation
(`gh run rerun <id>`) for **you** to run in your terminal, plus a read-only
`expected_check` the platform runs afterward to confirm your re-run started. `--packet-id`
is admitted again inline before anything posts (the same one check, VD11 — no second
copy); missing or unadmitted ⇒ exit 1, no HTTP POST, no approval. Without `--dry-run` a
successful post opens one `cloud_change` approval assigned to the org's **SRE/Ops**
approver
([ADR 0063](../../../docs/decisions/0063-the-sre-ops-approver-is-an-org-scoped-persona-slot-not-a-per-dossier-claim.md)).
There is no `--trigger` / `--now` flag — the platform never calls the re-run API.

## Step 3 — author a new pipeline (spec phase-b/24 unit R9)

```bash
uv run agent-cli pipeline-author --system github --packet-id <id> --repo-path /path/to/repo --open-pr
```

Inspects the repo's real build (its test command, language, Dockerfile) and drafts a
pipeline file grounded in it — never a template. `--open-pr` opens a **draft** PR of the
file using *your own* git credentials from this session; a human reviews and a human
deploys. No `--deploy` flag exists. Same `--packet-id` requirement and inline admission
as Step 2. `--open-pr` only works from a developer's own Claude Code — our servers refuse
it (ADR 0153 §4).

## Step 4 — report the run

```bash
uv run agent-cli report-run \
  --action pipeline-audit --repo <repo dir name> --repo-path /path/to/repo \
  --status succeeded --started-at <ISO time you started Step 1> \
  --report-file <the digest you saved>
```

Best-effort by construction — `report-run` always exits `0`; it spools and retries if the
backend is unreachable.
