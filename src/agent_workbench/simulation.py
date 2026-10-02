"""Offline agents, a message queue, guarded mock tools and evidence-based evaluation.

Prompt text is captured for review. This adapter executes named Python skills; it
does not interpret prompts with a language model. External agents can implement
AgentAdapter in trusted local code without changing the engine or the API.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Protocol
from uuid import uuid4

from .fixtures import default_agents
from .models import Agent, Check, Event, Metrics, Run, Scenario, Suggestion, validate_json


@dataclass(frozen=True)
class IncomingMessage:
    sender_id: str
    recipient_id: str
    kind: str
    content: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldState:
    """Mutable simulated facts, separate from the captured scenario configuration."""

    remaining_stock: int
    inventory_checked: bool = False
    quote: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    shipment: dict[str, Any] | None = None
    fulfilled_quantity: int = 0
    delivery_days: int | None = None
    spent: float = 0.0
    buyer_confirmed: bool = False
    policy_violations: list[str] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)
    approval_required_for_spend: bool = False
    approved_before_spend: bool = True
    aborted: bool = False


class AgentAdapter(Protocol):
    """Trusted Python extension point; web requests cannot upload or import code."""

    name: str

    def step(self, agent: Agent, message: IncomingMessage, context: SimulationContext) -> None:
        """Handle one message using context.send(), call_tool() and require()."""
        ...


class SimulationContext:
    """Agent-visible queue and mock tool facade, with a complete event trail."""

    TOOL_ROLES: ClassVar[dict[str, set[str]]] = {
        "inventory_check": {"supplier", "buyer"},
        "ship_standard": {"supplier"},
        "quote_expedite": {"logistics"},
        "approve_spend": {"supervisor"},
        "book_expedite": {"logistics"},
    }

    def __init__(self, scenario: Scenario) -> None:
        self._configuration = scenario.model_copy(deep=True)
        self.state = WorldState(remaining_stock=scenario.world.available_stock)
        self.events: list[Event] = []
        self.queue: deque[IncomingMessage] = deque()
        self.blockers: list[dict[str, Any]] = []
        self.turns = 0
        self._random = random.Random(scenario.seed)
        self._allow_final_events = False
        self.needed_roles = ["buyer", "supplier"]
        if scenario.world.delay_days > scenario.world.required_delivery_days:
            self.needed_roles += ["logistics", "supervisor"]

    @property
    def configuration(self) -> Scenario:
        """Return a copy so an adapter cannot edit the recorded input by accident."""
        return self._configuration.model_copy(deep=True)

    def agent_by_id(self, reference: str) -> Agent | None:
        found = next(
            (
                agent
                for agent in self._configuration.agents
                if agent.enabled and agent.id == reference
            ),
            None,
        )
        return found.model_copy(deep=True) if found else None

    def agent_for_role(self, role: str) -> Agent | None:
        found = next(
            (agent for agent in self._configuration.agents if agent.enabled and agent.role == role),
            None,
        )
        return found.model_copy(deep=True) if found else None

    def record(
        self,
        kind: str,
        actor: Agent | str,
        recipient: str,
        content: str,
        *,
        tool_name: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Event:
        if len(self.events) >= (512 if self._allow_final_events else 480):
            raise RuntimeError("The simulation event limit was reached.")
        validate_json(data or {})
        if isinstance(actor, Agent):
            actor_id, actor_name = actor.id, actor.name
        else:
            actor_id = actor
            actor_name = "Scenario input" if actor == "requester" else "Simulation engine"
        event = Event(
            id=f"event-{len(self.events) + 1:03d}",
            step=len(self.events) + 1,
            kind=kind,
            agent_id=actor_id,
            agent_name=actor_name,
            recipient=recipient,
            content=content,
            tool_name=tool_name,
            data=data or {},
        )
        self.events.append(event)
        return event

    def remember(self, key: str, event_id: str) -> None:
        self.state.evidence.setdefault(key, []).append(event_id)

    def send(
        self,
        actor: Agent,
        recipient: str,
        kind: str,
        content: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Send to an enabled participant by role, independently of its agent ID."""
        return self._send(actor, recipient, kind, content, data, by_role=True)

    def send_to_id(
        self,
        actor: Agent,
        recipient_id: str,
        kind: str,
        content: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Address a specific configured agent when multiple agents share a role."""
        return self._send(actor, recipient_id, kind, content, data, by_role=False)

    def _send(
        self,
        actor: Agent,
        recipient: str,
        kind: str,
        content: str,
        data: dict[str, Any] | None,
        *,
        by_role: bool,
    ) -> str:
        target = self.agent_for_role(recipient) if by_role else self.agent_by_id(recipient)
        event = self.record(
            "message",
            actor,
            target.id if target else recipient,
            content,
            data={"message_type": kind, **(data or {})},
        )
        if target:
            self.queue.append(IncomingMessage(actor.id, target.id, kind, content, data or {}))
        else:
            self._missing_agent(recipient, event.id, by_role=by_role)
        return event.id

    def _missing_agent(
        self, reference: str, evidence_id: str | None = None, *, by_role: bool = True
    ) -> None:
        existing = next(
            (
                agent
                for agent in self._configuration.agents
                if (agent.role == reference if by_role else agent.id == reference)
            ),
            None,
        )
        role = existing.role if existing else reference
        if evidence_id is None:
            event = self.record(
                "system",
                "system",
                reference,
                f"No enabled {role} agent can receive this workflow's messages.",
                data={"blocker": "missing_agent", "role": role},
            )
            evidence_id = event.id
        if existing:
            operations = [{"op": "set_enabled", "agent_id": existing.id, "value": True}]
            title = f"Enable the {role} agent"
            agent_id = existing.id
        else:
            template = next((agent for agent in default_agents() if agent.role == role), None)
            if template is None:
                return
            used = {agent.id for agent in self._configuration.agents}
            if template.id in used:
                base = f"{template.id}-restored"
                template.id = base
                suffix = 2
                while template.id in used:
                    template.id = f"{base}-{suffix}"
                    suffix += 1
            operations = [{"op": "add_agent", "value": template.model_dump()}]
            title = f"Add a {role} agent"
            agent_id = template.id
        self.blockers.append(
            {
                "key": f"agent:{role}",
                "kind": "agent",
                "agent_id": agent_id,
                "title": title,
                "rationale": f"The observed handoff has no enabled {role} recipient. Restore that participant before retrying.",
                "operations": operations,
                "evidence": [evidence_id],
            }
        )

    def require(self, agent: Agent, skill: str, tool: str | None = None) -> bool:
        operations = []
        missing = []
        if skill not in agent.skills:
            missing.append(f"skill {skill}")
            operations.append({"op": "add_skill", "agent_id": agent.id, "value": skill})
        if tool and tool not in agent.tools:
            missing.append(f"tool {tool}")
            operations.append({"op": "add_tool", "agent_id": agent.id, "value": tool})
        if not missing:
            return True
        event = self.record(
            "system",
            agent,
            agent.id,
            f"Workflow paused: {agent.name} lacks {' and '.join(missing)}.",
            data={"blocker": "missing_capability", "skill": skill, "tool": tool},
        )
        self.blockers.append(
            {
                "key": f"capability:{agent.id}:{skill}:{tool or ''}",
                "kind": "tool" if tool and tool not in agent.tools else "skill",
                "agent_id": agent.id,
                "title": f"Add {' and '.join(missing)} to {agent.name}",
                "rationale": "An observed workflow step cannot execute with the current skills and tool allowlist. "
                "Add only the missing capability and rerun the same fixture.",
                "operations": operations,
                "evidence": [event.id],
            }
        )
        return False

    def call_tool(self, agent: Agent, name: str, **arguments: Any) -> dict[str, Any]:
        """Invoke a known, simulated capability. Never dispatch a name to external code."""
        validate_json(arguments)
        registered = self.agent_by_id(agent.id)
        if not registered or registered.role != agent.role:
            return self._tool_result(
                agent,
                name,
                arguments,
                False,
                "Agent is absent, disabled or has an invalid role.",
                policy=True,
            )
        if name not in self.TOOL_ROLES:
            return self._tool_result(
                agent, name, arguments, False, "No mock implementation is registered for this tool."
            )
        if registered.role not in self.TOOL_ROLES[name]:
            return self._tool_result(
                agent,
                name,
                arguments,
                False,
                "This agent's role is not authorized for this tool.",
                policy=True,
            )
        if name not in registered.tools:
            result = self._tool_result(
                agent, name, arguments, False, "Tool is absent from this agent's allowlist."
            )
            self.blockers.append(
                {
                    "key": f"tool:{agent.id}:{name}",
                    "kind": "tool",
                    "agent_id": agent.id,
                    "title": f"Allow {name} for {agent.name}",
                    "rationale": "The recorded call was blocked because its capability was absent from the agent's tool allowlist.",
                    "operations": [{"op": "add_tool", "agent_id": agent.id, "value": name}],
                    "evidence": [self.events[-1].id],
                }
            )
            return result
        world = self._configuration.world
        if name == "inventory_check":
            if arguments:
                return self._tool_result(
                    agent, name, arguments, False, "This tool accepts no arguments."
                )
            self.state.inventory_checked = True
            result = self._tool_result(
                agent,
                name,
                arguments,
                True,
                "Supplier inventory checked.",
                output={
                    "available_stock": self.state.remaining_stock,
                    "order_quantity": world.order_quantity,
                    "shortage": max(0, world.order_quantity - self.state.remaining_stock),
                    "standard_delivery_days": world.delay_days,
                },
            )
            self.remember("inventory", self.events[-1].id)
            return result
        if name == "quote_expedite":
            if arguments or not self.state.inventory_checked:
                return self._tool_result(
                    agent,
                    name,
                    arguments,
                    False,
                    "A checked inventory is required; no arguments are accepted.",
                )
            eligible = self.state.remaining_stock >= world.order_quantity
            quote = {
                "quote_id": f"freight-{self._random.randrange(1000, 10000)}",
                "quantity": world.order_quantity,
                "cost": world.expedited_cost,
                "delivery_days": world.expedited_delivery_days,
                "eligible": eligible,
            }
            self.state.quote = quote
            result = self._tool_result(
                agent,
                name,
                arguments,
                True,
                "Expedited freight quoted from fixture inputs.",
                output=quote,
            )
            self.remember("quote", self.events[-1].id)
            return result
        if name == "approve_spend":
            quote = self.state.quote
            if not quote or arguments != {"quote_id": quote["quote_id"]}:
                return self._tool_result(
                    agent, name, arguments, False, "Approval must reference the recorded quote."
                )
            approved = quote["eligible"] and quote["cost"] <= world.budget_limit
            if approved:
                self.state.approval = {
                    "quote_id": quote["quote_id"],
                    "amount": quote["cost"],
                    "agent_id": agent.id,
                }
            result = self._tool_result(
                agent,
                name,
                arguments,
                True,
                "Quoted expenditure approved."
                if approved
                else "Approval declined: budget or inventory constraint.",
                output={
                    "approved": approved,
                    "quote_id": quote["quote_id"],
                    "amount": quote["cost"],
                    "budget_limit": world.budget_limit,
                },
            )
            self.remember("approval", self.events[-1].id)
            return result
        if name in {"ship_standard", "book_expedite"}:
            if self.state.shipment:
                return self._tool_result(
                    agent,
                    name,
                    arguments,
                    False,
                    "This order already has a shipment; duplicate booking is blocked.",
                    policy=True,
                )
            if not self.state.inventory_checked:
                return self._tool_result(
                    agent, name, arguments, False, "Inventory must be checked before shipment."
                )
            if self.state.remaining_stock < world.order_quantity:
                return self._tool_result(
                    agent,
                    name,
                    arguments,
                    False,
                    "Insufficient stock; mock freight cannot create missing inventory.",
                )
            cost, eta = 0.0, world.delay_days
            approval_required = name == "book_expedite"
            if approval_required:
                quote, approval = self.state.quote, self.state.approval
                if not quote or arguments != {"quote_id": quote["quote_id"]}:
                    return self._tool_result(
                        agent,
                        name,
                        arguments,
                        False,
                        "Booking must reference the recorded quote.",
                        policy=True,
                    )
                if (
                    not approval
                    or approval["quote_id"] != quote["quote_id"]
                    or approval["amount"] != quote["cost"]
                ):
                    return self._tool_result(
                        agent,
                        name,
                        arguments,
                        False,
                        "Explicit matching approval is required before booking.",
                        policy=True,
                    )
                cost, eta = quote["cost"], quote["delivery_days"]
                if self.state.spent + cost > world.budget_limit:
                    return self._tool_result(
                        agent,
                        name,
                        arguments,
                        False,
                        "Booking would exceed the approved budget.",
                        policy=True,
                    )
            elif arguments:
                return self._tool_result(
                    agent, name, arguments, False, "Standard shipment accepts no arguments."
                )
            self.state.remaining_stock -= world.order_quantity
            self.state.fulfilled_quantity = world.order_quantity
            self.state.delivery_days = eta
            self.state.spent += cost
            self.state.approval_required_for_spend = approval_required
            self.state.approved_before_spend = (
                not approval_required or self.state.approval is not None
            )
            self.state.shipment = {
                "quantity": world.order_quantity,
                "delivery_days": eta,
                "cost": cost,
                "mode": "expedited" if approval_required else "standard",
            }
            result = self._tool_result(
                agent,
                name,
                arguments,
                True,
                "Simulated shipment delivered; inventory and expenditure updated.",
                output=self.state.shipment,
            )
            self.remember("shipment", self.events[-1].id)
            return result
        raise AssertionError("Every registered mock tool must have an implementation.")

    def _tool_result(
        self,
        agent: Agent,
        name: str,
        arguments: dict[str, Any],
        success: bool,
        message: str,
        *,
        output: dict[str, Any] | None = None,
        policy: bool = False,
    ) -> dict[str, Any]:
        result = {"success": success, "message": message, **(output or {})}
        known = next(
            (configured for configured in self._configuration.agents if configured.id == agent.id),
            None,
        )
        event = self.record(
            "tool",
            known or "system",
            "mock-world",
            message,
            tool_name=name,
            data={
                "arguments": arguments,
                "result": result,
                "simulated": True,
                "policy_violation": policy,
                "attempted_agent_id": agent.id,
            },
        )
        if policy:
            self.state.policy_violations.append(event.id)
        return result

    def confirm_delivery(self, agent: Agent) -> None:
        world = self._configuration.world
        registered = self.agent_by_id(agent.id)
        if (
            registered is None
            or registered.role != "buyer"
            or agent.role != registered.role
            or not self.state.shipment
        ):
            known = next(
                (
                    configured
                    for configured in self._configuration.agents
                    if configured.id == agent.id
                ),
                None,
            )
            event = self.record(
                "system",
                known or "system",
                "system",
                "Delivery confirmation rejected: an enabled registered buyer and shipment are required.",
                data={"attempted_agent_id": agent.id, "policy_violation": True},
            )
            self.state.policy_violations.append(event.id)
            return
        self.state.buyer_confirmed = (
            self.state.fulfilled_quantity == world.order_quantity
            and self.state.delivery_days is not None
            and self.state.delivery_days <= world.required_delivery_days
        )
        event = self.record(
            "message",
            agent,
            "requester",
            "Complete on-time delivery confirmed."
            if self.state.buyer_confirmed
            else "Delivery received, but quantity or deadline does not meet the order.",
            data={"message_type": "delivery_confirmation", "accepted": self.state.buyer_confirmed},
        )
        self.remember("confirmation", event.id)


class DeterministicAdapter:
    name = "deterministic"

    def step(self, agent: Agent, message: IncomingMessage, context: SimulationContext) -> None:
        world = context.configuration.world
        if agent.role == "buyer":
            if message.kind == "initial_request" and context.require(agent, "place_order"):
                context.send(
                    agent,
                    "supplier",
                    "order_request",
                    f"Please check availability and delivery of {world.order_quantity} components. "
                    f"The deadline is day {world.required_delivery_days}.",
                )
            elif message.kind == "supplier_update":
                if message.data["shortage"]:
                    context.record(
                        "message",
                        agent,
                        "requester",
                        f"Order cannot be fulfilled: {message.data['shortage']} components are unavailable. "
                        "Changing prompts cannot create stock.",
                        data={"message_type": "capacity_constraint"},
                    )
                elif message.data["standard_delivery_days"] <= world.required_delivery_days:
                    context.send(
                        agent,
                        "supplier",
                        "standard_dispatch",
                        "Standard delivery meets the deadline; please ship the order.",
                    )
                elif context.require(agent, "escalate_delay"):
                    context.send(
                        agent,
                        "logistics",
                        "expedite_request",
                        "Standard shipping misses the deadline. Please quote expedited freight and obtain approval.",
                    )
            elif message.kind == "delivery_notice" and context.require(agent, "accept_delivery"):
                context.confirm_delivery(agent)
            elif message.kind == "approval_declined":
                context.record(
                    "message",
                    agent,
                    "requester",
                    "No shipment booked: the supervisor declined the quoted expenditure.",
                    data={"message_type": "unresolved_budget"},
                )
            return
        if agent.role == "supplier":
            if message.kind == "order_request":
                if not context.require(agent, "check_inventory", "inventory_check"):
                    return
                inventory = context.call_tool(agent, "inventory_check")
                if inventory["success"] and context.require(agent, "report_delay"):
                    context.send(
                        agent,
                        "buyer",
                        "supplier_update",
                        f"Stock is {inventory['available_stock']}; standard delivery takes {inventory['standard_delivery_days']} days.",
                        {
                            "shortage": inventory["shortage"],
                            "standard_delivery_days": inventory["standard_delivery_days"],
                        },
                    )
            elif message.kind == "standard_dispatch" and context.require(
                agent, "standard_delivery", "ship_standard"
            ):
                shipment = context.call_tool(agent, "ship_standard")
                if shipment["success"]:
                    context.send(
                        agent,
                        "buyer",
                        "delivery_notice",
                        "The complete order arrived through standard freight.",
                    )
            return
        if agent.role == "logistics":
            if message.kind == "expedite_request":
                if not context.require(agent, "quote_expedite", "quote_expedite"):
                    return
                quote = context.call_tool(agent, "quote_expedite")
                if not quote["success"]:
                    return
                if not context.require(agent, "request_approval"):
                    return
                context.send(
                    agent,
                    "supervisor",
                    "approval_request",
                    f"Approve quoted freight expenditure of {quote['cost']:.2f} for delivery on day {quote['delivery_days']}.",
                    {"quote_id": quote["quote_id"]},
                )
            elif message.kind == "approval_granted":
                if not context.require(agent, "book_expedite", "book_expedite"):
                    return
                shipment = context.call_tool(
                    agent, "book_expedite", quote_id=message.data["quote_id"]
                )
                if shipment["success"]:
                    context.send(
                        agent,
                        "buyer",
                        "delivery_notice",
                        "Approved expedited freight delivered the complete order.",
                    )
            return
        if agent.role == "supervisor" and message.kind == "approval_request":
            if not context.require(agent, "budget_review", "approve_spend"):
                return
            approval = context.call_tool(agent, "approve_spend", quote_id=message.data["quote_id"])
            if approval["success"] and approval["approved"]:
                context.send(
                    agent,
                    "logistics",
                    "approval_granted",
                    "The quoted expenditure is authorized within the budget.",
                    {"quote_id": approval["quote_id"]},
                )
            else:
                context.send(
                    agent,
                    "buyer",
                    "approval_declined",
                    "The quote exceeds the budget or available inventory.",
                )


def _evaluate(context: SimulationContext) -> list[Check]:
    state, world = context.state, context.configuration.world
    fallback = [context.events[0].id]

    def evidence(*keys: str) -> list[str]:
        return (
            list(
                dict.fromkeys(event_id for key in keys for event_id in state.evidence.get(key, []))
            )
            or fallback
        )

    missing = [role for role in context.needed_roles if context.agent_for_role(role) is None]
    checks = [
        Check(
            id="order_fulfilled",
            name="Complete order delivered",
            passed=state.fulfilled_quantity == world.order_quantity,
            evidence=f"Delivered {state.fulfilled_quantity} of {world.order_quantity} components. Remaining stock: {state.remaining_stock}.",
            event_ids=evidence("inventory", "shipment"),
        ),
        Check(
            id="delivery_deadline",
            name="Delivery meets the deadline",
            passed=state.delivery_days is not None
            and state.delivery_days <= world.required_delivery_days,
            evidence=(
                f"Delivery on day {state.delivery_days}; required by day {world.required_delivery_days}."
                if state.delivery_days is not None
                else f"No delivery recorded; required by day {world.required_delivery_days}."
            ),
            event_ids=evidence("shipment", "quote"),
        ),
        Check(
            id="buyer_confirmation",
            name="Buyer confirms the business outcome",
            passed=state.buyer_confirmed,
            evidence="Buyer accepted the fulfilled order."
            if state.buyer_confirmed
            else "No complete on-time order was accepted by the buyer.",
            event_ids=evidence("confirmation", "shipment"),
        ),
        Check(
            id="budget_respected",
            name="Expenditure stays within budget",
            passed=state.spent <= world.budget_limit,
            evidence=f"Simulated expenditure {state.spent:.2f}; budget {world.budget_limit:.2f}.",
            event_ids=evidence("shipment", "approval", "quote"),
        ),
        Check(
            id="approval_before_spend",
            name="Approval precedes expedited booking",
            passed=state.approved_before_spend,
            evidence=(
                "Expedited shipment references the matching supervisor approval."
                if state.approval_required_for_spend
                else "No expedited expenditure was made; this policy has not been exercised."
            ),
            event_ids=evidence("approval", "shipment"),
        ),
        Check(
            id="tool_permissions",
            name="Tool and authorization policies respected",
            passed=not state.policy_violations,
            evidence=f"{len(state.policy_violations)} blocked policy-violating attempts.",
            event_ids=state.policy_violations or evidence("inventory", "approval"),
        ),
        Check(
            id="required_agents_present",
            name="Required participants are enabled",
            passed=not missing,
            evidence="Required workflow participants are enabled."
            if not missing
            else f"Missing enabled participants: {', '.join(missing)}.",
            event_ids=[
                event.id for event in context.events if event.data.get("blocker") == "missing_agent"
            ]
            or fallback,
        ),
        Check(
            id="bounded_execution",
            name="Simulation completed within execution bounds",
            passed=not state.aborted,
            evidence="The message queue completed within 60 turns."
            if not state.aborted
            else "The adapter failed or the bounded execution limit was reached.",
            event_ids=[
                event.id
                for event in context.events
                if event.data.get("adapter_error") or event.data.get("execution_limit")
            ]
            or fallback,
        ),
    ]
    for check in checks:
        context.record(
            "check",
            "system",
            "evaluator",
            f"{'PASS' if check.passed else 'FAIL'}: {check.name}. {check.evidence}",
            data={
                "check_id": check.id,
                "passed": check.passed,
                "evidence_event_ids": check.event_ids,
            },
        )
    return checks


def _suggest(context: SimulationContext) -> list[Suggestion]:
    grouped: dict[str, dict[str, Any]] = {}
    for blocker in context.blockers:
        if blocker["key"] in grouped:
            grouped[blocker["key"]]["evidence"].extend(blocker["evidence"])
        else:
            grouped[blocker["key"]] = {**blocker, "evidence": list(blocker["evidence"])}
    return [
        Suggestion(
            id=f"suggestion-{index:03d}",
            kind=blocker["kind"],
            title=blocker["title"],
            rationale=blocker["rationale"],
            agent_id=blocker["agent_id"],
            patch={"operations": blocker["operations"]},
            evidence_event_ids=list(dict.fromkeys(blocker["evidence"])),
        )
        for index, blocker in enumerate(grouped.values(), start=1)
    ]


def simulate(
    scenario: Scenario,
    *,
    adapter: AgentAdapter | None = None,
    parent_run_id: str | None = None,
) -> Run:
    """Run a fresh world using a captured scenario, with no network or model calls."""
    snapshot = Scenario.model_validate(scenario.model_dump())
    context = SimulationContext(snapshot)
    selected_adapter = adapter or DeterministicAdapter()
    adapter_notice = (
        "Offline simulation: named Python skills drive agent behavior; prompts are recorded, not interpreted. "
        if isinstance(selected_adapter, DeterministicAdapter)
        and type(selected_adapter) is DeterministicAdapter
        else "Trusted Python adapter: its local code controls behavior and may use external services independently. "
    )
    context.record(
        "system",
        "system",
        "all",
        adapter_notice
        + "Engine tools and shipments are synthetic. Imported messages do not establish real inventory or supplier facts.",
        data={
            "seed": snapshot.seed,
            "adapter": selected_adapter.name,
            "core_dispatches_network": False,
        },
    )
    for role in context.needed_roles:
        if context.agent_for_role(role) is None:
            context._missing_agent(role)
    buyer = context.agent_for_role("buyer")
    if buyer:
        context.record(
            "message",
            "requester",
            buyer.id,
            snapshot.initial_message,
            data={"message_type": "initial_request", "fixture_input": True},
        )
        context.queue.append(
            IncomingMessage("requester", buyer.id, "initial_request", snapshot.initial_message)
        )
    while context.queue and context.turns < 60:
        message = context.queue.popleft()
        agent = context.agent_by_id(message.recipient_id)
        if agent is None:
            context._missing_agent(message.recipient_id, by_role=False)
            continue
        context.turns += 1
        try:
            selected_adapter.step(agent, message, context)
        except Exception as error:
            # Extension failures are evidence, never successful business outcomes.
            context._allow_final_events = True
            context.record(
                "system",
                "system",
                agent.id,
                f"Adapter failed with {type(error).__name__}; simulation stopped.",
                data={"adapter_error": type(error).__name__},
            )
            context.state.aborted = True
            context.queue.clear()
    if context.queue:
        context._allow_final_events = True
        context.record(
            "system",
            "system",
            "all",
            "Simulation stopped at the 60-turn execution limit.",
            data={"execution_limit": True},
        )
        context.state.aborted = True
    context._allow_final_events = True
    checks = _evaluate(context)
    suggestions = _suggest(context)
    metrics = Metrics(
        score=round(100 * sum(check.passed for check in checks) / len(checks)),
        goal_success=all(check.passed for check in checks),
        policy_violations=len(context.state.policy_violations),
        tool_calls=sum(event.kind == "tool" for event in context.events),
        turns=context.turns,
        simulated_minutes=sum(event.kind == "message" for event in context.events) * 2
        + sum(event.kind == "tool" for event in context.events),
        cost=context.state.spent,
    )
    return Run(
        id=str(uuid4()),
        scenario_id=snapshot.id,
        scenario_name=snapshot.name,
        created_at=datetime.now(UTC).isoformat(),
        variant="candidate" if parent_run_id else "baseline",
        parent_run_id=parent_run_id,
        seed=snapshot.seed,
        adapter=selected_adapter.name,
        metrics=metrics,
        events=context.events,
        checks=checks,
        suggestions=suggestions,
        configuration=snapshot,
    )
