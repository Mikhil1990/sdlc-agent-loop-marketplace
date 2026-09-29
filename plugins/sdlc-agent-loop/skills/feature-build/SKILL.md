---
name: feature-build
description: "Use when the user has an approved Feature Planning task file and wants it implemented — e.g. 'build that' / 'go ahead and implement task.md' after the feature-planning skill produced one. Writes the code + tests as a patch yourself, self-checks it via change-impact, and — only after the user confirms and a test command passes — opens a draft PR. Never marks a PR ready for review or merges it."
disable-model-invocation: false
---

# Feature Build

Native invocation: a deterministic script gathers Product Understanding context, **you**
— this conversation — write the implementation (code + tests) as a single patch and the
Change Impact report for your own diff, and a second deterministic script applies the
patch on a branch, runs the sandbox tests, and opens a **draft** PR only if they pass.
Same pattern as `code-correction`: split into deterministic steps (context, apply) and
native reasoning (the actual implementation) so there's no nested `claude` CLI subprocess
call reasoning with none of this conversation's context.

**Repo profile:** if `.sdlc-agent*/AGENTS.md` exists at the repo root, read it first — it is the authoritative execution contract for this repository (build/test commands, local conventions) and, where it conflicts with anything else in this tree, this file wins.

## Prerequisites

- The target repo must be onboarded: `codebase-map.json` and
  `constitution/product/product-rules.md` must exist.
- An approved task file — normally `feature-plans/<slug>/task.md` from the
  `feature-planning` skill, confirmed by the user. Don't build from an unconfirmed task
  file; ask first if it's unclear whether the plan was approved.
- `agent-cli` must be installed from the pinned release wheel (**not** an editable checkout):
  `uv tool install "agent-platform @ https://github.com/Mikhil1990/sdlc-agent-loop-marketplace/releases/download/v0.6.15/agent_platform-0.6.15-py3-none-any.whl"`,
  and `gh` authenticated for the target repo. See
  [the plugin README § Prerequisites](../../README.md#prerequisites) for the full list
  (`codebase-memory-mcp`, `AGENT_PLATFORM_API_URL` / `_PAT`, an onboarded repo);
  `agent-cli doctor` checks them.
- A test command that actually validates the target repo (e.g. `dotnet test`, `pytest -q`,
  `npm test`). Without one, write and show the patch but don't apply it — ask the user for
  the right test command.

## Step 0 — find the work, then admit the input packet (required, fails closed)

**Start with what is ready for you** (unit R19, ADR 0152 §5, spec phase-d/30 `tasks/07`),
never a bare "ask the user for a packet id":

```bash
uv run agent-cli ready-work
```

- `ready` — a signed plan with no successful build against it yet. Pick one (ask the user
  if more than one is ready) and use its `packet_id` below.
- `sent_back` — a plan the Tech Lead rejected, with a reason. Tell the user the reason and
  offer to revise it via the `feature-planning` skill, passing
  `--supersedes-packet-id <packet_id>` on the resubmit — do not build a sent-back plan.
- `waiting_on_questions` — a submission still waiting on a clarifying-question answer;
  nothing to build yet.

Once you have a `ready` item's `packet_id`, admit it — this reaches the exact same
validation function `agent-cli build --packet-id` uses, never a second copy. Feature Build
consumes a signed **`feature_spec`** packet — the Spec Plan the `feature-planning` skill
produced, ratified by the Tech Lead's approval of the `feature_spec_build` gate (unit D11,
[ADR 0101](../../../docs/decisions/0101-an-agent-input-is-admission-checked-against-an-approved-packet-and-it-fails-closed.md);
ADR 0151 §1 / ADR 0152 §4 moved the approving persona from the PM to the Tech Lead):

```bash
uv run agent-cli admit-packet --packet-id <feature_spec packet id> --expected-type feature_spec
```

- **Exit 0** → proceed. A human-declared `absent` packet still admits the build; tell the
  user the feature will read **yellow**
  ([ADR 0099](../../../docs/decisions/0099-the-typed-packet-is-the-unit-of-agent-to-agent-exchange-provenance-is-first-class.md) §4),
  never blocked.
- **Non-zero** → **stop and relay the refusal to the user verbatim.** It names the required
  packet type, the persona who owes it (`feature_planning`), that persona's assignment, and
  the three ways through: **sign it**, **upload it**, or **declare it `absent`**. There is
  no skip, force or offline flag.

