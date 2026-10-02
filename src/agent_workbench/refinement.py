"""Apply small, validated configuration patches without mutating a stored run."""

from typing import Any

from .models import Agent, Scenario, validate_identifier, validate_json


def apply_refinement(scenario: Scenario, patch: dict[str, Any]) -> Scenario:
    validate_json(patch)
    if set(patch) != {"operations"}:
        raise ValueError("A refinement patch must contain only an operations list.")
    operations = patch["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
        raise ValueError("A patch must have 1-32 operations.")
    result = scenario.model_copy(deep=True)
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("op"), str):
            raise ValueError("Each refinement operation must identify its op.")
        name = operation["op"]
        if name == "add_agent":
            if set(operation) != {"op", "value"}:
                raise ValueError("add_agent accepts only a value.")
            agent = Agent.model_validate(operation["value"])
            if any(existing.id == agent.id for existing in result.agents):
                raise ValueError("An added agent's ID must be unique.")
            result.agents.append(agent)
            continue
        if name == "remove_agent":
            if set(operation) != {"op", "agent_id"}:
                raise ValueError("remove_agent accepts only agent_id.")
            found = next(
                (agent for agent in result.agents if agent.id == operation["agent_id"]), None
            )
            if found is None:
                raise ValueError("The removed agent does not exist.")
            result.agents.remove(found)
            continue
        if set(operation) != {"op", "agent_id", "value"}:
            raise ValueError("Capability operations accept only op, agent_id and value.")
        agent = next((agent for agent in result.agents if agent.id == operation["agent_id"]), None)
        if agent is None:
            raise ValueError("The patched agent does not exist.")
        value = operation["value"]
        if name in {"add_skill", "remove_skill", "add_tool", "remove_tool"}:
            if not isinstance(value, str):
                raise ValueError("Capability identifiers must be strings.")
            validate_identifier(value)
            values = agent.skills if name.endswith("skill") else agent.tools
            if name.startswith("add"):
                if value not in values:
                    values.append(value)
            elif value in values:
                values.remove(value)
        elif name == "replace_prompt":
            if not isinstance(value, str):
                raise ValueError("The replacement prompt must be text.")
            agent.prompt = value
        elif name == "set_enabled":
            if not isinstance(value, bool):
                raise ValueError("set_enabled requires a boolean.")
            agent.enabled = value
        elif name == "set_skills":
            agent.skills = value
        elif name == "set_tools":
            agent.tools = value
        else:
            raise ValueError(f"Unsupported refinement operation: {name}")
    # Validate the full result after edits, including size bounds and unique IDs.
    # Refinements cannot edit world truth, goals, budgets or the comparison seed.
    return Scenario.model_validate(result.model_dump())
