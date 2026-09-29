---
name: feature-planning
description: "Use when a user describes a feature they want in plain language and wants a spec + task breakdown before any code gets written — e.g. 'I want users to be able to X' / 'can you plan out Y'. Gathers repo context deterministically, then you (the current Claude Code session) ask clarifying questions on demand, only when the answer changes what you produce next, and write the Spec Plan + Task File yourself. Pulled forward from the platform's Phase 2 into the six-agent wedge loop; the output feeds the feature-build skill."
disable-model-invocation: false
---

# Feature Planning

Native invocation: a deterministic script gathers Product Understanding context (and
falls back to the whole product constitution when no specific files are known yet), and
**you** — this conversation — turn the feature request into a Spec Plan and Task File,
asking clarifying questions first if the request is underspecified. Same pattern as the
`change-impact`/`code-correction` skills: a deterministic CLI step for context, native
reasoning for the actual planning — no nested `claude` CLI subprocess call.

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it is the authoritative execution contract for this repository (build/test commands, local conventions) and, where it conflicts with anything else in this tree, this file wins.

## Prerequisites

- The target repo must be onboarded: `codebase-map.json` and
  `constitution/product/product-rules.md` must exist (`uv run agent-cli onboard-repo --repo-url
  <url>` if not).
- `agent-cli` must be installed from the pinned release wheel (**not** an editable checkout):
  `uv tool install "agent-platform @ https://github.com/Mikhil1990/sdlc-agent-loop-marketplace/releases/download/v0.6.15/agent_platform-0.6.15-py3-none-any.whl"`.
  See [the plugin README § Prerequisites](../../README.md#prerequisites) for the full list
  (`codebase-memory-mcp`, `AGENT_PLATFORM_API_URL` / `_PAT`, an onboarded repo);
  `agent-cli doctor` checks them. `agent-cli plan-context` does no LLM/network call — only
  reads the local codebase-map/product-rules files.

## Step 0 — admit the input packet (required, fails closed)

Feature Planning consumes a signed **`feature_intent`** packet — the Business
Stakeholder's ratified statement of what they want (unit D11,
[ADR 0101](../../../docs/decisions/0101-an-agent-input-is-admission-checked-against-an-approved-packet-and-it-fails-closed.md)).
Ask the user for its id and check it **before anything else** — this reaches the same one
validation function the headless `agent-cli build` path uses, never a second copy:

```bash
uv run agent-cli admit-packet --packet-id <feature_intent packet id> --expected-type feature_intent
```

If the feature has a **Feature Dossier**, admit its **whole ratified required set in one
call** instead — one command however many personas the architect ratified, and the skill
needs to know no persona vocabulary (unit D13,
[ADR 0103](../../../docs/decisions/0103-the-admission-boundary-reaches-every-gate-an-ingress-produces-a-packet-it-does-not-consume-one.md) §1):

```bash
uv run agent-cli admit-packet --dossier-id <dossier id>
```

Exit 0 ⇒ every ratified packet is admitted (or the ratified set is empty — proceed).
Non-zero ⇒ the refusal names the **first** failing type; relay it verbatim. A dossier
whose level-1 gate has not been approved has no ratified set and is refused — approve
level 1 first.

- **Exit 0** → proceed. If the line says the packet is a human-declared `absent`, continue
  anyway, but tell the user the resulting feature will read **yellow**
  ([ADR 0099](../../../docs/decisions/0099-the-typed-packet-is-the-unit-of-agent-to-agent-exchange-provenance-is-first-class.md) §4) —
  never blocked.
- **Non-zero** → **stop and relay the refusal to the user verbatim.** It names the required
  packet type, the persona who owes it (`business_stakeholder`), that persona's assignment,
  and the three ways through: **sign it** (a human with that slot signs the packet),
  **upload it** (the customer produced the document themselves), or **declare it `absent`**
  (the customer declined the step — the feature then reads yellow, never blocked). Do not
  plan without one; there is no skip, force or offline flag.

If the user has no packet id and this repo is not connected to a hosted app, Feature
Planning cannot run — the check fails closed with no offline override, and that cost is
accepted (ADR 0101 §2 / VD3).

## Step 1 — gather context (deterministic, no LLM call)

```bash
uv run agent-cli plan-context \
  --repo-path /path/to/repo \
  --files src/Services/Ordering/OrderService.cs \
  --output plan-context.json
```

`--files` is optional — pass any files you already suspect are related (from earlier
conversation or a quick look at the repo) to scope the `product_understanding` field;
omit it and you'll still get `product_rules_full` (the whole product-rules.md) to ground
on.

## The rules you plan under

These are the **single authored copy** of this agent's behavioural rules — rendered here
verbatim from `agent_core/agents/feature_planning.py::SHARED_RULES` (ADR 0106), the same
text the subprocess path (`agent-cli plan`) composes into its system prompt. Before this
was generated the native planning skill had **no** rule set at all; the second bullet is
the one that changed how this skill behaves. "The provided context" / "the Product
Understanding context" is the `product_understanding` field of the Step 1 JSON; "the
Product rules / constitution" is `product_rules_full`; "Past incidents" is `past_incidents`
(with `incident_blind_spots` naming any postmortem that could not be correlated at all).

