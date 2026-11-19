# Agent Inventory

Audited: 2026-11-07  
Source of truth: `app/main.py`, `skills/*/SKILL.md`, `GET /api/agents`, `GET /api/skills`.

## Registered Agents

| Agent ID | Display name | Skill | Declared responsibility | Current execution |
|---|---|---|---|---|
| CEO | CEO / Orchestrator | orchestration | Receive requests, decompose and coordinate roles | Shared Qwen prompt |
| Researcher | Researcher | research | Analyze supplied topics and materials | Shared Qwen prompt |
| Developer | Developer | coding | Analyze and assist with code | Shared Qwen prompt |
| Workspace | Workspace Editor | workspace | Reviewable file proposals | Shared Qwen + dedicated proposal API |
| Vision | Vision | analysis | Analyze images/screens when requested | Shared Qwen prompt |
| Computer Use | Computer Use | computer | UIA observation and approved Windows actions | Shared Qwen + dedicated planner |
| Browser | Browser Agent | browser | DOM observation and approved browser actions | Shared Qwen + dedicated planner |
| Writer | Writer | writing | Draft documents and reports | Shared Qwen prompt |
| QA | QA | qa | Review quality and identify gaps | Shared Qwen prompt |

## Installed Skills

| Skill ID | File | Characters |
|---|---|---:|
| analysis | `skills/analysis/SKILL.md` | 589 |
| browser | `skills/browser/SKILL.md` | 1,606 |
| coding | `skills/coding/SKILL.md` | 738 |
| computer | `skills/computer/SKILL.md` | 2,033 |
| orchestration | `skills/orchestration/SKILL.md` | 941 |
| qa | `skills/qa/SKILL.md` | 658 |
| research | `skills/research/SKILL.md` | 770 |
| workspace | `skills/workspace/SKILL.md` | 1,925 |
| writing | `skills/writing/SKILL.md` | 538 |

All 9 registered roles reported an installed Skill. All roles currently report `shared_local_model`.

## Observed limitations

- The Agent catalog is hard-coded in `AGENT_CATALOG`; it is not a dynamic registry with versioned manifests.
- Skill files are plain prompt instructions loaded by role; they are not executable plugins or typed capability packages.
- `/api/chat` selects one role and calls Ollama once. It does not run a multi-agent collaboration loop.
- CEO chat loads the orchestration Skill but has no general tools to create/assign/execute tasks from the chat endpoint.
- `run_task` asks the model to choose among researcher/analyst/writer/developer/qa roles, then executes the generated steps sequentially. The role is a prompt label, not an isolated worker.
- The task runner's `analyst` role maps to the analysis Skill but is not a catalog Agent.
- Vision, Browser and Computer Use use specialized endpoints/planners, not a common Agent Runtime.
- No per-agent model, context budget, tool allowlist, timeout, retry policy or structured output contract is stored in an Agent manifest.

## Recommended Agent manifest

Each Agent should eventually have:
- stable ID and version;
- purpose and explicit input/output JSON schema;
- system prompt / Skill references;
- allowed tools and filesystem scopes;
- model preference and context budget;
- timeout and retry policy;
- approval requirements;
- acceptance criteria and verification procedure.

Start with the existing 9 Agents; add Planner and Security Reviewer as internal roles only when the common runtime can support them. Avoid multiplying visible Agent tiles before their behavior is real.
