# Delivery roadmap

## 0. First prototype — in this repository

Supplier-delay scenario, local deterministic agents, mock business state/tools, event traces, policy/outcome assertions, evidence-linked configuration refinements, immutable parent/candidate comparison, SQLite, email snapshot import, JSON editing and Python extension seam.

Acceptance: run the baseline, inspect a failure and its event evidence, apply a proposed change, observe a changed business action and outcome, and recover both runs after a restart. The checks must still catch overspend and missing approval when a new configuration tries to shortcut the workflow.

## 1. Design-partner pilot

Choose one company and one recurring workflow. Agree on what success means with an operations owner. Collect a bounded set of approved historical cases and tool snapshots. Review scenarios and counterpart assumptions with humans. Reserve a held-out subset before building any refinement loop.

Deliver Python/HTTP adapters for the partner's actual runtime, one mailbox **read/import** connector and one ERP snapshot connector. Run the system using explicit model credentials and budgets supplied by the customer. Preserve offline mock tools so experiments cannot make real commitments. Validate claimed improvements through repeat trials, failure distributions and expert review of held-out cases.

Go/no-go: a company pays for the pilot, gives sufficient source access, assigns an operations reviewer and adopts a measurable acceptance gate. A better synthetic demo score alone is insufficient evidence of market demand or production value.

## 2. Protocol adapters and system refinement

Implement versioned MCP and A2A adapters with contract tests; connect arbitrary runtimes through the same internal interface. Add a reviewed scenario compiler, live counterpart simulation, budgets and replay provenance. Support proposals for adding/removing agents, changing prompts/skills, and adding/removing/adjusting tools. Produce code/configuration diffs and evaluate them against separate regression and acceptance sets. Avoid optimizing a system against its own unquestioned judge.

## 3. Enterprise self-hosting

Authentication, permissions, isolated workers, managed secrets, encrypted backups, Postgres/queue, audit trails, telemetry and private-cloud deployment templates. Supported upgrades and offline installation. Model and connector costs belong to the customer's environment and should be reported separately from the platform subscription.

## 4. Commercial packaging

Test productized implementation + support before assuming platform subscription demand. Offer optional enterprise controls or curated scenario packs only after design partners identify value. Consider a hosted convenience tier later. Keep customer-authored adapters and scenario data portable. License changes or contributor arrangements require deliberate review before adopting any dual-license model.
