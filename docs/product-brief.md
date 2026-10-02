# InnovSim: product brief

## The idea

A company should be able to rehearse its AI-assisted workflows before allowing agents to act with clients, suppliers, and partners. InnovSim is a proposed open-source, customer-managed platform for that rehearsal and improvement process.

The customer brings the agent system it already runs, relevant business evidence, and success criteria. The workbench supplies an editable simulation environment, counterpart behaviours, tool/state fixtures, measurements, and evidence-linked improvement proposals. Employees can use ordinary code and their preferred coding assistants to adapt the platform itself.

The originating vision is broader than supply-chain management. Procurement is the first test case, with architecture that can later support other business workflows. The user-facing promise is: **test and improve your business-agent workflow on your infrastructure, using your own code and evidence.**

## The product loop

1. **Describe the workflow.** Define agents, their roles, prompts, skills, tools, the shared business environment, and the decisions requiring human authority.
2. **Create reviewable scenarios.** Import approved historical evidence or write fixtures. Keep observed facts, assumptions, and expected outcomes visible.
3. **Connect the system.** Adapt locally running or remotely hosted agents through a stable interface; the customer controls the runtime and model provider.
4. **Simulate.** Exercise the workflow against counterpart behaviours and resettable tools/state. Capture communications, actions, failures, and business outcomes.
5. **Refine.** Suggest adding/removing agents, reprompting agents or skills, adding/removing skills, and adding/adjusting tools. Each proposal needs failure evidence and an editable change.
6. **Compare.** Apply a chosen change to a candidate configuration, rerun the same scenario cohort, and inspect benefits and regressions before a deployment decision.

The intended platform is code-first. Visual editing helps people inspect and review the system; it does not determine which integrations or logic they are allowed to write. Versioned customer code remains the source of deployable behaviour.

## What “PaaS” means here

The initial offer is a **customer-managed platform plus implementation/support services**. It can run on a local workstation, a company server, or customer cloud infrastructure such as Azure. An optional vendor-hosted service can be considered later.

The platform does not need to host production agents. It orchestrates tests against adapters, mocked tools, and controlled counterpart models. MCP can connect tools, A2A can connect agents, and custom APIs can connect either; transport is separate from the simulated business environment.

The first code is Apache-2.0. Customers can inspect and modify it, create connectors, and keep private business customisations. The commercial hypotheses are maintained releases, connector/domain expertise, support, and recurring evaluation services. No paid tier or proprietary module is included in this first prototype.

## First customer and first workflow

Target a procurement or operations team already building supplier-email automation, with an engineering/automation owner willing to review scenarios. A workflow without an owner, accessible data, or measurable acceptance criteria is a poor first pilot.

Start with a delayed purchase order. The buyer needs a defined quantity by a deadline; the supplier has limited stock and delayed replenishment; the logistics option costs extra; the buyer has a spending/approval limit. The system must identify the order, inspect available options, avoid promises unsupported by state, and escalate when authority or facts are missing.

Useful variations include partial delivery, late responses, contradictory information, changed quantities, absent order references, and unavailable tools. This is a tractable first business world; simulating an entire supply chain is a later ambition.

Proposed pilot outcome: demonstrate a measured reduction in selected workflow failures on a business-reviewed, held-out scenario cohort, while preserving approval constraints. Agree thresholds with the customer before testing. Completion rate, unauthorised commitments, escalation quality, cost, latency, and review effort should remain visible separately.

## How to sell it

Start with a fixed-scope paid pilot that solves a release problem: “Before this supplier workflow goes live, we will show where it fails and deliver tested changes your team can run and own.” Deliver the environment, cases, adapter, report, and customer installation.

Price and packaging are hypotheses: investigate EUR 5,000–15,000 for a four-to-six-week pilot, then EUR 500–2,000/month for maintained software and evaluation/support work. Customer infrastructure and model spend are separate. Validate the buyer, budget, effort, and value in interviews; these numbers are not established market prices or proof of demand.

Avoid starting with a generic marketplace, universal agent builder, or broad “future of agent commerce” proposition. Expand after repeated paid pilots reveal common environments, connectors, and failure patterns. [The research](research.md) documents close competitors and the assumptions that require validation.

## This prototype's scope

The initial application demonstrates an offline supplier-order simulation with deterministic scripted agents, a shared world, mocked tools, business assertions, event traces, stored runs, and selected evidence-linked configuration patches that can be rerun as candidates. Users can inspect and edit the represented agent configuration.

This prototype does not interpret edited prompts with an LLM. Suggestions are rule-derived patches, not learned optimisation. Email import accepts text or `.eml` text to seed the existing supplier fixture; it does not fetch a mailbox, learn client personas, or reconstruct a real business. MCP, A2A, actual model adapters, live read connectors, richer topology optimisation, arbitrary-code runners, and production access controls are planned extensions.

The demo should be used to assess the workflow and foundation. Production readiness and commercial value require evidence from an actual connected agent and a reviewed customer pilot.
