# Working in InnovSim

This is a code-first, self-hosted business workflow simulation project. Keep the simulation core independent of agent vendors and communication protocols.

- Mock business tools by default. Simulation must never send email, modify a real ERP, or create commitments with a counterparty.
- Keep imported source evidence separate from synthetic personas and fixture state. Do not claim an imported email establishes inventory or delivery truth.
- Record configuration snapshots and the seed with every run. Refinements rerun an immutable parent snapshot; preserve the baseline.
- Derive checks from trace events and resulting business state. Label deterministic scripts, estimated time and hypothetical cost honestly.
- Never execute code supplied through the web API. Local Python adapters are trusted developer code.
- Verify changes with meaningful core/API tests and `npm run build` in `web`; inspect UI changes in the running application.
- Finish file-changing tasks with a local Git commit containing only task changes. Preserve unrelated changes. Push, publish, or open a PR only with explicit user authorization.
