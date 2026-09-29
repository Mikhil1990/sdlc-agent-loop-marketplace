#!/usr/bin/env python3
"""Standalone runner for IncidentLearningAgent — prints correlated past incidents as JSON.

Bundled with the incident-learning skill so it can be invoked without a full
agent-cli pipeline run (no LLM call, no API key needed).
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from agent_core.agents.incident_learning import IncidentLearningAgent  # noqa: E402
from agent_core.context.context_bus import ContextBus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Incident Learning agent standalone.")
    parser.add_argument("--repo-path", default=".", help="Path to the target repo checkout")
    parser.add_argument("--files", nargs="+", required=True, help="Modified file paths (repo-relative)")
    parser.add_argument(
        "--incidents-dir",
        help="Override path to the postmortems folder (default: <repo-path>/incidents)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve()
    context = ContextBus(modified_files=args.files, metadata={"repo_root": str(repo_root)})

    agent = IncidentLearningAgent(
        incidents_dir=Path(args.incidents_dir) if args.incidents_dir else None,
    )
    agent.execute(context)

    print(json.dumps([record.model_dump() for record in context.past_incidents], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
