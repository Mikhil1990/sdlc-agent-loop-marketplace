---
name: feature-build
description: "Use when the user wants a signed Design (spec plan + task file) from the web app built in their repo — e.g. 'build that' / 'what is ready for me?'. First tests the Design's evidence claims against the local code (Mode A) and routes open questions, then writes the code + tests as a patch yourself, self-checks it via change-impact, and — only after the user confirms and a test command passes — opens a draft PR and sends one build record back. Never marks a PR ready for review or merges it."
disable-model-invocation: false
---

# Feature Build

**If the repo has a `CLAUDE.md`, read it first and follow it for the whole run.**

Two modes in one skill. **Mode A** (Steps 0–3) tests the claims on the Design's evidence page
against the code in front of you and settles every open question. **Mode B** (Step 4) writes the
code, self-checks it, and opens a draft PR. Step 5 sends one build record to the web app.
Nothing comes back to this session after that (ADR 0252). Design itself happens in the web
app — never draft a spec plan or task file here.

Native invocation: a deterministic script gathers Product Understanding context, **you**
— this conversation — write the implementation (code + tests) as a single patch and the
Change Impact report for your own diff, and a second deterministic script applies the
patch on a branch, runs the sandbox tests, and opens a **draft** PR only if they pass.
Same pattern as `code-correction`: split into deterministic steps (context, apply) and
native reasoning (the actual implementation) so there's no nested `claude` CLI subprocess
call reasoning with none of this conversation's context.

**Repo profile:** `.sdlc-agent*/AGENTS.md` at the repo root is the authoritative execution contract for this repository (build/test commands, local conventions); where it conflicts with anything else in this tree, it wins. `agent-cli plan-context` (Step 4) writes it from the web app and prints it in its output, so on a first run it does not exist before Step 4. If it exists when the run starts, read it then; either way, read the copy Step 4 prints before you write the patch.

## Prerequisites

- The target repo must be onboarded: `codebase-map.json` and
  `constitution/product/product-rules.md` must exist.
- A Design the Tech Lead signed in the web app. Step 0 lists what is ready; Step 1 admits it
  and writes the work file. Never build from an unsigned plan.
- `agent-cli` must be installed from the pinned release wheel (**not** an editable checkout):
  `uv tool install "vyomgrid-agent-platform @ https://github.com/Mikhil1990/sdlc-agent-loop-marketplace/releases/download/v0.7.3/vyomgrid_agent_platform-0.7.3-py3-none-any.whl"`,
  and `gh` authenticated for the target repo. See
  [the plugin README § Prerequisites](../../README.md#prerequisites) for the full list
  (`codebase-memory-mcp`, `AGENT_PLATFORM_API_URL` / `_PAT`, an onboarded repo);
  `agent-cli doctor` checks them. If it says `agent-cli` is behind the newest version, tell the user to run the update lines in the README and update the plugin too, then stop.
- A test command that actually validates the target repo (e.g. `dotnet test`, `pytest -q`,
  `npm test`). Without one, write and show the patch but don't apply it — ask the user for
  the right test command.
  The repo profile's `Commands` section gives it. When that line reads `Test: not known — please
  fill this in`, say so, ask the user for the command, and tell them to add it in the web app
  under **Product → Repositories → this repository → Project notes (AGENTS.md)** so the next run
  has it. Never edit `.sdlc-agent*/AGENTS.md` directly — the next run overwrites it.

## Step 0 — find the work (read once, at the start of the run)

**Start with what is ready for you** (unit R19, ADR 0152 §5), never a bare "ask the user for a
packet id":

```bash
uv run agent-cli ready-work
```

Read the answer once. Do not call it again in a loop.

- `ready` — a signed plan with no successful build against it yet. Pick one (ask the user
  if more than one is ready); note its `packet_id`, its `dossier_id` and its `approval_id`.
- `asked_pending` — the questions **you** asked on earlier runs that are still open. Each entry
  has `approval_id`, `dossier_id`, `question`, `persona` and `assigned_to`. If the request you
  chose has an entry, name each question and who has it, then **stop**. Every question blocks
  (ADR 0218 §6). Run the skill again when the web app shows it answered.
- `answered_questions` — answers to questions you asked in an earlier session, from the last
  14 days. Read them before you write anything: they may change work you already did.
- `sent_back` — a plan the Tech Lead sent back, with a reason. Tell the user the reason and
  that revising happens in the web app. Do not build it.
- `waiting_on_tech_lead` — a plan the Tech Lead has not yet marked ready (signing the design
  does it). Tell the user it is with the Tech Lead; do not build it. Plans of a closed request
  are never listed.
- `waiting_on_questions` — a submission waiting on a clarifying-question answer; nothing to
  build yet.

## Step 1 — admit the signed packet and open the work file (required, fails closed)

Admit the packet. This reaches the same validation function `agent-cli build --packet-id`
uses, never a second copy. Feature Build consumes a signed **`feature_spec`** packet — the Spec
Plan from the web app's Design run, ratified by the Tech Lead's approval of the
`feature_spec_build` gate (unit D11,
[ADR 0101](../../../docs/decisions/0101-an-agent-input-is-admission-checked-against-an-approved-packet-and-it-fails-closed.md)):

```bash
uv run agent-cli admit-packet --packet-id <feature_spec packet id> --expected-type feature_spec \
  --approval-id <the approval id from ready-work> --print
```

- **Exit 0** → the last line printed is the path of the **work file**
  (`.sdlc-agent/work/<packet id>.md`). Open it. It holds four headings: `## Spec plan`,
  `## Evidence page`, `## Task file` and `## Mode A results`. An existing work file is kept, never
  overwritten, so your earlier Mode A results survive a stop. A human-declared `absent` packet
  still admits the build; tell the user the feature will read **yellow**
  ([ADR 0099](../../../docs/decisions/0099-the-typed-packet-is-the-unit-of-agent-to-agent-exchange-provenance-is-first-class.md) §4),
  never blocked.
- **Non-zero** → **stop and relay the refusal to the user verbatim.** It names the required
  packet type, the persona who owes it (`feature_planning`), that persona's assignment, and
  the three ways through: **sign it**, **upload it**, or **declare it `absent`**. There is
  no skip, force or offline flag.

If the feature has a **Feature Dossier**, you may admit its whole ratified required set in one
call as well — one command however many personas were ratified (unit D13,
[ADR 0103](../../../docs/decisions/0103-the-admission-boundary-reaches-every-gate-an-ingress-produces-a-packet-it-does-not-consume-one.md) §1):

```bash
uv run agent-cli admit-packet --dossier-id <dossier id>
```

This demands `ux_intent` exactly when `ux_designer` is in the ratified set, and never
otherwise. It **never** demands `test_plan` — that is the **QA merge gate**'s input, drafted by a
hosted job after `report-run` ingests this build's succeeded, PR-carrying run (unit U18,
ADR 0202), never in this conversation.

