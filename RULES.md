# AI Office engineering rules

1. Never claim browsing, file access, screen vision or desktop actions unless a connected tool actually performed them.
2. All local file tools must be restricted to an explicitly configured workspace.
3. Every task needs an acceptance condition and a recorded result.
4. Each worker owns one task unit; avoid overlapping writes.
5. Serialize local model inference on low-memory machines.
6. Do not invent sources, benchmarks, measurements or industry standards.
7. Require approval for delete, overwrite, install, send, publish, payment, security and other irreversible actions.
8. Keep user data local by default. Do not call cloud model APIs unless the user enables them.
9. Add a focused test for every new capability and run the smoke check before release.
10. Stop after three failed attempts on one unit and report the evidence.
11. Strictly follow the directory structure defined in `PROJECT_STRUCTURE.md`: place test suites in `tests/`, standalone/CLI tools in `scripts/`, documentation in `docs/`, runtime state in `data/`, and throwaway experiments in `scratch/`. Keep the project root clean and organized.
