# Tool Registry — Current Inventory and Target Contract

## Current connected capabilities

| Capability | API / module | Current safety boundary | Durability |
|---|---|---|---|
| Workspace browse/read | `/api/workspace*`, `main.py` | Root-confined paths; hidden folders; text allowlist; 512 KB preview cap | Read-only |
| Workspace edit | `workspace_editor.py` | Proposal + unified diff + explicit approval + SHA-256 conflict check + backup + rollback | Proposal and backup JSON/files persist |
| Browser | `browser.py`, `/api/browser/*` | Dedicated Chrome profile; public HTTP(S) URL validation; DOM-based allowlist; approval per action | Pending queue is in memory |
| Computer Use | `computer.py`, `computer_use.py`, `/api/computer/*` | UIA observation; click/type/scroll only; sensitive targets blocked; explicit per-step approval; post-action verification | Pending queue is in memory |
| Screenshot / UIA | `/api/computer/screenshot`, `/tree`, `/active`, `/windows` | Observation endpoints; local desktop context | Not persisted as task artifacts by default |
| Ollama inference | `ollama_chat` | One shared model semaphore; local endpoint | No inference/task event ledger |

## Current tool restrictions

- Direct computer action endpoint always returns 403; action must go through Computer Use proposal/approval.
- Browser blocks local/private network destinations and sensitive goals/fields; form submission, downloads/uploads and sensitive operations are disabled.
- Computer Use supports click/type/scroll only; no shell command or app launch.
- Workspace Editor does not write directly from the model; approval is required and stale diffs are rejected.
- `RULES.md` requires explicit approval for destructive, external, financial, security-sensitive or irreversible actions.

## Missing common registry

There is no central registry describing each tool's:
- stable tool ID and version;
- JSON input/output schema;
- Agent allowlist;
- filesystem/network scope;
- side-effect classification;
- risk level;
- timeout and retry policy;
- approval policy;
- audit event format.

## Target contract

A future Tool Registry should expose typed definitions and a single policy gateway. An Agent must request a tool by ID with validated arguments. The policy gateway checks Agent identity, task scope, user permissions, resource scope and side-effect class before dispatch.

Recommended side-effect classes:
- `read_only`: inspect/list/read within granted scope;
- `reversible_write`: create or edit with backup and rollback;
- `external_action`: browser submission, send/share/publish;
- `destructive`: delete, overwrite, install/uninstall, security changes;
- `financial`: purchase/payment/transfer.

Only read-only tools should be auto-allowed by default. Reversible writes should use reviewable diffs. External, destructive and financial actions should require fresh human approval. Never let a Skill prompt grant permissions.
