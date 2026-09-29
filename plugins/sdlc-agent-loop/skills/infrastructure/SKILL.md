---
name: infrastructure
description: "Use when the user asks what is running in an org's cloud (Azure, AWS or GCP), or wants presence/absence drift between declared infrastructure templates and the live account narrated. Read-only: it lists resources and answers a question grounded only in that read — it proposes no change and issues no cloud mutation. Needs a customer-granted read-only cloud credential (Azure Reader / AWS ReadOnlyAccess / GCP roles/viewer)."
disable-model-invocation: false
---

# Infrastructure Agent (read-only cloud inventory + drift)

Track C's "cloud operations" read half ([ADR 0061](../../../docs/decisions/0061-cloud-operations-is-three-agents-two-solution-proposers-and-one-problem-finder.md),
spec phase-b/21 unit R6). It reads a live cloud account and narrates it. It **never**
mutates a cloud resource and — in this unit — proposes no change. A change plan is a
separate later capability with its own SRE/Ops approval gate.

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it is the authoritative execution contract for this repository (build/test commands, local conventions) and, where it conflicts with anything else in this tree, this file wins.

## Prerequisites

- `agent-cli` installed from the pinned release ref (see [the plugin README § Prerequisites](../../README.md#prerequisites)).
- A **read-only** cloud credential the customer has granted, resolved through
  `SecretResolver` + the tenant environment exactly as the Azure drift check already does:
  - Azure: role **Reader** — `AGENT_AZURE_TENANT_ID` / `AGENT_AZURE_CLIENT_ID` / `AGENT_AZURE_CLIENT_SECRET`, or a Key Vault named by the tenant.
  - AWS: policy **`ReadOnlyAccess`** (or `ViewOnlyAccess`) — `AGENT_AWS_REGION` / `AGENT_AWS_ACCESS_KEY_ID` / `AGENT_AWS_SECRET_ACCESS_KEY`.
  - GCP: role **`roles/viewer`** — `AGENT_GCP_*` / a tenant secret-manager project.
  The adapter raises a named error if the credential is missing or lacks read; it never
  falls back to a broader credential.
- The matching SDK extra: `uv sync --extra azure-mgmt｜aws-mgmt｜gcp-mgmt`.

## Step 1 — run the read

```bash
# Live inventory for one cloud
uv run agent-cli infra-audit --cloud aws --repo-path /path/to/repo

# Ask a question, answered only from the structured read
uv run agent-cli infra-audit --cloud azure --question "what compute is running in prod" --repo-path /path/to/repo

# Azure only: also diff against Bicep-declared resources (presence/absence)
uv run agent-cli infra-audit --cloud azure --live --subscription-id <sub> --resource-group <rg> --repo-path /path/to/repo
```

`--dry-run` prints the inventory and narration without writing a run or an Activity report.
Drift narration is Azure + Bicep only; for AWS/GCP the drift section is empty (widening it
to Terraform/CloudFormation is a separate decision).

**This step PRODUCES a `deployment_view` packet** (unit D13,
[ADR 0103](../../../docs/decisions/0103-the-admission-boundary-reaches-every-gate-an-ingress-produces-a-packet-it-does-not-consume-one.md)
§6) — a non-dry-run success writes one `draft` packet carrying `resources` and, when a
live drift check ran, `drift`, and prints its id. This agent **consumes no packet and has
no Step 0** — it produces and proposes nothing (VD11). Tell the user to have a human with
the `sre_ops` slot sign the packet (`POST /api/packets/{id}/sign`, or the dossier's
Required Inputs panel) before the `devops` skill's proposal steps can admit it.

## Step 2 — read the report

The command prints a Markdown digest (`## Summary`, `## Inventory`, `## Drift`,
`## Answer`). Without `--dry-run` it is also persisted via `create_audit_report(kind="infra")`
and shows in **Activity** (it is a run type, not an approval — it opens no Inbox item).

Surface the digest to the user as-is. The agent is grounded: it names only resources in the
structured read. If it flags something worth changing it says so in words — it does not, in
this capability, emit commands or a change plan.

## Step 3 — report the run

```bash
uv run agent-cli report-run \
  --action infra-audit --repo <repo dir name> --repo-path /path/to/repo \
  --status succeeded --started-at <ISO time you started Step 1> \
  --report-file <the digest you saved>
```

Best-effort by construction — `report-run` always exits `0`; it spools and retries if the
backend is unreachable. Never let it delay showing the user the digest.
