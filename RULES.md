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
11. Strictly follow the directory structure defined in `PROJECT_STRUCTURE.md`: place test suites in `tests/`, standalone/CLI tools in categorized subdirectories under `scripts/`, documentation in `docs/`, runtime state in `data/`, throwaway experiments in `scratch/`, AI engines in `engine/`, and all output deliverables in `Export/`. Keep the project root clean and organized.
12. Export Rule: All generated production deliverables must be stored in `Export/` (`Export/Images/`, `Export/Manga/`, `Export/3D/`, `Export/Audio/`, `Export/Video/`).
13. Hardware Guard: Strict hardware lock for 6GB VRAM / 12GB RAM environment. Always serialize GPU inference through ResourceScheduler, run ComfyUI with `--lowvram --cpu-vae --reserve-vram 1.0`, and free VRAM immediately after use.
14. Skill-First Protocol: Agents MUST read the corresponding skill documentation in `.agents/skills/` or `skills/` before performing any specialized operations.
