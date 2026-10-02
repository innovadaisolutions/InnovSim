"""A real Python extension that changes a workflow handoff without changing prompts.

Run: python examples/custom_adapter.py
This example uses only mock engine tools. An adapter is trusted executable local
code: never load one from a web request or an untrusted email attachment.
"""

from agent_workbench import DeterministicAdapter, SimulationContext, simulate
from agent_workbench.fixtures import supplier_delay
from agent_workbench.models import Agent
from agent_workbench.refinement import apply_refinement
from agent_workbench.simulation import IncomingMessage


class ApprovalRouterAdapter(DeterministicAdapter):
    """Implement the missing approval handoff in Python, using real context APIs."""

    name = "python-approval-router"

    def step(self, agent: Agent, message: IncomingMessage, context: SimulationContext) -> None:
        if agent.role == "logistics" and message.kind == "expedite_request":
            if not context.require(agent, "quote_expedite", "quote_expedite"):
                return
            quote = context.call_tool(agent, "quote_expedite")
            if quote["success"]:
                context.record(
                    "system",
                    agent,
                    agent.id,
                    "Custom Python adapter routed the quote to the supervisor.",
                    data={"extension": self.name},
                )
                context.send(
                    agent,
                    "supervisor",
                    "approval_request",
                    "Custom adapter requests authorization for the recorded freight quote.",
                    {"quote_id": quote["quote_id"]},
                )
            return
        super().step(agent, message, context)


def demonstration():
    adapter = ApprovalRouterAdapter()
    baseline = simulate(supplier_delay(), adapter=adapter)
    patch = baseline.suggestions[0].patch
    candidate = simulate(
        apply_refinement(baseline.configuration, patch), adapter=adapter, parent_run_id=baseline.id
    )
    return baseline, candidate


if __name__ == "__main__":
    import json

    for run in demonstration():
        print(
            json.dumps(
                {
                    "run_id": run.id,
                    "adapter": run.adapter,
                    "variant": run.variant,
                    "parent_run_id": run.parent_run_id,
                    "metrics": run.metrics.model_dump(),
                },
                indent=2,
            )
        )
