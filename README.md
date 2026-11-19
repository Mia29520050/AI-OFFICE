# AI Office

Local-first multi-agent desktop workspace. Current milestone: 0.6.0.

## Current implementation
- Windows desktop window using pywebview + WebView2. The launcher automatically reopens through the standard-user Explorer shell if started elevated, keeping WebView2 at the same integrity level as UniKey/EVKey so Vietnamese IME input is not blocked.
- Dark VS Code-inspired workbench with activity rail, Explorer, central workspace, agents, task panels and status bar. Home uses a dashboard hero, five descriptive quick actions, a dedicated CEO chat composer and a compact workspace overview panel. Responsive layout progressively hides the right panel and Explorer, reflows quick actions/chat controls, compacts the home view at short heights, and allows an 800×560 native minimum window. Header follows a compact Antigravity-style menubar (AI Office, Workspace, View, Window); duplicate in-content minimize/maximize/close controls are removed so only native Windows title-bar controls remain. Native HWND and shortcut AppUserModelID use the AI Office infinity icon rather than the pythonw.exe host icon.
- Original infinity mark cropped from the supplied logo image, without the AI OFFICE text or four-point star. PNG and Windows ICO are stored in `app/ui/assets/` and used by the UI, shortcut and native window.
- FastAPI local backend at `127.0.0.1:8765`, Ollama runtime with Qwen3.5-4B and SQLite chat/task history.
- Functional Explorer: browse project folders and preview allow-listed text files (maximum 512 KB). Sensitive folders such as `.git`, `.venv` and `data` are hidden; traversal outside the project root is rejected.
- Workspace Editor: Workspace Agent can read the selected UTF-8 text file and create a complete-content proposal. The app shows a unified diff, waits for explicit approval, verifies the file's SHA-256 has not changed, creates a pre-apply backup, writes atomically, and supports rollback guarded by the applied hash. New-file rollback removes only the exact file created by that proposal. Proposal history and backups live under hidden `data/` and are excluded from Explorer. The Home dashboard exposes Workspace Editor, and choosing the Workspace Agent in Chat routes the request into the reviewed edit form rather than pretending a normal chat response changed a file.
- Workspace Editing Engine: the dedicated Workspace Editor Agent reads a selected UTF-8 text file (Agent context currently limited to 10,000 characters) or proposes a new allow-listed text file. It never writes directly: every request creates a persistent pending proposal with a unified diff. The user must explicitly approve; the backend re-checks the original SHA-256 to reject stale diffs, writes atomically, and stores the original bytes plus a manifest under `data/workspace-backups/`. Rollback restores an edited file or removes a created file only when the current file still matches the applied SHA-256. Proposals and backup history are kept under hidden `data/` storage. No recursive directory creation or delete proposal is exposed.
- Functional Agents view: CEO, Researcher, Developer, Workspace Editor, Vision, Computer Use, Browser, Writer and QA, with installed-skill status. Agent selection loads the associated local Skill/system prompt; all roles currently share one Qwen3.5-4B model.
- Functional Tasks view: create tasks, inspect plan, status, result and execution logs. Existing SQLite task records are preserved.
- Functional Skills view: enumerate installed `SKILL.md` files and inspect their contents.
- Tools view: observe active window, list visible windows and display a screenshot. Browser panel launches a dedicated Chrome profile at `data/browser-profile`, separate from the user's personal Chrome profile and cookies.
- Browser Automation: navigate only to public HTTP/HTTPS URLs, read page title/headings/text and visible DOM controls, and prepare DOM-targeted proposals with a local Qwen3.5-4B model. The planner uses compact DOM/text rather than screenshots to stay inside the 2K local context. Includes network request filtering for private/local addresses, a bounded proposal queue and explicit per-action approval.
- Browser actions are limited to public link clicks, non-form `type=button` clicks, filling non-sensitive text/search inputs or textareas, and scrolling. Form submission, Enter key, authentication, password entry, file download/upload, purchases, payment, publishing and account/security actions are blocked.
- After each approved browser action, the app re-observes the DOM and asks the model for verification. User-requested continuation is limited to eight steps and pauses for approval after every proposal.
- Computer Use Planner: local Qwen3.5-4B proposes exactly one click/type/scroll step from a reduced screenshot (640 px) and compact UIA tree sized for the 2K local context; it cannot run shell commands or launch apps.
- Step-by-step continuation: after a step is verified, the user can request the next proposal against the same goal. The model receives bounded history, avoids repeating completed steps, checks the original window handle/PID and stops after eight steps.
- Explicit approval queue: each proposal shows the original window, target control, text (if any), reason and expected result; expires after 120 seconds and can be cancelled. Each step needs its own approval.
- Before execution, revalidates the original window handle/PID/title and exact UIA selector. After execution, captures a fresh screenshot/UIA tree and asks the model for verification only. The next-step button appears only after a positive verification.
- Direct computer action endpoint is disabled; all desktop actions must pass through proposal and approval.
- Sensitive/high-impact targets and credential fields are blocked; no autonomous send/delete/purchase/payment/security/install/terminal actions.
- Screen images are sent to the local model only for explicit screen analysis or computer-use planning.
- One model inference queue to reduce memory pressure on 12 GB RAM / 6 GB VRAM devices.

## Not yet implemented
- Live web search and source citations.
- Unattended multi-step computer operation; current continuation pauses for explicit approval and a user-requested next step after each verified action.
- Independent model routing per role and executable skill plugins.

The app must not claim a capability that has not actually been executed. Computer Use supports a user-approved step sequence; it does not continue unattended or approve actions on behalf of the user.

## Run
- Double-click the Desktop shortcut `AI Office`, or run `Start-AI-Office.bat`.
- Ollama must be running and `qwen3.5:4b` must be available.
- Local endpoint: `http://127.0.0.1:8765`
- Data: `data/office.db`
- Workspace Editing QA: `.venv\\Scripts\\python.exe tests\\workspace_editor_check.py` (isolated create/edit/diff/approval/backup/rollback/conflict and path-safety checks).
