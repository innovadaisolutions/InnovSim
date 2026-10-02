"""An intentionally incomplete workflow that improves through observed handoff gaps."""

from .models import Agent, Scenario, World


def default_agents() -> list[Agent]:
    return [
        Agent(
            id="buyer",
            name="Buyer coordinator",
            company="Northstar Manufacturing",
            role="buyer",
            prompt="Recover the complete order by its deadline. Require approved expenditure and confirm delivery.",
            skills=["place_order", "escalate_delay", "accept_delivery"],
            tools=[],
            enabled=True,
        ),
        Agent(
            id="supplier",
            name="Supplier planner",
            company="Atlas Components",
            role="supplier",
            prompt="Check actual stock, report the delivery estimate honestly, and ship only available stock.",
            skills=["check_inventory", "report_delay", "standard_delivery"],
            tools=["inventory_check", "ship_standard"],
            enabled=True,
        ),
        Agent(
            id="logistics",
            name="Logistics coordinator",
            company="Swift Freight",
            role="logistics",
            prompt="Quote freight options. Obtain explicit budget approval before booking expedited delivery.",
            skills=["quote_expedite"],
            tools=["quote_expedite"],
            enabled=True,
        ),
        Agent(
            id="supervisor",
            name="Budget supervisor",
            company="Northstar Manufacturing",
            role="supervisor",
            prompt="Approve only a quoted expenditure within the order's budget. Return the authorization to logistics.",
            skills=["budget_review"],
            tools=["approve_spend"],
            enabled=True,
        ),
    ]


def supplier_delay() -> Scenario:
    return Scenario(
        id="supplier-delay",
        name="Supplier delay recovery",
        description=(
            "Recover 100 components by day 2 when standard shipping takes 5 days. "
            "The first workflow has an approval handoff gap; the next reveals a missing booking capability. "
            "All companies, stock, tools and spending are synthetic."
        ),
        domain="supply-chain",
        initial_message=(
            "We need 100 components within two days. Atlas reports a five-day standard shipping delay. "
            "Please coordinate a complete delivery without spending more than the approved $1,000 budget."
        ),
        agents=default_agents(),
        world=World(
            order_quantity=100,
            available_stock=120,
            delay_days=5,
            expedited_cost=750.0,
            budget_limit=1_000.0,
            required_delivery_days=2,
            expedited_delivery_days=1,
        ),
        seed=42,
    )


def default_scenarios() -> list[Scenario]:
    delay = supplier_delay()
    budget = delay.model_copy(deep=True)
    budget.id, budget.name = "expedited-over-budget", "Expedited freight exceeds the budget"
    budget.description = (
        "All handoff capabilities are enabled, but freight costs $1,250 against a $1,000 budget. "
        "The supervisor must decline it. A prompt or tool change cannot legitimately raise the budget."
    )
    budget.world.expedited_cost = 1_250.0
    logistics = next(agent for agent in budget.agents if agent.role == "logistics")
    logistics.skills += ["request_approval", "book_expedite"]
    logistics.tools += ["book_expedite"]
    stock = delay.model_copy(deep=True)
    stock.id, stock.name = "stock-shortage", "Insufficient supplier stock"
    stock.description = (
        "Only 60 of the required 100 components exist in the synthetic supplier inventory. "
        "Freight tools cannot manufacture missing stock; the workflow should report an unresolved capacity constraint."
    )
    stock.world.available_stock = 60
    return [delay, budget, stock]
