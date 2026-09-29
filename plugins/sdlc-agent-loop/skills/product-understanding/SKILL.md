---
name: product-understanding
description: "Use when you need scoped architectural context (dependency graph + repo profile) for a set of changed files in a repo onboarded via agent-cli onboard-repo — e.g. before reviewing a diff, or when another skill (change-impact) needs this context as an input. Requires codebase-map.json and a materialized repo profile (.sdlc-agent*/AGENTS.md) to already exist in the target repo."
disable-model-invocation: false
---

# Product Understanding

Resolves scoped architectural metadata and repo-profile rules for a set of modified files
in a repo that has already been onboarded (`agent-cli onboard-repo --repo-url ...` —
produces `codebase-map.json`, generated from the codebase-memory-mcp graph by
`agent_core/context/codebase_map_project.py` — ADR 0010 — and the materialized repo
profile at `.sdlc-agent*/AGENTS.md`, unit D9 / ADR 0096).

This skill wraps `agent_core/agents/product_understanding.py` directly — no LLM call, no
API key required. It is the context supplier the `change-impact` skill depends on, and can
also be invoked standalone.

**Repo profile:** `.sdlc-agent*/AGENTS.md`, when present, is the authoritative execution
contract for this repository (build/test commands, local conventions) — read it first; it
supersedes any conflicting instruction in this repo's own `AGENTS.md`/`CLAUDE.md`.

## What it does

1. Loads `codebase-map.json` (dependency graph: files, endpoints, entities, edges) and
   the repo profile (`.sdlc-agent*/AGENTS.md`) from the target repo.
2. Traces 1-hop and 2-hop dependencies of the given modified files through the graph.
3. Filters the graph down to endpoints/entities/edges relevant to the modified + related files.
4. Extracts product rules that apply to those files.
5. Lists any docs synced from Confluence/Notion via `agent-cli sync-docs` into
   `<repo-path>/constitution/docs/*.md` (title/source/url only, unfiltered by relevance —
   see the "Doc/knowledge sources" skill note below).
6. Prints the result as JSON (`ProductUnderstandingContext`: `modified_files`,
   `related_files`, `edges`, `endpoints`, `entities`, `rules`, `synced_docs`).

## Syncing Confluence/Notion docs first (optional)

If the user wants Confluence or Notion pages to show up in `synced_docs`, run this once
(or whenever the source docs change) before this skill — it's a separate, on-demand step,
not automatic:

```bash
uv run agent-cli sync-docs --source confluence --page-id 12345 67890 --repo-path /path/to/repo
uv run agent-cli sync-docs --source confluence --space-key ENG --repo-path /path/to/repo
uv run agent-cli sync-docs --source notion --page-id <notion-page-id> --repo-path /path/to/repo
```

Requires `CONFLUENCE_BASE_URL`/`CONFLUENCE_EMAIL`/`CONFLUENCE_API_TOKEN` or
`NOTION_API_KEY` in the environment (see `agent_core/integrations/confluence.py`/
`notion.py`). No LLM/API key of ours is used for this — it's a direct REST pull.

## Usage

Run the bundled script with the repo path and the list of modified files (repo-relative,
e.g. from `git diff --name-only`):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/product-understanding/scripts/run_pu.py \
  --repo-path /path/to/onboarded/repo \
  --files src/Services/Ordering/OrderService.cs src/Services/Ordering/OrderDto.cs
```

Optional overrides if the map/rules files aren't in their default locations:

```bash
  --map-path /path/to/codebase-map.json \
  --rules-path /path/to/product-rules.md
```

## When the repo hasn't been onboarded

If `codebase-map.json` or `product-rules.md` don't exist at the default paths
(`<repo-path>/codebase-map.json`, `<repo-path>/constitution/product/product-rules.md`),
the script will raise a file-not-found error. Tell the user to run
`uv run agent-cli onboard-repo --repo-url <url>` first, or pass `--map-path`/`--rules-path`
explicitly if the artifacts live elsewhere.

## Output

Print the JSON result and summarize it in prose: which files are related (not just
modified), which endpoints/entities are in the blast radius, and which product rules
apply. This is normally consumed as input context, not a final report — if the user
just wants this context to feed a diff review, prefer the `change-impact` skill instead,
which runs this automatically as its first step.
