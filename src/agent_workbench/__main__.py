"""Local developer CLI. The default demo requires no credentials or network."""

import argparse
import json
from pathlib import Path

from .models import Run, Scenario
from .storage import Repository


def _summary(run: Run) -> dict:
    return {
        "run_id": run.id,
        "variant": run.variant,
        "parent_run_id": run.parent_run_id,
        "adapter": run.adapter,
        "seed": run.seed,
        **run.metrics.model_dump(),
        "suggestions": [{"id": item.id, "title": item.title} for item in run.suggestions],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="innovsim", description="InnovSim offline workflow simulation workbench"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve the local API and built browser interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    for command in ["demo", "run"]:
        current = commands.add_parser(command, help="Run and persist an offline workflow")
        current.add_argument("--database", default=None)
        current.add_argument(
            "--refine",
            action="store_true",
            help="Apply observed suggestions iteratively, up to eight candidates",
        )
        current.add_argument(
            "--export", type=Path, default=None, help="Write the final complete run as JSON"
        )
        if command == "run":
            current.add_argument("--scenario", type=Path, required=True, help="Scenario JSON file")
    export = commands.add_parser("export", help="Export an immutable persisted run as JSON")
    export.add_argument("run_id")
    export.add_argument("--database", default=None)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        import uvicorn

        uvicorn.run("agent_workbench.api:create_app", factory=True, host=args.host, port=args.port)
        return
    repository = Repository(args.database)
    try:
        if args.command == "export":
            run = repository.get_run(args.run_id)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"Exported run {run.id} to {args.output.resolve()}")
            return
        scenario_id = "supplier-delay"
        if args.command == "run":
            scenario = Scenario.model_validate_json(args.scenario.read_text(encoding="utf-8"))
            repository.save_scenario(scenario)
            scenario_id = scenario.id
        run = repository.run_scenario(scenario_id)
        print(json.dumps(_summary(run), indent=2))
        if args.refine:
            for _ in range(8):
                if run.metrics.goal_success or not run.suggestions:
                    break
                run = repository.refine_run(run.id, run.suggestions[0].id)
                print(json.dumps(_summary(run), indent=2))
        if args.export:
            args.export.parent.mkdir(parents=True, exist_ok=True)
            args.export.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"Final run exported to {args.export.resolve()}")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
