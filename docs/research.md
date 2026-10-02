# InnovSim: viability and technical research

Researched on **2 October 2026** from the primary sources linked below. Product claims describe the inspected documentation, not independent performance verification. Commercial recommendations and prices are hypotheses to test with customers.

## Decision

Build a **customer-owned, code-first workbench for rehearsing and improving business-agent workflows**. Start with supplier order exceptions: delayed deliveries, partial fulfilment, expedite costs, missing confirmations, and decisions that require approval.

The idea is technically viable. The defensible opportunity is narrower than “agents talking to agents”: reconstruct a useful test environment from customer evidence, represent business state and constraints explicitly, run existing agents against controlled counterpart behaviours, and show which changes improve measured outcomes. Customers should be able to edit the platform and their adapters in ordinary code, with their own model providers and infrastructure.

This is a proposed positioning, not an established market gap. Simulation, open-source self-hosting, multi-turn evaluation, framework-neutral adapters, and automated prompt/code improvements already exist. There is no evidence here that this category is guaranteed to remain valuable for ten years. The first business question is whether a specific team will pay to reduce the risk and effort of releasing a specific workflow.

## What already exists

| Product or project | Verified capability | Consequence for this project |
| --- | --- | --- |
| [LangSmith evaluation](https://docs.langchain.com/langsmith/multi-turn-simulation) | Multi-turn interaction simulation is documented; its [evaluation types](https://docs.langchain.com/langsmith/evaluation-types) include offline regression tests, code evaluators, and LLM judges. | Conversation simulation and version comparisons alone are established features. |
| [LangSmith Engine](https://www.langchain.com/langsmith/engine) | Detects trace failures, red-teams agents, proposes prompt/code fixes, validates fixes, and can open reviewable PRs. Its FAQ says Engine does not support a customer-provided model. | “Suggest improvements” is already competitive. Customer control over models and explicit business-state evidence can matter, but must be demonstrated. |
| [LangWatch Scenario](https://github.com/langwatch/scenario) | Apache-2.0 simulation testing with an agent adapter, simulated users, scripted or automatic conversations, custom assertions, and per-turn judges; Python, TypeScript, and Go are supported. The [visualizer](https://scenario-docs.langwatch.ai/visualizations/) displays conversations and tool calls. | A particularly close competitor and potential reusable component. Do not claim framework-neutral simulation as a unique invention. |
| [Langfuse self-hosted](https://langfuse.com/pricing-self-host) | Free MIT-licensed core covers tracing, evaluation, prompts, datasets, and experiments. Commercial enterprise services and governance features also exist. | Self-hosting and open-source evaluation alone are insufficient differentiation. Consider exporting traces rather than rebuilding all observability. |
| [DeepEval Conversation Simulator](https://deepeval.com/docs/conversation-simulator) | Generates conversations from scenarios, expected outcomes, and personas through a callback to the application. | Persona-based conversational tests are available today. |
| [Maxim evaluation](https://www.getmaxim.ai/evals) | Markets agent simulation/evaluation with SDKs and a no-code interface. | A polished simulation workbench competes with commercial platforms as well as libraries. No performance claims are independently validated here. |
| [Promptfoo](https://www.promptfoo.dev/docs/guides/llm-redteaming/) | Open-source evaluation and adversarial tests can target custom applications. Its basic [self-hosted server](https://www.promptfoo.dev/docs/usage/self-hosting/) is explicitly described as experimental rather than production-ready. | Reuse security tests where appropriate; distinguish a local prototype from supported enterprise infrastructure. |
| [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/overview) / [CrewAI testing](https://docs.crewai.com/en/concepts/testing) | Microsoft provides agent, workflow, provider, and MCP abstractions. CrewAI has repeated crew tests and performance reports. | Connect existing runtimes instead of requiring customers to replace them with a new orchestration framework. |
| [Sierra tau benchmark repository](https://github.com/sierra-research/tau2-bench) | A simulation framework with domain policies, tools, tasks, and optional tools for the user simulator. The current README presents tau³, including text, voice, and knowledge domains. | Useful reference for task/state evaluation; a benchmark is not a ready customer-specific business platform. Version changes can affect score comparability. |
| [Dynamics 365 Procurement Agent](https://learn.microsoft.com/en-us/dynamics365/supply-chain/procurement/procurement-agent-supplier-com-overview) | The documentation, marked production-ready preview, describes supplier email processing and purchase-order change handling. Its [responsible AI FAQ](https://learn.microsoft.com/en-us/dynamics365/supply-chain/faq-supplier-communications-agent) includes downstream-impact simulation. | The proposed beachhead already has ERP-native competition. Position the workbench as cross-system rehearsal and release evidence, rather than another generic procurement agent. |

The [Microsoft magentic-ui repository](https://github.com/microsoft/magentic-ui) has also changed: its current main branch presents MagenticLite, an experimental browser/local-filesystem agent. The previous Magentic-UI release lives on a separate branch. It is useful interaction research, but should not be described as the current generic B2B simulation platform.

## Differentiation to test

1. **Evidence to scenarios:** turn an approved, bounded email/ERP sample into editable cases with source provenance, missing facts, and explicit assumptions. Preserve held-out examples.
2. **Shared business world:** model inventory, orders, deadlines, prices, authority, and commitments. Agents may negotiate; the environment determines what actions actually change state.
3. **Counterpart models:** include cooperative, incomplete, mistaken, delayed, and contradictory responses. A real counterpart need not already operate an agent.
4. **System-level improvement:** propose changes to roles, prompts, skills, tools, or workflow topology, with failure evidence and a reviewable patch.
5. **Release evidence:** compare the old and new configurations on the same test cohort; expose trade-offs such as fewer escalations versus more unauthorised commitments.

These are product hypotheses. LangWatch, LangSmith, or an ERP vendor may already meet much of a customer's need. The pilot should establish where this proposed workbench adds value and where integration with an existing tool is preferable.

## How to sell the first version

Sell a fixed-scope **supplier-exception rehearsal pilot**, with the workbench as the delivery mechanism. An abstract “agent PaaS” pitch makes the buyer responsible for discovering the value.

Proposed buyer: a procurement/operations owner paired with an engineering or automation lead at a company already preparing supplier-email automation. An implementation partner may be a useful channel because they encounter the same release problems across customers. This is a target profile, not validated demand.

Proposed four-to-six-week pilot:

- Choose one workflow and one business owner; agree which decisions can be automated and which require a person.
- Use a customer-approved sample of historical messages and relevant order snapshots. Begin with exported data and mocked writes.
- Have the business owner review 20–50 scenarios and expected actions, including ambiguous cases and exceptions.
- Connect one existing agent system, measure a baseline, propose bounded changes, and run a held-out comparison.
- Deliver runnable code, editable scenario fixtures, a before/after report, identified limitations, and a customer-operated installation.

Proposed acceptance measures: correct order/line identification; correct stock and deadline handling; unauthorised spend/commitments; appropriate escalation; workflow completion; model/tool spend; latency; and human review time. Customers must set priorities and thresholds. A weighted demo score is not automatically a useful procurement KPI.

**Pricing hypotheses, not observed willingness to pay:** test a EUR 5,000–15,000 fixed pilot and EUR 500–2,000/month for updates, support, and recurring evaluation help, with infrastructure/model usage paid by the customer. Revise these after interviews and effort estimates. Price the pilot around a measurable problem, not the number of agents. Later offers could include customer-managed enterprise support, validated domain scenario packs, connector maintenance, or an optional hosted service.

Interview questions should establish the current release process, specific failure costs, available data, who owns the budget, existing tooling, and what evidence would authorise a release. Secure a paid pilot before building a broad connector marketplace or a full general-purpose hosting platform.

## Language and infrastructure decision

| Choice | Fit for this workload | Decision |
| --- | --- | --- |
| Python | Suits scenario generation, evaluation, data handling, and agent adapters; existing simulation examples and agent frameworks provide Python interfaces. [FastAPI](https://fastapi.tiangolo.com/features/) supplies typed validation and API schemas. | Use Python 3.12, FastAPI, and Pydantic for the first backend. Keep the domain engine independent of the HTTP layer. |
| TypeScript / JavaScript | Suits an interactive browser workbench; has official MCP/A2A tooling and simulation libraries. | Use TypeScript with React for the UI. A TypeScript-only backend would also be viable; Python is an iteration preference, not a proven performance winner. |
| Rust | Suits measured CPU-intensive processing or a future execution/isolation component. Rust also has an official Tier 1 MCP SDK. | Defer until profiling or isolation requirements justify a separate component. Do not introduce it merely to optimise network-bound model calls. |

The [current MCP SDK table](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/sdk.mdx) lists Python, TypeScript, and Rust as Tier 1. Therefore protocol support is not a defensible reason to reject Rust. The initial Python/TypeScript choice optimises development and customer customisation, while HTTP and event contracts permit other languages.

Start with SQLite and a single local process. Move to PostgreSQL, asynchronous workers, resumable jobs, and bounded concurrency when customer workload requires them. Keep provider credentials and inference in the customer's chosen deployment. Installing the application locally does not itself make a remote model provider local.

## Interoperability and email

[MCP](https://modelcontextprotocol.io/specification/2026-07-28) standardises access to tools, resources, and prompts. [A2A](https://a2a-protocol.org/latest/specification/) standardises communication and task handling between agents. They serve different interfaces; neither supplies the business simulation world automatically. Ordinary HTTP, local Python callbacks, and executable adapters can remain useful alongside them.

The [official A2A Python SDK](https://github.com/a2aproject/a2a-python) currently documents spec 1.0 support and 0.3 compatibility. Pin the protocol and SDK versions, record capabilities, and test contracts. “Latest” specification URLs can change; adapters need an explicit compatibility boundary.

For imported emails, retain a source ID and separate observed facts from inferred scenario details. An exported message gives evidence of a past exchange, not a validated digital twin of a business or proof of how its employees will behave in a different situation.

For later live read connectors, [Microsoft Graph](https://learn.microsoft.com/en-us/graph/permissions-reference) distinguishes `Mail.Read` from `Mail.ReadBasic`, which excludes bodies and attachments. [Gmail's scope documentation](https://developers.google.com/workspace/gmail/api/auth/scopes?hl=en) classifies `gmail.readonly` as restricted; verification and security-assessment requirements depend on how restricted data is accessed and handled. Customer-managed installations still need a deliberate authentication design. Keep simulated sending and ERP writes disconnected from live actions.

## Refinement must earn its evidence

A model can suggest an attractive fix that merely overfits its own simulated counterpart. Keep business assertions deterministic where possible and use model judges for supplementary criteria. Review simulator fidelity with the domain owner, preserve held-out source cases, run repeated trials for stochastic agents, and report uncertainty.

Distinguish three operations:

- **Trace replay:** reproduce recorded events and outcomes for inspection; it cannot prove a changed agent would make better decisions.
- **Controlled re-execution:** rerun a changed configuration in a reset environment; comparable inputs do not guarantee identical model responses.
- **Live operation:** interact with real systems or counterparties; this requires a separate deployment and authority boundary.

Refinement proposals should include event/source evidence, the suspected failure, the editable change, risks, and a candidate-run comparison. Do not automatically deploy proposals or treat a judge score as approval.

## Open-source and revenue

The initial project uses **Apache-2.0**, following the [official Apache license](https://www.apache.org/licenses/LICENSE-2.0.html). It permits customers to modify the code privately and use their own connections; its terms include notices and contributor patent provisions. Revenue is proposed from expertise, maintained releases, support, and services rather than restricting the ability to run the core.

The [OSI license definition](https://opensource.org/licenses) distinguishes open-source terms from arbitrary source availability. Restrictions on competitors, commercial users, or fields of use should not be presented as ordinary open-source licensing. If reciprocal sharing is a future priority, [AGPL section 13](https://www.gnu.org/licenses/agpl-3.0.html#section13) requires a source offer to remote users of modified network-interactive versions. That trade-off may complicate private customer modifications and should be decided explicitly before a licensing change. No proprietary enterprise module or commercial licensing scheme is implemented in this prototype.

## What this first implementation establishes

The first MVP uses **offline deterministic scripted agents**, a shared supplier-order world, mocked tools, assertions, event evidence, stored configurations/runs, and selected configuration patches followed by a candidate rerun. This establishes the product loop and an extensible application foundation.

It does **not** establish genuine LLM-agent behaviour, learned counterpart models, automatic code/prompt optimisation, production security, live mailbox integration, or MCP/A2A interoperability. Imported `.eml` text seeds an existing fixture; it does not reconstruct a workflow from customer history. Prompts are editable and captured, but the deterministic adapter acts through scripted skills/tools rather than interpreting those prompts. Business cost and elapsed minutes are fixture values, not verified savings or model bills.

The next technical proof should connect one actual customer agent to a reviewed, resettable fixture, then validate a small held-out cohort with a domain owner. The next commercial proof should be a paid, bounded pilot with an agreed acceptance criterion.
