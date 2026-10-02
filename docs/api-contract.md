# Prototype API contract

All endpoints use JSON under `/api`. The local demo uses deterministic Python agents and simulated tools. No model credentials, live mailbox, or live business actions are used.

## Models

```ts
type Agent = { id: string; name: string; company: string; role: string; prompt: string; skills: string[]; tools: string[]; enabled: boolean };
type Scenario = { id: string; name: string; description: string; domain: string; initial_message: string; agents: Agent[]; world: { order_quantity: number; available_stock: number; delay_days: number; expedited_cost: number; budget_limit: number; [key: string]: unknown }; seed: number };
type Event = { id: string; step: number; kind: 'message' | 'tool' | 'check' | 'system'; agent_id: string; agent_name: string; recipient: string; content: string; tool_name?: string; data?: Record<string, unknown> };
type Check = { id: string; name: string; passed: boolean; evidence: string; event_ids: string[] };
type Suggestion = { id: string; kind: string; title: string; rationale: string; agent_id?: string; patch: Record<string, unknown>; evidence_event_ids: string[] };
type Run = { id: string; scenario_id: string; scenario_name: string; created_at: string; variant: 'baseline' | 'candidate'; parent_run_id: string | null; seed: number; adapter: string; metrics: { score: number; goal_success: boolean; policy_violations: number; tool_calls: number; turns: number; simulated_minutes: number; cost: number }; events: Event[]; checks: Check[]; suggestions: Suggestion[]; configuration: Scenario };
```

`score` is 0–100. `cost` is hypothetical business expenditure, not model/API spend. `simulated_minutes` is a fixture estimate, not wall-clock performance. The scenario's tools are mock capabilities. Prompt edits are captured but the deterministic adapter follows skills/tools, not LLM instructions.

## Endpoints

- `GET /api/health` → `{status: 'ok', mode: 'simulation', adapter: 'deterministic'}`.
- `GET /api/scenarios` → `Scenario[]`, seeded with at least one supplier-delay example.
- `GET /api/scenarios/{id}` → `Scenario`.
- `POST /api/scenarios` with `Scenario` → saved `Scenario` (upsert).
- `GET /api/runs` → `Run[]`, newest first (last 50).
- `POST /api/runs` with `{scenario_id: string}` → persisted baseline `Run` using saved scenario.
- `GET /api/runs/{id}` → `Run`.
- `POST /api/runs/{id}/refine` with `{suggestion_id: string}` → persisted candidate `Run`, applying the selected patch to the parent's immutable configuration and rerunning with the same seed. Its `parent_run_id` identifies the compared run. Candidate refinements can be chained.
- `POST /api/import/email` with `{text: string, name?: string}` → persisted `Scenario` cloned from the supplier-delay fixture, with email body as `initial_message`. Accept plain text and RFC822 `.eml` text. No OAuth, mailbox fetch or message send.

Missing resources return 404. Validation errors return 422. No web API may execute user-submitted code or arbitrary outbound network calls.
