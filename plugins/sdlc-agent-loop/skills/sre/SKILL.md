---
name: sre
description: "Use when the user wants a reliability-posture read for an org — what is at risk, what changed, what to check before a release — pulling together cloud drift, CI pipeline health, the latest architecture-compliance audit, and recent incidents. Read-only and propose-nothing: the SRE agent is a problem-finder. It emits a digest and stops; it never proposes a change, opens no approval gate, runs no command. Infrastructure / DevOps propose the fixes; a human ratifies the posture."
disable-model-invocation: false
---

# SRE Agent (reliability-posture digest — problem-finder only)

Track C's one problem-finder ([ADR 0061](../../../docs/decisions/0061-cloud-operations-is-three-agents-two-solution-proposers-and-one-problem-finder.md) §1,
spec phase-b/25 unit R10). It assembles what units R6, R8 and the architecture-compliance
audit already know into one **reliability-posture digest** and stops there. It **proposes
no remediation** — no commands, no change plan, no approval gate.

This agent consumes no packet and produces none (unit D13, [ADR 0103](../../../docs/decisions/0103-the-admission-boundary-reaches-every-gate-an-ingress-produces-a-packet-it-does-not-consume-one.md)
§6 / VD11) — it has no Step 0 admitting a `deployment_view`, unlike `devops`, because it
never opens an approval for anyone to admit anything against ([ADR 0061](../../../docs/decisions/0061-cloud-operations-is-three-agents-two-solution-proposers-and-one-problem-finder.md)
§1: a problem-finder that opens no approval has no gate to guard).

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it is the authoritative execution contract for this repository (build/test commands, local conventions) and, where it conflicts with anything else in this tree, this file wins.

## Prerequisites

- `agent-cli` installed from the pinned release ref.
- Optional read credentials (each source is skipped and recorded as absent when missing,
  never an error):
  - a read-only cloud credential (as for the `infrastructure` skill) for the R6 inventory
    + drift signal;
  - a CI read credential (as for the `devops` skill) for the R8 pipeline-runs signal.
- The architecture-compliance audit and incident signals are read from local state
  (`agent-cli audit` output; `<repo>/incidents/*.md`).

## Step 1 — run the digest

```bash
uv run agent-cli sre-digest --cloud aws --system github --repo-path /path/to/repo
uv run agent-cli sre-digest --repo-path /path/to/repo          # pipeline + audit + incidents only
```

`--dry-run` prints the digest without writing a run or an Activity report. Without
`--dry-run` it persists via `create_audit_report(kind="reliability")` and shows in
**Activity** (a run type — **not** an approval; it opens no Inbox item).

## Step 2 — read the digest

The command prints a Markdown digest with fixed headings `## Reliability Posture`,
`## Risks` (each risk names its signal source and a severity), `## Check Before Release`.
Surface it to the user as-is. Where the agent flags a fix, it names which agent
(Infrastructure / DevOps) could propose one — it does not propose it, and neither should
you from this skill.

This digest is the release-readiness content unit **D4**'s §11 Deployment-View sign-off
will ratify. D4 is not built yet; until then the digest stands alone as an Activity record.

## Step 3 — report the run

```bash
uv run agent-cli report-run \
  --action sre-digest --repo <repo dir name> --repo-path /path/to/repo \
  --status succeeded --started-at <ISO time you started Step 1> \
  --report-file <the digest you saved>
```

Best-effort — `report-run` always exits `0`; it spools and retries if the backend is
unreachable.
