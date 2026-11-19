# AI Office — Architecture Audit

Date: 2026-11-07  
Repository: `F:\AI-Office`  
Audited release: `0.6.0`  
Scope: read-only repository/runtime audit plus focused Workspace Editor lifecycle test.

## Executive summary

AI Office already has a useful local-first foundation: FastAPI + pywebview, Ollama/Qwen3.5-4B, SQLite conversations/tasks, a 9-role catalog, 9 local Skill files, a single-model inference semaphore, Workspace Editor proposals with diff/backup/rollback, and approval-gated Browser/Computer Use planners.

However, the current system is **not yet a true multi-agent orchestration runtime**. The Agent catalog is a role/prompt registry; all roles share one model. The current task runner asks one model to create a short plan, then runs the steps sequentially as text prompts. It does not dispatch isolated Agent workers, execute registered tools as part of a general agent loop, maintain a dependency graph, or resume interrupted work.

## Verified current state

- FastAPI local API: `127.0.0.1:8765`; app version `0.6.0`.
- Ollama online; only `qwen3.5:4b` was returned by `/api/tags`.
- Model is Q4_K_M, about 3.3 GB on disk, reported 4.2B parameters.
- One `asyncio.Semaphore(1)` serializes model inference.
- Model requests use `num_ctx=2048`, `num_predict` capped at 1600 and `keep_alive=5m`.
- Agent catalog: 9 roles; Skill registry: 9 local `SKILL.md` files.
- SQLite schema: `conversations`, `messages`, `tasks`.
- Two completed task records exist.
- Browser, Computer Use and Workspace Editor routes are registered.
- Workspace Editor uses persistent JSON proposals, atomic writes, SHA-256 stale-file checks, backups and rollback.
- Browser and Computer Use proposal queues are in-memory dictionaries with short expiry.
- Repository currently has no Git commits; all project files appear untracked on branch `master`.

## Important discrepancy: chat-history database

During the audit, the active `data/office.db` was observed with 2 conversation rows and 0 message rows. A pre-existing backup at `data/backups/settings-history-theme-20261106-233737/office-after-ui-repair.db` contains 1 conversation and 32 messages. Both databases pass SQLite integrity checks.

The reason the active database differs from the backup is not established by this audit. No restore, merge or overwrite was performed. Preserve both files and investigate the history migration/active database selection before any database changes.

## Main architecture gaps

1. **No general Agent worker runtime:** role selection loads a Skill prompt, but there is no isolated worker lifecycle with input/output contracts, tool permissions and completion verification.
2. **Task runner is sequential prompt chaining:** `run_task` creates 2–4 text steps and executes each in order using the same model. There is no DAG/dependency scheduler or real parallel execution.
3. **Task durability is incomplete:** task summary fields persist in SQLite, but the running coroutine is an in-process `asyncio.create_task`. There is no startup recovery, cancellation, per-step durable state or checkpoint resume.
4. **Tool use is fragmented:** Browser, Computer Use and Workspace Editor have separate APIs; there is no common typed Tool Registry, permission broker or agent tool-call loop.
5. **Approval state is not durable:** Browser and Computer Use pending proposals live in memory. Workspace proposals are durable.
6. **Capability reporting is too broad:** `task_orchestration` currently reports true when Ollama is online, although the implementation is a simple sequential text pipeline.
7. **No independent model routing:** all 9 roles use the same Qwen model.
8. **Knowledge is mostly prompt files and recent chat history:** no project memory, structured spec store, repository symbol graph or cross-task memory index.
9. **Local API has no user/session authentication:** binding to loopback reduces exposure, but local processes can call endpoints directly. Approval endpoints rely on a boolean confirmation field rather than a stronger session-bound approval token.
10. **Git baseline is absent:** no commits exist, so Git cannot currently provide a reliable change baseline or rollback history.

## Verification performed

- Python syntax compilation for application and selected test modules: passed.
- Workspace Editor lifecycle/security test: 16/16 passed.
- Read-only API inspection: status, Agent catalog, Skill registry, tasks, conversations and OpenAPI routes responded successfully.
- SQLite integrity: `ok`.
- Existing task records: 2 completed.
- Current active chat database: 0 messages; backup database: 32 messages.
- No new Agent runtime code was written during this audit.

## Recommendation

Build Phase 1 around durable task/step records, a typed Agent contract, a shared Tool Registry and a central policy/approval service. Keep the existing specialized Browser, Computer Use and Workspace Editor engines as adapters rather than replacing them. Do not enable unattended destructive actions.