<!-- BEGIN GENERATED: agent-rules feature_planning -->
<!-- Generated by scripts/render_agent_rules.py from agent_core/agents/feature_planning.py::SHARED_RULES (ADR 0106). Do not hand-edit: run `uv run python scripts/render_agent_rules.py --write`. -->

- Ask at the point where the answer changes what you produce next, and not before.
  Never ask what a later stage will know better. Mark each question `blocking` if you
  cannot produce this artifact without its answer; otherwise state your working
  assumption, mark it `assumed`, and carry on.
- Scope is settled before you are called: the request reaching you has been ratified by
  its stakeholders. Ask clarifying questions about *how* to build it, never about whether
  it should be built.
- Tag each clarifying question with who should answer it and why (see the tag-format and
  purpose rules below) — never leave a question untagged when you know who owns it.
- The "Product rules / constitution" section is the target repository's repo profile
  (`.sdlc-agent*/AGENTS.md`) — its authoritative execution contract (build/test commands,
  local conventions). Plan within it; where it conflicts with a convention you would
  otherwise assume, it wins.
- The repository may be in any language or stack. Do not assume a framework, build tool,
  or directory layout the context does not show.
- Ground every claim in the provided context; do not invent files, modules, or endpoints
  that aren't in the Product Understanding context.
- When the "Past incidents" section is non-empty, the files it names have caused a
  production failure before. Say so in the Spec Plan where it changes the plan — an extra
  acceptance criterion, a regression to guard, a task ordered earlier — and do not cite an
  incident that does not touch the code this feature changes.
- unit U21 (ADR 0208 §2): name a risk in the optional `## Risks` section only when the
  incidents, the touched blocks, or the spec itself give you a reason for it — never for
  its own sake. Omit the section entirely when nothing grounds one.

- Tag each clarifying question with the persona AND the kind of question it is, in the
  format `[persona|kind] <question>`. The admissible persona|kind pairs are:
  `product_manager|product_intent`, `domain_expert|business_rule`,
  `business_stakeholder|scope_priority`, `tech_lead|technical`, `architect|technical`,
  `qa_test_owner|test_adequacy`, `ux_designer|ux`, `security_compliance|security_constraint`.
- Before asking, apply three tests. Settled? If the feature's own record (a prior
  answer, a learning, a resolved gate's decision) already answers it, do not ask — use
  the record and cite it. Inferable? If the framing context or the artifact inputs
  answer it, do not ask — proceed and state the assumption. Purposeful? Say what the
  answer changes; a question whose answer would not alter what this gate produces is
  not asked.
- Frame every question in the feature's own accumulated record — the prior clarifying
  answers, the past incidents, the dossier learnings, and the Feature Brief already in
  your context — never in a vacuum. A question may build on a recorded answer, sharpen
  one, or challenge one; it may not ignore one.
- Word each question in its target persona's own register, never in code terms for a
  business persona:
  `business_stakeholder`: outcomes, revenue, risk and timing — never a code identifier,
  field, table, enum, file, library or refactor.
  `product_manager`: user flows, acceptance criteria and intended behaviour — never a
  code identifier, field, table, enum, file, library or refactor.
  `domain_expert`: real-world cases, exceptions and business policy — never a code
  identifier, field, table, enum, file, library or refactor.
  `ux_designer`: user-facing flow, layout and wording — never a code identifier, field,
  table, enum, file, library or refactor.
  `tech_lead`: code structure, seams, dependencies and implementation trade-offs — may
  be asked in technical terms.
  `architect`: modules, seams, data flow and structural cost — may be asked in
  technical terms.
  `qa_test_owner`: coverage, edge cases and what a test plan proves or misses — may be
  asked in technical terms.
  `security_compliance`: access control, data handling and regulatory exposure — may be
  asked in technical terms.

<!-- END GENERATED: agent-rules -->

They govern both Step 2 (what you may ask) and Step 3 (how you plan).

## Step 2 — ask about *how*, never *whether*

If the user pointed you at a feature request **document** (a PBI/ticket export, a written
spec draft, anything longer than a one-line description) rather than describing the
feature inline, Read that file first and treat its full contents as the request — don't
ask the user to re-type it.

**Whether** this feature should be built was already decided — at the level-1 gate
([ADR 0104](../../../docs/decisions/0104-work-is-a-human-written-request-with-a-kind-label-and-the-level-1-gate-is-its-single-intake-decision.md)),
before the packet you admitted in Step 0 was signed — so never ask the user to justify,
defend or re-scope the work, and never propose *not* building it. Your clarifying
questions are only ever about **how**: an acceptance criterion that is unclear or
untestable, a conflict with `product_rules_full`, an interface or data shape the request
leaves ambiguous. Ask at the point where the answer changes what you produce next, and
only for what you can't reasonably infer from the gathered context — a clear request
with settled scope needs zero.

