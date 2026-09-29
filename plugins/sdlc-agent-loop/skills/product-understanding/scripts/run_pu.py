#!/usr/bin/env python3
"""Standalone runner for ProductUnderstandingAgent — prints scoped context as JSON.

Bundled with the product-understanding skill so it can be invoked without a
full agent-cli pipeline run (which also requires an LLM API key).
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from agent_core.agents.product_understanding import ProductUnderstandingAgent  # noqa: E402
from agent_core.context.context_bus import ContextBus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Product Understanding agent standalone.")
    parser.add_argument("--repo-path", default=".", help="Path to the target repo checkout")
    parser.add_argument("--files", nargs="+", required=True, help="Modified file paths (repo-relative)")
    parser.add_argument("--map-path", help="Override path to codebase-map.json (default: <repo-path>/codebase-map.json)")
    parser.add_argument("--rules-path", help="Override path to product-rules.md")
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve()
    context = ContextBus(modified_files=args.files, metadata={"repo_root": str(repo_root)})

    agent = ProductUnderstandingAgent(
        map_path=Path(args.map_path) if args.map_path else None,
        rules_path=Path(args.rules_path) if args.rules_path else None,
    )
    agent.execute(context)

    print(context.product_understanding.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
