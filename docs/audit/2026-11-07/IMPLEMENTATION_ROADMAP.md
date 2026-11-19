# AI Office — Implementation Roadmap

Audit baseline: 2026-11-07  
Current version: 0.6.0  
Hardware constraint: 12 GB system RAM, RTX 3050 Laptop 6 GB VRAM; one local Qwen3.5-4B model.

## Phase 0 — Baseline and repository hygiene

- [ ] Preserve current database and backup copies; investigate active-history discrepancy.
- [ ] Create a Git baseline commit only after user-approved repository initialization and secret review.
- [ ] Add deterministic tests and a repeatable test command.
- [ ] Separate runtime data, test fixtures, browser profile and source code clearly.

Exit criteria: clean, reviewable source baseline; database history state understood; no accidental secret or user-data commit.

## Phase 1 — Agent Foundation

- [ ] Define versioned Agent manifests (ID, Skill, input/output schema, model, tool allowlist, permissions, timeout, retry, acceptance).
- [ ] Implement a common Agent Runtime interface: `run(input, context) -> typed result`.
- [ ] Implement Task and Workflow models with durable parent/child step records.
- [ ] Implement state machine and persist every transition in SQLite.
- [ ] Implement a shared typed Tool Registry and policy gateway.
- [ ] Adapt existing Workspace Editor, Browser and Computer Use engines as tools/adapters.
- [ ] Add append-only execution/audit events.
- [ ] Keep one Ollama inference active at a time on this hardware.
- [ ] Add cancellation and safe restart recovery.
- [ ] Correct `/api/status` so capabilities describe verified implementation, not model availability alone.

Acceptance:
- CEO creates a typed plan with 3–5 steps.
- Backend validates ownership, dependencies, tool scopes and acceptance criteria.
- At least 3 existing roles execute through the common Agent Runtime.
- Each step persists owner, state, input/output, logs and verification.
- A forced app restart does not silently lose a workflow or replay a side effect.
- A denied permission cannot be bypassed by a Skill prompt or direct API call.
- Existing chat, history, Workspace Editor, Browser and Computer Use regressions pass.

## Phase 2 — CEO Orchestrator

- [ ] Plan validation and clarification detection.
- [ ] Agent routing based on capabilities, not only role names.
- [ ] DAG scheduling; serial execution initially, bounded concurrency later.
- [ ] Retry, timeout, failure escalation and cancellation.
- [ ] QA verification against explicit acceptance criteria.
- [ ] Final report with evidence and unresolved items.

Acceptance: one complex request is decomposed, executed by multiple roles and independently verified without falsely claiming unavailable tools.

## Phase 3 — Workflow and Skill System

- [ ] Versioned Skill manifests and reusable Skill Packs.
- [ ] Workflow templates and dependency graph.
- [ ] Checkpoints, resume and human approval nodes.
- [ ] Workflow run history and diffable configuration.

Acceptance: saved workflow can be run twice with isolated run state and recover safely after restart.

## Phase 4 — Knowledge Intelligence

- [ ] Spec Agent and structured requirements.
- [ ] Project memory separated from chat memory.
- [ ] Repository indexing and symbol/dependency graph.
- [ ] Impact analysis before code changes.
- [ ] Evidence links from decisions to files, symbols and test results.

Acceptance: Developer can identify relevant modules and affected tests before editing a project.

## Phase 5 — Verified Autonomous Execution

- [ ] Agent tool loop with bounded tool calls.
- [ ] Workspace edits remain proposal/diff/approval based.
- [ ] Browser and Computer Use remain approval-gated for external/high-impact actions.
- [ ] Test-runner tool with captured stdout/stderr and exit status.
- [ ] Recovery and rollback across multi-step workflows.

Acceptance: a bounded project task can be completed end-to-end with verified outputs, audit trail and safe rollback.

## Phase 6 — Grapuco-inspired system management

- [ ] Agent/Skill/Tool/Model/Workflow maps.
- [ ] System and project specifications.
- [ ] Code graph and change impact visualization.
- [ ] Audit dashboard and performance metrics.
- [ ] Versioned AI System registry.

Acceptance: Master can inspect how systems, agents, tools and workflows relate and why a task took a given path.

## Hardware-aware model strategy

- Start with one Qwen3.5-4B model and a single inference queue.
- Do not load nine separate models or run nine concurrent inference workers.
- Separate role prompts and tool scopes even while sharing the same model.
- Add optional cloud routing only after explicit configuration, data classification and privacy controls.
- Measure RAM, VRAM, latency and failure rate before enabling parallel model execution.
