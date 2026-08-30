# sdlc-agent-loop marketplace (private)

Private, org-scoped Claude Code plugin marketplace for `sdlc-agent-loop`.
See [ADR 0052](https://github.com/Mikhil1990/AI-Assisted-Software-Development/blob/main/docs/decisions/0052-runtime-distribution-is-a-private-org-scoped-marketplace.md).

## Install (connected org)

```
claude plugin marketplace add Mikhil1990/sdlc-agent-loop-marketplace
claude plugin install sdlc-agent-loop@sdlc-agent-loop-marketplace
```

Then install the runtime package and run the preflight check — see
`claude_plugin/README.md` in the platform repo.

## Release

The plugin and the `agent-platform` package release as a locked pair (ADR 0052 §3):
one git tag `v<version>` in the platform repo fixes `plugin.json` `version`, the
`agent-platform` version the SKILL prerequisites pin, and this manifest's plugin
`source.ref` / `source.sha`.

Current release: **v0.6.0** — `plugins[0].source.ref` is pinned to tag `v0.6.0`
(sha `5624be9`), `plugins[0].version` is `0.6.0`. The `agent-platform` package the
SKILL prerequisites install is the same tag.
