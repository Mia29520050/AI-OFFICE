# Workflow Design — Current State and Target

## Current implementation

The current `POST /api/tasks` flow:
1. Inserts one task row with status `queued`.
2. Starts `asyncio.create_task(run_task(...))` inside the API process.
3. Changes status to `planning`.
4. Calls the shared Ollama model for a 2–4 step JSON plan.
5. Filters roles to researcher/analyst/writer/developer/qa.
6. Executes each step sequentially through the same `ollama_chat` function.
7. Writes aggregate plan/result/logs to one task row.
8. Marks the task completed or failed.

This is a sequential multi-role text pipeline, not yet a dependency-aware multi-agent scheduler.

## Target workflow state machine

`draft -> planned -> awaiting_approval -> queued -> running -> verifying -> completed`

Additional terminal/interrupt states:
- `blocked`
- `failed`
- `cancelled`
- `needs_human_review`

Each step should have its own:
- task ID and parent workflow ID;
- Agent owner;
- typed input and output;
- dependency IDs;
- status and timestamps;
- retry count and last error;
- tool calls and approval references;
- acceptance criteria and verification result.

## Scheduling rules

1. Planner produces a typed plan; backend validates it before execution.
2. Build a DAG from explicit dependency IDs.
3. Only run independent steps concurrently.
4. Serialize all Ollama calls on the current 12 GB RAM / 6 GB VRAM machine.
5. Keep at most one model inference active until memory/performance measurements justify a change.
6. Persist each state transition before dispatching the next step.
7. Retry transient failures at most three times with bounded backoff.
8. Stop on permission denial, failed acceptance checks or exhausted retries.
9. QA verifies outputs against the original request, not merely whether the model returned text.
10. CEO summarizes only verified results and clearly identifies partial/blocked work.

## Recovery

On application startup:
- find workflows left in `planned`, `queued` or `running`;
- mark interrupted in-flight steps as `interrupted`;
- revalidate inputs and workspace hashes;
- resume only safe/idempotent steps;
- require fresh approval for expired or side-effecting proposals;
- never silently replay an external action.

## User experience

A workflow should appear as one parent task with a timeline and expandable child steps. Show Agent owner, status, dependencies, output preview, retry/error and approval state. The chat should remain the conversational entry point; task execution should be inspectable in the Tasks view.