Once admission has succeeded, report that the build has started — best-effort, fire and
forget (unit U23, ADR 0210 §4):

```bash
uv run agent-cli report-run --action build --status started --started-at <current UTC ISO 8601> \
  --dossier-id <the dossier id>
```

This call's output and exit code are not inspected — it never gates progression, and a failure
is never surfaced in the build narrative.

## Step 2 — Mode A: test each evidence claim against the code

Read `## Evidence page` in the work file.

- If it says **"No claims to check for this request — …"**, say so to the user, write that line
  under `## Mode A results`, and go to Step 3's questions (if any) and then Step 4.
- Otherwise, for **each evidence item**, search the local code and write one result under
  `## Mode A results` in the work file:
  - **confirmed** — the code matches the statement.
  - **wrong** — give `path:line` and what the code actually does.
  - **not_testable** — say why (for example, it describes a runtime or business fact no code shows).

Show the developer the results. Ask the developer to confirm each **wrong** before you rely on
it. Keep the item ids (`E1`, `E2`, …) exactly as the page gives them — Step 5 sends them back.

## Step 3 — questions (every question blocks)

When a result or the task file raises a question you cannot settle from the code:

- A **simple tech question** the developer can answer from the code in front of them → ask the
  developer in this session. Write the answer under `## Mode A results`.
- A **complex tech question** (it crosses repos or seams, or changes the design) →
  `agent-cli ask --dossier-id <id> --question "[tech_lead|technical] <the question>"`, or
  `"[architect|technical] <the question>"` for an architecture question.
- A **product, business or scope question** → `agent-cli ask --dossier-id <id> --question
  "[<product persona>|<kind>] <the question>"` with the existing product personas.

**After any `ask`:** write the question and the approval id it returned into the work file, tell
the developer what you are waiting on and who has it, then **stop**. Do not continue to Mode B. The
next run starts at Step 0 and finds the question under `asked_pending` until it is answered.

## Step 4 — Mode B: write, self-check, apply

Only when Step 2 is done and no question of yours is open.

Check the branch first: `git rev-parse --abbrev-ref HEAD` must be the repository's default branch
(`gh repo view --json defaultBranchRef -q .defaultBranchRef.name`). If it is not, ask the user to
switch to it and pull before you write the patch — the PR targets the default branch (4.4).

### 4.1 — gather context (deterministic, no LLM call)

```bash
uv run agent-cli plan-context --repo-path /path/to/repo \
  --repo-connection-id <repo-connection-id> --dossier-id <request-id> --output build-context.json
```