If the feature has a **Feature Dossier**, admit its whole ratified required set in one call
instead — one command however many personas were ratified (unit D13,
[ADR 0103](../../../docs/decisions/0103-the-admission-boundary-reaches-every-gate-an-ingress-produces-a-packet-it-does-not-consume-one.md) §1):

```bash
uv run agent-cli admit-packet --dossier-id <dossier id>
```

This demands `ux_intent` exactly when `ux_designer` is in the ratified set, and never
otherwise. It **never** demands `test_plan`, even when `qa_test_owner` is ratified —
`test_plan` is the **QA merge gate**'s input, not a Step-0 input (the build has not written
any tests yet at Step 0; demanding it here would deadlock every dossier that ratifies QA).
That check runs later, in `agent-cli build --dossier-id`, immediately before its
`feature_build_pr` gate opens — this native skill path has no such gate (Step 4 above is a
conversational confirmation, not a DB approval), so it has nothing to hold that check. The
`test_plan` itself is drafted by a hosted job **after** `report-run` ingests this build's
succeeded, PR-carrying run — never inside this conversation or `agent-cli build` (unit U18,
ADR 0202) — so there is nothing for this skill to trigger or wait on.

Once admission has succeeded, report that the build has started — best-effort, fire and
forget (unit U23, ADR 0210 §4):

```bash
uv run agent-cli report-run --action build --status started --started-at <current UTC ISO 8601> \
  --dossier-id <the dossier id admitted above>   # or --packet-id, matching whichever this Step used
```

This call's output and exit code are not inspected — it never gates progression to Step 1,
and a failure (no PAT, host unreachable, anything else) is never surfaced in the build
narrative.

## Step 1 — gather context (deterministic, no LLM call)

```bash
uv run agent-cli plan-context --repo-path /path/to/repo --output build-context.json
```

Same command the `feature-planning` skill uses (reuse the file from that skill's run if
you already have one in this conversation) — `product_understanding` and
`product_rules_full`.

## Step 2 — write the implementation yourself (native reasoning, no subprocess)

Using the task file's content and the gathered context, implement the feature — write the
code changes and accompanying tests as a single unified diff — following the rules below.

The rules are the **single authored copy** of this agent's behavioural rules — rendered
here verbatim from `agent_core/agents/feature_build.py::SHARED_RULES` (ADR 0106), the same
text the subprocess path (`agent-cli build`) composes into its system prompt. "The Product
Understanding context" is the `product_understanding` field of the Step 1 JSON; "the
Product rules / constitution" is `product_rules_full`; "the Task File" is the approved
`task.md` you were pointed at.

<!-- BEGIN GENERATED: agent-rules feature_build -->
<!-- Generated by scripts/render_agent_rules.py from agent_core/agents/feature_build.py::SHARED_RULES (ADR 0106). Do not hand-edit: run `uv run python scripts/render_agent_rules.py --write`. -->

- Paths must be relative to the repo root; for edits to existing files, only touch files that are plausible given the Task File and Product Understanding context — do not invent unrelated files.
- Include tests for the new behavior in the same diff — never ship an implementation without a test.
- The Task File is an approved, ratified plan — implement it as written. Do not re-plan, re-scope, or substitute a different approach.
- The "Product rules / constitution" section is the target repository's repo profile (`.sdlc-agent*/AGENTS.md`) — its authoritative execution contract (build/test commands, local conventions). Follow it; do not introduce dependencies or patterns it prohibits, and where it conflicts with a convention you would otherwise assume, it wins.
- The repository may be in any language or stack. Match the language, test framework and layout the context shows — do not assume a stack it does not show.
- Keep the change scoped to what the Task File describes — no unrelated refactors.
- Explain what was implemented and how the tests cover it in 2-4 sentences; the first sentence should be usable standalone as a one-line PR title.
- If the Task File is too vague to implement safely, or cannot be implemented as written, give only that explanation of what's missing or blocking, and propose no patch — never silently build something else instead.

<!-- END GENERATED: agent-rules -->

The subprocess path emits the diff as a fenced ` ```diff ` block and the explanation under
a `## Explanation` heading; here, instead, write the patch to a file (e.g.
`.feature-build-patch.diff`) and the explanation (2-4 sentences, first sentence usable
standalone as a PR title) to a second file.

## Step 3 — self-check your own diff (native reasoning)

