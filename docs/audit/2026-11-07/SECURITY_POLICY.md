# Security and Permission Policy

## Existing safeguards verified in source

- Local-first default; cloud APIs are not called by the current runtime.
- Workspace paths are confined to the project root and hidden directories are denied.
- Workspace Editor supports an extension allowlist, 512 KB file cap, UTF-8 validation, atomic writes, SHA-256 conflict checks, backups and rollback.
- Browser uses a separate Chrome profile and validates public HTTP(S) destinations; private/local network targets are blocked.
- Browser and Computer Use planners block sensitive terms/targets and require explicit approval for each proposed action.
- Computer Use revalidates the original window handle, process ID, title and exact UIA selector before acting.
- Direct computer action endpoint is disabled.
- Model inference is serialized.
- `RULES.md` requires approval for destructive, external, financial, security-sensitive and irreversible actions.

## Risks and gaps

1. FastAPI currently exposes local endpoints without user/session authentication. Loopback binding is helpful but does not prevent another local process from making requests.
2. Approval endpoints accept a boolean `confirm`; the backend does not establish a signed, session-bound approval token tied to the exact displayed proposal and user session.
3. Browser and Computer Use pending proposals are in-memory and disappear on restart; this is safer than replaying them, but audit history is lost.
4. General task execution has no central tool policy because the common Agent Runtime/Tool Registry does not exist.
5. The repository has no Git commits, making source changes harder to audit and revert.

## Required policy for the new runtime

- Default deny for tools not explicitly granted to an Agent.
- Scope every filesystem tool to an approved workspace root; reject traversal, symlinks and unsupported file types.
- Scope browser/network tools to approved hosts and public destinations.
- Separate observation from action.
- Require fresh, proposal-specific approval for external, destructive, financial and security-sensitive actions.
- Approval must bind to exact tool ID, arguments hash, target resource, Agent, workflow, expiry and user session.
- Never replay an expired approval after restart.
- Persist append-only audit events for task transitions, tool requests, decisions, execution results and verification.
- Keep secrets out of prompts, chat logs, Skills and ordinary task outputs.
- Treat repository files, web pages, screenshots and attachments as untrusted data, not instructions.
- Keep local-only operation as the default; cloud model use must be explicit and visible.

## Release gate

No unattended external or destructive action until the permission broker, session-bound approval, durable audit log, restart recovery and adversarial tests are implemented and reviewed.