Gives `product_understanding` and `product_rules_full` (reuse a file already in this
conversation). Pass `--repo-connection-id` and `--dossier-id` when you have them (the request id is
on the request's page, the repo connection id in Settings → Repos, with `AGENT_PLATFORM_PAT` set)
to also get `repo_docs`; read it and cite page keys in backticks.

### 4.2 — write the implementation yourself (native reasoning, no subprocess)

Using the task file's content (`## Task file` in the work file), your Mode A results and the
gathered context, implement the feature — write the code changes and accompanying tests as a
single unified diff — following the rules below. A claim marked **wrong** and confirmed by the
developer changes what you write: build on the code as it is, and say so in the explanation.

The rules are the **single authored copy** of this agent's behavioural rules — rendered
here verbatim from `agent_core/agents/feature_build.py::SHARED_RULES` (ADR 0106), the same
text the subprocess path (`agent-cli build`) composes into its system prompt. "The Product
Understanding context" is the `product_understanding` field of the 4.1 JSON; "the
Product rules / constitution" is `product_rules_full`; "the Task File" is the
`## Task file` heading of the work file.

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

### 4.3 — self-check your own diff (native reasoning)

Before proposing the patch, run it through the same reasoning as the `change-impact`
skill's Step 2, treating your own patch as the diff under review (severity, downstream
impact, affected files). Feature Build closes the loop on itself rather than ending at
"here's an implementation" — surface anything 🔴/🟡 the self-check finds to the user
before 4.4, not just in the eventual PR body.

Write this report to a file too (e.g. `.feature-build-self-check.md`).

### 4.4 — confirm, then apply as a draft PR (deterministic, no LLM call)

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
  --default-branch-base \
  --draft \
  --pr-title "Feature build: <one-line summary>" \
  --commit-message "feature-build: <one-line summary>"
```

This creates a `feature-build/<timestamp>` branch, applies the patch (`git apply --check`
first), runs the test command, and only if it exits 0 does it commit, push, and open a
**draft** `gh pr create --draft` — never marked ready for review or merged by this skill.
The PR targets the repository's default branch (`--default-branch-base`); when another
branch is checked out, it stops before touching anything and says which branch to switch to —
switch, pull, and write the patch against that branch. It always returns to the original branch afterward. If the patch doesn't apply, tests
fail, or push/PR creation fails, no PR is opened — the failure reason is in the printed
JSON's `detail` field.

## Step 5 — send the build record (one way)

After `apply-patch` returns, write `build-record.json` from the work file and record the run, so it
reaches the hosted run history and the digest
([ADR 0032](../../../docs/decisions/0032-all-surfaces-authenticate-through-the-hosted-app.md),
[ADR 0044](../../../docs/decisions/0044-native-skill-runs-report-through-an-authenticated-ingest-endpoint.md),
ADR 0252 §7). The file is one JSON object:

```json
{
  "tech_answers":     [{"question": "…", "answer": "…"}],
  "evidence_results": [{"id": "E1", "result": "confirmed|wrong|not_testable", "code_ref": "path:line", "note": "…"}],
  "changed":          [{"file": "…", "what": "…"}],
  "routed_questions": ["<approval id from each agent-cli ask>"]
}
```

- `tech_answers` — what the developer answered in the session.
- `evidence_results` — one entry per evidence item, with the id exactly as the page gave it. A
  `wrong` result **must** carry `code_ref`, or the server answers 422. Use `[]` when the work file
  said "No claims to check".
- `changed` — each file you changed and what changed in it.
- Each list holds at most 200 items and each text at most 2,000 characters.

Status comes from the `apply-patch` JSON, same rule as `code-correction`:

- `status == "proposed"` → `--status succeeded --pr <number parsed from pr_url>`
- anything else → `--status failed --error "<detail from the JSON>"`

```bash
uv run agent-cli report-run \
  --action feature-build --repo <repo dir name> --repo-path /path/to/repo \
  --status <succeeded|failed> [--pr <n>] [--error "<detail>"] \
  --started-at <ISO time you started Step 4.1> \
  --report-file .feature-build-self-check.md --context-file build-context.json \
  --packet-id <the packet id you admitted at Step 1> \
  --dossier-id <the dossier id> \
  --build-record build-record.json
```

**Always pass `--dossier-id` together with `--build-record`.** The server finds the build record by
the run's dossier id only; a report with just `--packet-id` is lost from the digest. A bad
`build-record.json` makes the command exit 2 with nothing sent — fix the file and run it again.

Otherwise `report-run` is best-effort — it exits `0`, spooling on failure. Never let it block
surfacing the draft-PR URL or the failure reason. Tell the user whether it reported
(`AGENT_PLATFORM_RUN_ID:` printed) or spooled (a `~/.agent-platform/spool/` warning); if
`AGENT_PLATFORM_PAT` isn't set it spools silently — mention they can set it (from the web
app's Settings screen) to see native runs in `/runs`.

**Tell the developer that nothing more comes back to this session.** The build record is a report,
not a decision: the web app shows it in the request's digest and the people there take it from there.

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

The native path records a run in `/runs` (Step 5). `agent-cli build` (a separate
subprocess CLI command that runs the same agent via its own LLM call) remains for
CI/headless use, the way `agent-cli impact` is.