Before proposing the patch, run it through the same reasoning as the `change-impact`
skill's Step 2, treating your own patch as the diff under review (severity, downstream
impact, affected files). Feature Build closes the loop on itself rather than ending at
"here's an implementation" — surface anything 🔴/🟡 the self-check finds to the user
before Step 4, not just in the eventual PR body.

Write this report to a file too (e.g. `.feature-build-self-check.md`).

## Step 4 — confirm, then apply as a draft PR (deterministic, no LLM call)

**Show the user the patch, explanation, and self-check report before running anything.**
This mutates the repo the same way `code-correction`'s apply step does — confirm first.
This conversational confirmation is the human-in-the-loop gate; there's no separate
DB-approval-item flow for this native path.

Once confirmed:

```bash
uv run agent-cli apply-patch \
  --repo-path /path/to/repo \
  --patch-file .feature-build-patch.diff \
  --explanation-file .feature-build-explanation.txt \
  --impact-report-file .feature-build-self-check.md \
  --test-command dotnet test \
  --branch-prefix feature-build \
  --draft \
  --pr-title "Feature build: <one-line summary>" \
  --commit-message "feature-build: <one-line summary>"
```

This creates a `feature-build/<timestamp>` branch, applies the patch (`git apply --check`
first), runs the test command, and only if it exits 0 does it commit, push, and open a
**draft** `gh pr create --draft` — never marked ready for review or merged by this skill.
It always returns to the original branch afterward. If the patch doesn't apply, tests
fail, or push/PR creation fails, no PR is opened — the failure reason is in the printed
JSON's `detail` field.

## Step 5 — report the run

After `apply-patch` returns, record the run so it reaches the hosted run history
([ADR 0032](../../../docs/decisions/0032-all-surfaces-authenticate-through-the-hosted-app.md),
[ADR 0044](../../../docs/decisions/0044-native-skill-runs-report-through-an-authenticated-ingest-endpoint.md)).
Status comes from the `apply-patch` JSON, same rule as `code-correction`:

- `status == "proposed"` → `--status succeeded --pr <number parsed from pr_url>`
- anything else → `--status failed --error "<detail from the JSON>"`

```bash
uv run agent-cli report-run \
  --action feature-build --repo <repo dir name> --repo-path /path/to/repo \
  --status <succeeded|failed> [--pr <n>] [--error "<detail>"] \
  --started-at <ISO time you started Step 1> \
  --report-file .feature-build-self-check.md --context-file build-context.json \
  [--packet-id <the packet id you admitted at Step 0>] \
  [--dossier-id <the dossier id you admitted at Step 0>]
```

Pass whichever id form Step 0 actually used — `--packet-id` if you admitted one signed
packet, `--dossier-id` if you admitted a dossier's whole ratified set (unit D14,
[ADR 0107](../../../docs/decisions/0107-a-native-run-carries-the-admission-provenance-that-joins-it-to-its-work-request.md) §1)
— so the run in `/runs` can be joined back to the work request it was admitted against.
Both flags are optional; omitting them reports the run exactly as before.

Best-effort — `report-run` always exits `0`, spooling on failure. Never let it block
surfacing the draft-PR URL or the failure reason. Tell the user whether it reported
(`AGENT_PLATFORM_RUN_ID:` printed) or spooled (a `~/.agent-platform/spool/` warning); if
`AGENT_PLATFORM_PAT` isn't set it spools silently — mention
they can set it (from the web app's Settings screen) to see native runs in `/runs`.

## Output

Report the outcome plainly: whether a draft PR was opened (give the URL and say
explicitly it's a draft, not ready for review), or why not (patch didn't apply, tests
failed — show the tail of `test_output`). Never claim code was "shipped" or "merged" —
a human reviews the draft PR, marks it ready, and merges it themselves.

If the result carries a non-empty `profile_command_uninvokable` (unit D9, ADR 0098 §2/§3),
say so distinctly from an ordinary test failure: the test command itself could not run,
which means the repo profile is stale, not that the tests failed. Point at editing the
repo profile in the web app — never edit `.sdlc-agent*/AGENTS.md` directly, it is
overwritten on the next run.

The native path now records a run in `/runs` (Step 5). `agent-cli build` (a separate
subprocess CLI command that runs the same agent via its own LLM call) remains for
CI/headless use, the way `agent-cli impact` is.
