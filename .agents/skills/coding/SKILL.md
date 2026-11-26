---
name: coding
description: Safe repository implementation, modern web standards, and paranoid security review.
---
# Coding skill

1. **Pre-Implementation Inspection**: Inspect repository status, structure, and consult the Codebase Knowledge Graph (`/api/research/codebase-graph`) before modifying files to understand dependency callers.
2. **Acceptance Test First**: Define a clear, testable acceptance condition and write or update unit tests before shipping modifications.
3. **Paranoid Security Gate**:
   - Strictly prohibit obfuscated code, base64 payload decoding (`base64.b64decode` + `exec/eval`), and dynamic `eval()`.
   - Never load untrusted model checkpoints via `pickle.load` or `torch.load` without `weights_only=True`. Only use `.gguf` and `.safetensors`.
   - Protect local user data: never exfiltrate tokens, environment variables, or paths over unvalidated network sockets.
4. **Modern Web Standards (Google Chrome Modern Web Guidance)**:
   - For UI files (`app/ui/`): use native Baseline Web APIs (CSS Grid/Subgrid, Container Queries, Popover API, Native Dialog, ResizeObserver).
   - Avoid legacy JavaScript polyfills, outdated jQuery-style DOM hacks, and unnecessary external dependencies.
5. **Minimal Atomic Changes**: Make the smallest surgical change that solves the requirement. Use unified diff format with complete drop-in replacements.
6. **Execution & Evidence**: Never claim code was executed or tested unless the command actually ran and produced recorded stdout/stderr evidence.
7. **Regression Guard**: Run focused pytest unit tests first, then smoke checks. Stop after three failed attempts on one unit and report findings clearly.
