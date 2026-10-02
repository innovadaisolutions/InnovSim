"""Bounded public models shared by the API and the local Python extension seam."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def validate_identifier(value: str) -> str:
    import re

    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", value):
        raise ValueError("Identifiers use 1-100 letters, numbers, dots, underscores or hyphens.")
    return value


def validate_json(value: Any, depth: int = 0) -> None:
    """Reject non-JSON and excessive extension data before persistence."""
    if depth > 8:
        raise ValueError("Extension data exceeds the maximum nesting depth of 8.")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > 1_000_000_000_000:
            raise ValueError("Extension numbers must be finite and bounded.")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 1_000_000_000_000:
            raise ValueError("Extension numbers must be finite and bounded.")
        return
    if isinstance(value, str):
        if len(value) > 20_000:
            raise ValueError("Extension strings are limited to 20,000 characters.")
        return
    if isinstance(value, list):
        if len(value) > 1_000:
            raise ValueError("Extension lists are limited to 1,000 items.")
        for item in value:
            validate_json(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 64 or any(not isinstance(key, str) or len(key) > 100 for key in value):
            raise ValueError("Extension objects are limited to 64 short string keys.")
        for item in value.values():
            validate_json(item, depth + 1)
        return
    raise ValueError("Extension data must be JSON serializable.")


class Agent(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=80)
    prompt: str = Field(max_length=20_000)
    skills: list[str] = Field(max_length=64)
    tools: list[str] = Field(max_length=64)
    enabled: bool = Field(strict=True)

    _id = field_validator("id")(validate_identifier)

    @field_validator("skills", "tools")
    @classmethod
    def validate_capabilities(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Skills and tools must have unique identifiers.")
        return [validate_identifier(value) for value in values]


class World(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_quantity: int = Field(strict=True, ge=1, le=1_000_000)
    available_stock: int = Field(strict=True, ge=0, le=1_000_000)
    delay_days: int = Field(strict=True, ge=0, le=365)
    expedited_cost: float = Field(strict=True, ge=0, le=1_000_000_000, allow_inf_nan=False)
    budget_limit: float = Field(strict=True, ge=0, le=1_000_000_000, allow_inf_nan=False)
    required_delivery_days: int = Field(default=2, strict=True, ge=0, le=365)
    expedited_delivery_days: int = Field(default=1, strict=True, ge=0, le=365)

    @model_validator(mode="after")
    def validate_extensions(self) -> World:
        validate_json(self.model_dump())
        return self


class Scenario(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(max_length=10_000)
    domain: str = Field(min_length=1, max_length=80)
    initial_message: str = Field(min_length=1, max_length=131_072)
    agents: list[Agent] = Field(max_length=32)
    world: World
    seed: int = Field(strict=True, ge=0, le=4_294_967_295)

    _id = field_validator("id")(validate_identifier)

    @model_validator(mode="after")
    def consistent_ids(self) -> Scenario:
        ids = [agent.id for agent in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent IDs must be unique within a scenario.")
        if set(ids) & {"system", "requester"}:
            raise ValueError("system and requester are reserved agent IDs.")
        return self


class Event(StrictModel):
    id: str
    step: int
    kind: Literal["message", "tool", "check", "system"]
    agent_id: str
    agent_name: str
    recipient: str
    content: str
    tool_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Check(StrictModel):
    id: str
    name: str
    passed: bool
    evidence: str
    event_ids: list[str]


class Suggestion(StrictModel):
    id: str
    kind: str
    title: str
    rationale: str
    agent_id: str | None = None
    patch: dict[str, Any]
    evidence_event_ids: list[str]


class Metrics(StrictModel):
    score: int
    goal_success: bool
    policy_violations: int
    tool_calls: int
    turns: int
    simulated_minutes: int
    cost: float


class Run(StrictModel):
    id: str
    scenario_id: str
    scenario_name: str
    created_at: str
    variant: Literal["baseline", "candidate"]
    parent_run_id: str | None
    seed: int
    adapter: str
    metrics: Metrics
    events: list[Event]
    checks: list[Check]
    suggestions: list[Suggestion]
    configuration: Scenario

    @model_validator(mode="after")
    def validate_evidence(self) -> Run:
        ids = {event.id for event in self.events}
        if len(ids) != len(self.events):
            raise ValueError("Run event IDs must be unique.")
        known_actors = {agent.id for agent in self.configuration.agents} | {"system", "requester"}
        if any(event.agent_id not in known_actors for event in self.events):
            raise ValueError(
                "Every event actor must identify a configured agent or a reserved system actor."
            )
        for check in self.checks:
            if not check.event_ids or not set(check.event_ids) <= ids:
                raise ValueError("Every check must link to existing run events.")
        for suggestion in self.suggestions:
            if not suggestion.evidence_event_ids or not set(suggestion.evidence_event_ids) <= ids:
                raise ValueError("Every suggestion must link to existing run events.")
        if len({item.id for item in self.checks}) != len(self.checks):
            raise ValueError("Check IDs must be unique.")
        if len({item.id for item in self.suggestions}) != len(self.suggestions):
            raise ValueError("Suggestion IDs must be unique.")
        if self.scenario_id != self.configuration.id or self.seed != self.configuration.seed:
            raise ValueError("Run metadata must match its captured scenario.")
        return self
