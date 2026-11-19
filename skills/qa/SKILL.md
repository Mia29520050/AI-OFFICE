---
name: qa
description: Independent review, source traceability and verification of agent deliverables.
---
# QA skill

1. Review the original requirement and acceptance criteria, not only the implementer's summary.
2. Verify every project claim against cited Project Reader files. Confirm each `[PROJECT: path]` exists in the evidence manifest.
3. Verify every current or web claim against pages actually opened by Browser Agent. Confirm each `[WEB: URL]` is in the task's fetched-source manifest.
4. Reject fabricated dates, versions, standards, benchmark values, source URLs, file reads, test results or hardware actions.
5. Check chronology carefully. A newer report can supersede an older report; do not mark earlier steps as undone merely because later work is summarized.
6. Distinguish host-side tests, cross-builds, emulator runs and physical-device execution.
7. Classify findings as blocker, major, minor or informational. State evidence and the exact correction needed.
8. Return PASS only when acceptance criteria are met and important claims are traceable. Otherwise return FAIL.
9. Never silently fix the implementation while acting as reviewer.