## Step 3 — write the Spec Plan and Task File yourself (native reasoning, no subprocess)

Once you have enough information, produce both, grounded only in real files/modules from
`product_understanding` (don't invent ones that aren't there):

- **Spec Plan** — goal, scope, acceptance criteria, explicit out-of-scope items.
- **Task File** — an ordered checklist of concrete implementation tasks, referencing real
  files/modules where possible, sized for the `feature-build` skill to implement as one
  patch.

Name a risk in the Spec Plan only when the past incidents, the touched blocks, or the
spec itself give you a reason for it (unit U21, ADR 0208 §2) — never for its own sake,
and never one that does not touch the code this feature changes.

Write both to files (e.g. `feature-plans/<slug>/spec.md` and
`feature-plans/<slug>/task.md` in the repo root) using the Write tool.

## Step 4 — report the run

After both documents are written, record the run so it reaches the hosted run history
([ADR 0032](../../../docs/decisions/0032-all-surfaces-authenticate-through-the-hosted-app.md),
[ADR 0044](../../../docs/decisions/0044-native-skill-runs-report-through-an-authenticated-ingest-endpoint.md)).
This is best-effort by construction — `agent-cli report-run` always exits `0`; if it
can't reach the backend it spools to `~/.agent-platform/spool/runs.jsonl` and retries on
the next call. **Never let this step delay showing the user the documents from Step 3.**

```bash
uv run agent-cli report-run \
  --action feature-planning --repo <repo dir name> --repo-path /path/to/repo \
  --status succeeded --started-at <ISO time you started Step 1> \
  --context-file plan-context.json \
  [--packet-id <the packet id you admitted at Step 0>] \
  [--dossier-id <the dossier id you admitted at Step 0>]
```

Pass whichever id form Step 0 actually used — `--packet-id` for a single admitted
`feature_intent` packet, `--dossier-id` for a dossier's whole ratified set (unit D14,
[ADR 0107](../../../docs/decisions/0107-a-native-run-carries-the-admission-provenance-that-joins-it-to-its-work-request.md) §1)
— so the run in `/runs` can be joined back to the work request it was admitted against.
Both flags are optional; omitting them reports the run exactly as before.

Then tell the user which happened:
- `AGENT_PLATFORM_RUN_ID:<id>` on stdout → reported; the run is in `/runs`.
- a stderr warning about `~/.agent-platform/spool/` → spooled, will flush on the next run.
- nothing printed and no warning → `AGENT_PLATFORM_PAT` isn't
  set, so it spooled silently. Mention the user can set it (from the web app's
  Settings screen) to see native runs in `/runs`.

## Output

Show the user both documents and ask them to confirm/edit the draft. **This confirmation
is no longer the approval** (unit R19, ADR 0152 §3/§4, ADR 0107 §3 — an in-chat
confirmation was never recorded anywhere the app could see it). Once the user confirms,
submit the draft:

```bash
uv run agent-cli submit-plan \
  --spec-file feature-plans/<slug>/spec.md --task-file feature-plans/<slug>/task.md \
  --summary "<one-line summary of the feature>" \
  --submission-key "<a key you won't reuse for a different draft>" \
  --dossier-id <the dossier id you admitted at Step 0> \
  [--supersedes-packet-id <packet id, when revising a plan the Tech Lead sent back>]
```

Requires `AGENT_PLATFORM_PAT` — there is no offline fallback for this call; the result has
to reach the app (ADR 0152 consequences). Exit `0` prints `{"packet_id", "approval_id",
...}`: tell the user the plan is submitted and the Tech Lead marks it ready to build in
the app (linking the approval if the SPA URL is known). Exit non-zero: relay the error
verbatim — the drafted files are kept on disk (never spooled, Review Note 8), so the user
can ask you to retry the submit once whatever blocked it is fixed. Offer the
`feature-build` skill as the natural next step once the Tech Lead approves.

## Multi-repo features — the level-2 session (unit D13, ADR 0103 §5)

When a feature's Feature Dossier scopes it across **more than one repo** (a level-1
decision named several `repo_connection_id`s), each repo's plan runs as its **own**
`agent-cli level-2` invocation — never this skill's Step 0/1/3 directly, and never
`agent-cli plan` — one door, always (ADR 0031):

```bash
uv run agent-cli level-2 \
  --handoff-packet-id <this repo's signed repo_handoff packet id> \
  --repo-connection-id <this repo's connection id> \
  --repo-path /path/to/this/repo
```

This is enqueued **once per repo** automatically when a human approves the dossier's
`level_1_decision` gate — you would only run it by hand to retry or inspect one repo's
session. It admits the hand-off **keyed on that repo's connection** (another repo's
packet id is refused, `wrong_addressee`), plans against the hand-off's `slice` and
`seam_contracts` — not the whole feature description — and produces **that repo's own**
`feature_spec`, which opens the identical `feature_spec_build` gate and is admitted by
the per-repo `agent-cli build --dossier-id` unchanged. Non-zero exit → relay the refusal
verbatim, same shape as Step 0 above.
