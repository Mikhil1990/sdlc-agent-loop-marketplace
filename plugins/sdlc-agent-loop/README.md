# sdlc-agent-loop (Claude Code plugin)

Claude Code plugin distribution for the AI-Assisted-Software-Development closed loop.
See [../docs/status/current-implementation.md § Direction: Claude Code ecosystem wedge](../docs/status/current-implementation.md#direction-claude-code-ecosystem-wedge-current-priority)
for the full plan.

## Status

All six skills are implemented:

| Skill | Wraps | Invocation | Status |
|-------|-------|-----------|--------|
| `product-understanding` | `agent_core/agents/product_understanding.py` | native (standalone script, no LLM) | ✅ implemented |
| `incident-learning` | `agent_core/agents/incident_learning.py` | native (standalone script, no LLM) | ✅ implemented |
| `change-impact` | `agent_core/agents/product_understanding.py` + `incident_learning.py` + `change_impact.py` | **native** — `agent-cli context` gathers data, this session writes the report | ✅ implemented |
| `code-correction` | the above + `agent_core/agents/code_correction.py` | **native** — `agent-cli context`/`apply-patch` do the deterministic parts, this session writes the patch | ✅ implemented |
| `feature-build` | `agent_core/agents/feature_build.py` + reuses `change_impact.py`'s rules for self-check | **native** — `agent-cli ready-work`, then `admit-packet --approval-id` (fails closed on a missing/unsigned `feature_spec` packet) writes a local work file; Mode A tests the Design's evidence claims against the code and routes questions with `agent-cli ask`; Mode B (`plan-context`/`apply-patch`) writes the patch + self-check; `report-run --build-record` sends one build record back | ✅ implemented |

`feature-build` was pulled forward from the platform's Phase 2 into
the wedge (2026-08-16 decision, see `docs/status/current-implementation.md` § "six-agent closed
loop") and built natively from the start, following the same pattern `change-impact`/
`code-correction` were rewritten into. `feature-build` never merges or marks a PR ready
for review — it opens a **draft** PR (`gh pr create --draft`) after a passing self-check
and sandbox test run, same "propose, don't auto-land" posture as `code-correction`.
`agent-cli plan`/`agent-cli build` (subprocess, LLM-calling CLI commands) also exist in
`agent_core/cli/` for CI/headless use, the same role `agent-cli impact` plays
for `change-impact` (`agent-cli correct` was retired by ADR 0180; `code-correction` has only the skill path).

`change-impact` and `code-correction` were rewritten (2026-08-12) from an earlier version
that shelled out to `agent-cli impact`/`agent-cli correct` (the latter since retired, ADR 0180) as a subprocess — that spawned
a *second*, separate `claude` CLI process for the LLM reasoning step, with no access to
this conversation's context. They now use `agent-cli context` (diff + Product
Understanding + Incident Learning, deterministic, no LLM call) and `agent-cli apply-patch`
(apply/test/push/PR, deterministic, no LLM call) as thin git/filesystem helpers, while the
actual reasoning (the impact report, the patch) is done by the calling Claude Code session
itself — see each skill's `SKILL.md` for the exact instructions it follows.

`agent-cli impact` (the original subprocess-based command; `agent-cli correct` was retired by
ADR 0180) still exists in `agent_core/cli/` and remains the path used by CI/Model A/Model B (non-interactive
contexts with no Claude Code session to reason natively) and by the Agent Monitoring run
history/approval inbox, which the native skill path does not yet report into — see the
"Known gap" note in each skill's `SKILL.md`.

## Prerequisites

The plugin is distributed through a **public marketplace repo** whose tag also carries the
matching CLI wheel
([ADR 0228](../docs/decisions/0228-distribution-is-a-public-marketplace-repo-plus-a-release-attached-wheel.md)) —
you do **not** need a checkout of this monorepo. A working install needs:

1. **Python ≥ 3.10 with [`uv`](https://docs.astral.sh/uv/)** on `PATH`.
2. **`codebase-memory-mcp`**, the codebase-graph engine `agent-cli onboard-repo` and the native
   context commands read. Nothing to install separately: `agent-cli` bundles a pinned copy
   ([ADR 0215](../docs/decisions/0215-agent-cli-reuses-whatever-cbm-an-org-already-has-and-bundles-its-own-as-the-fallback.md))
   and reuses your org's own copy on `PATH` instead when one is already there. `agent-cli doctor`
   reports which copy it picked and why.
3. **A hosted-platform account.** Native skill runs report to the hosted backend
   ([ADR 0044](../docs/decisions/0044-native-skill-runs-report-through-an-authenticated-ingest-endpoint.md)),
   so set:
   - `AGENT_PLATFORM_API_URL` — defaults to `https://app.vyomgrid.com`; only set this to
     point at a self-hosted deployment instead
   - `AGENT_PLATFORM_PAT` — a personal access token minted from the hosted app's Settings
     (this one genuinely can't be defaulted — it's per-user and proves who you are)

   A transient outage mid-run is tolerated (the run spools to
   `~/.agent-platform/spool/runs.jsonl`); there is no offline / anonymous mode
   ([ADR 0032](../docs/decisions/0032-all-surfaces-authenticate-through-the-hosted-app.md)).
4. **The `vyomgrid-agent-platform` package** (provides `agent-cli`), installed from the wheel attached to
   this plugin's own release — **not** from PyPI, **not** an editable checkout. `uv tool`
   puts it in its own isolated environment and on your `PATH`:
   ```bash
   uv tool install "vyomgrid-agent-platform @ https://github.com/Mikhil1990/sdlc-agent-loop-marketplace/releases/download/v0.7.2/vyomgrid_agent_platform-0.7.2-py3-none-any.whl"
   agent-cli --version   # agent-cli 0.7.2
   ```
   The plugin and this package release as a **locked pair** — one tag fixes both versions
   (ADR 0052 §3, [ADR 0228](../docs/decisions/0228-distribution-is-a-public-marketplace-repo-plus-a-release-attached-wheel.md)).
   To upgrade, install the new release's wheel the same way (`uv tool install --force`).

   To take the newest release without naming a version (not for a plugin you pinned — the plugin
   and the package must match):
   ```bash
   uv tool install --upgrade vyomgrid-agent-platform --find-links https://github.com/Mikhil1990/sdlc-agent-loop-marketplace/releases/expanded_assets/latest
   ```
   **Installed it before 0.7.2 under the old name `agent-platform`?** Run
   `uv tool uninstall agent-platform` first, then one of the lines above. Both names provide
   `agent-cli`, so the new install stops on the old one.
5. **The plugin**, from the public marketplace:
   ```bash
   claude plugin marketplace add Mikhil1990/sdlc-agent-loop-marketplace
   claude plugin install sdlc-agent-loop@sdlc-agent-loop-marketplace
   ```
6. **The target repo connected to the hosted app** — sign in at `https://app.vyomgrid.com`,
   then **Product → Repositories → Connect**; VyomGrid's servers clone and index it, nothing
   runs locally. (The CLI alternative is `agent-cli onboard-repo --repo-url <url>`, which
   produces `codebase-map.json` and `constitution/product/product-rules.md` — required by
   all six skills.)

Run **`agent-cli doctor --repo-path <target repo>`** to check items 2, 3 and 6 before
invoking a skill — it prints each missing item and exits non-zero.

- No LLM API key is needed for any skill: `product-understanding`/`incident-learning`
  never call an LLM, and `change-impact`/`code-correction`/`feature-build`
  reason natively in the calling session rather than calling one out-of-band.
- `code-correction`/`feature-build` additionally need `gh` authenticated for the target
  repo (to open the PR) and a working test command for that repo.

## Local dev/test loop

1. Fastest iteration — point Claude Code at this directory directly:
   ```bash
   claude --plugin-dir /path/to/AI-Assisted-Software-Development/claude_plugin
   ```
   Invoke skills as `/sdlc-agent-loop:product-understanding`,
   `/sdlc-agent-loop:incident-learning`, `/sdlc-agent-loop:change-impact`,
   `/sdlc-agent-loop:code-correction`, or
   `/sdlc-agent-loop:feature-build`.
2. Test real install behavior:
   ```
   /plugin marketplace add /path/to/AI-Assisted-Software-Development/claude_plugin
   /plugin install sdlc-agent-loop
   ```
   Use `/reload-plugins` after live edits to `SKILL.md` files.
3. Before publishing, validate the manifest and file layout:
   ```bash
   claude plugin validate --strict /path/to/AI-Assisted-Software-Development/claude_plugin
   ```

## Structure

```
claude_plugin/
├── .claude-plugin/
│   └── plugin.json                    # marketplace metadata only
├── skills/
│   ├── product-understanding/
│   │   ├── SKILL.md
│   │   └── scripts/run_pu.py          # standalone runner, no LLM call
│   ├── incident-learning/
│   │   ├── SKILL.md
│   │   └── scripts/run_incident_learning.py  # standalone runner, no LLM call
│   ├── change-impact/
│   │   └── SKILL.md                   # uses `agent-cli context`; reasons natively
│   ├── code-correction/
│   │   └── SKILL.md                   # uses `agent-cli context`/`apply-patch`; reasons natively
│   └── feature-build/
│       └── SKILL.md                   # `ready-work`, `admit-packet --approval-id`, Mode A then Mode B, `apply-patch --draft`, `report-run --build-record`
└── README.md
```
