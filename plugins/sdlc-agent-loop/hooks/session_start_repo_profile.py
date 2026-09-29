#!/usr/bin/env python3
"""SessionStart hook — points a Claude Code session at the materialized repo profile
(unit D9, ADR 0096 §7). This is an affordance on top of the tool-neutral base path, not
a capability of its own (VD15): materialization already wrote the file to disk before
this session started, for whichever coding tool the customer runs. This hook only reads
the working tree and points the session at what is already there. It never fetches,
never decides, and never gates.

If no materialized profile is found, it exits silently (exit 0, no stdout) — a session
in a tree this runtime has never materialized into must not be interrupted (task 05
Step 2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Matches the collision-ladder family `agent_core/agents/onboarding.py::resolve_repo_profile_dir`
# resolves into: `.sdlc-agent`, `.sdlc-agent-vyomgrid`, `-2`, `-3`, ... — this hook does not
# resolve the ladder itself, it just looks for whichever one materialization already chose.
_SDLC_AGENT_DIR_PREFIX = ".sdlc-agent"


def _resolve_cwd() -> Path:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    cwd = payload.get("cwd")
    return Path(cwd).resolve() if cwd else Path.cwd()


def _find_profile(root: Path) -> Optional[Path]:
    if not root.is_dir():
        return None
    candidates = sorted(
        p for p in root.iterdir()
        if p.is_dir() and p.name.startswith(_SDLC_AGENT_DIR_PREFIX)
    )
    for candidate in candidates:
        profile = candidate / "AGENTS.md"
        if profile.is_file():
            return profile
    return None


def main() -> int:
    root = _resolve_cwd()
    profile = _find_profile(root)
    if profile is None:
        return 0

    rel = profile.relative_to(root)
    context = (
        f"This repository has a repo profile at `{rel}` — the authoritative execution "
        "contract for build/test commands and local conventions in this tree, maintained "
        "hosted and refreshed on every run. Read it before guessing a build/test command. "
        "Other AGENTS.md/CLAUDE.md files in this tree remain valid local knowledge; where "
        "one contradicts this file, this file wins."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
