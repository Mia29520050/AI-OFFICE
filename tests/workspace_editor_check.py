from __future__ import annotations
import uuid
from pathlib import Path
import httpx

BASE = "http://127.0.0.1:8765"
ROOT = Path(r"F:\AI-Office")
client = httpx.Client(timeout=30)
checks: list[tuple[str, bool, str]] = []
token = uuid.uuid4().hex[:10]
create_name = f"workspace_editor_check_{token}.md"
conflict_name = f"workspace_editor_conflict_{token}.md"
create_path = ROOT / create_name
conflict_path = ROOT / conflict_name

def record(label: str, ok: bool, detail: str = "") -> None:
    checks.append((label, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), label, detail)

def post_proposal(path: str, content: str, summary: str):
    return client.post(BASE + "/api/workspace/changes/propose", json={
        "path": path, "content": content, "summary": summary, "agent": "Workspace"
    })

try:
    first = post_proposal(create_name, "baseline line\n", "Create-file lifecycle test")
    record("create proposal pending without write",
           first.status_code == 200 and first.json().get("status") == "pending" and not create_path.exists(),
           str(first.status_code))
    if first.status_code != 200:
        raise RuntimeError(first.text)
    first_data = first.json()
    record("new-file unified diff", "/dev/null" in first_data.get("diff", "") and "+baseline line" in first_data.get("diff", ""))

    denied = client.post(BASE + f"/api/workspace/changes/{first_data['id']}/approve", json={"confirm": False})
    record("approval requires explicit confirmation", denied.status_code == 403, str(denied.status_code))

    applied = client.post(BASE + f"/api/workspace/changes/{first_data['id']}/approve", json={"confirm": True})
    record("create applies after approval", applied.status_code == 200 and create_path.read_text(encoding="utf-8") == "baseline line\n",
           str(applied.status_code))
    if applied.status_code != 200:
        raise RuntimeError(applied.text)
    created = applied.json()
    manifest = ROOT / created["backup_path"]
    record("create has durable backup manifest", manifest.is_file(), str(manifest))

    edited = post_proposal(create_name, "revised line\n", "Edit-file lifecycle test")
    record("edit diff shows remove and add",
           edited.status_code == 200 and "-baseline line" in edited.json().get("diff", "") and "+revised line" in edited.json().get("diff", ""),
           str(edited.status_code))
    if edited.status_code != 200:
        raise RuntimeError(edited.text)
    edited_data = edited.json()

    edit_applied = client.post(BASE + f"/api/workspace/changes/{edited_data['id']}/approve", json={"confirm": True})
    record("edit applies after approval",
           edit_applied.status_code == 200 and create_path.read_text(encoding="utf-8") == "revised line\n",
           str(edit_applied.status_code))
    backup = ROOT / "data" / "workspace-backups" / edited_data["id"] / "before.bin"
    record("edit backup preserves exact original bytes",
           backup.is_file() and backup.read_bytes() == b"baseline line\n")

    rollback_edit = client.post(BASE + f"/api/workspace/changes/{edited_data['id']}/rollback", json={"confirm": True})
    record("edit rollback restores original",
           rollback_edit.status_code == 200 and rollback_edit.json().get("status") == "rolled_back"
           and create_path.read_bytes() == b"baseline line\n",
           str(rollback_edit.status_code))

    rollback_create = client.post(BASE + f"/api/workspace/changes/{first_data['id']}/rollback", json={"confirm": True})
    record("create rollback removes newly created file",
           rollback_create.status_code == 200 and rollback_create.json().get("status") == "rolled_back"
           and not create_path.exists(),
           str(rollback_create.status_code))

    rejected = post_proposal(create_name, "must not be written\n", "Reject lifecycle test")
    if rejected.status_code == 200:
        rejected_result = client.post(BASE + f"/api/workspace/changes/{rejected.json()['id']}/reject", json={"confirm": True})
        record("reject leaves file untouched",
               rejected_result.status_code == 200 and rejected_result.json().get("status") == "rejected"
               and not create_path.exists(),
               str(rejected_result.status_code))
    else:
        record("reject leaves file untouched", False, str(rejected.status_code))

    conflict = post_proposal(conflict_name, "agent proposal\n", "Concurrent-edit guard test")
    if conflict.status_code == 200:
        conflict_path.write_text("external edit\n", encoding="utf-8")
        blocked = client.post(BASE + f"/api/workspace/changes/{conflict.json()['id']}/approve", json={"confirm": True})
        detail = client.get(BASE + f"/api/workspace/changes/{conflict.json()['id']}")
        record("concurrent change blocks approval without overwriting",
               blocked.status_code == 409 and conflict_path.read_text(encoding="utf-8") == "external edit\n"
               and detail.status_code == 200 and detail.json().get("status") == "conflict",
               str(blocked.status_code))
    else:
        record("concurrent change blocks approval without overwriting", False, str(conflict.status_code))

    traversal = post_proposal("../outside.md", "bad", "Traversal block")
    hidden = post_proposal("data/forbidden.md", "bad", "Hidden path block")
    absolute = post_proposal(r"C:\Windows\win.ini", "bad", "Absolute path block")
    unsupported = post_proposal("unsafe.exe", "bad", "Extension block")
    record("path traversal blocked", traversal.status_code == 403, str(traversal.status_code))
    record("hidden data folder blocked", hidden.status_code == 403, str(hidden.status_code))
    record("absolute path blocked", absolute.status_code == 403, str(absolute.status_code))
    record("unsupported extension blocked", unsupported.status_code == 415, str(unsupported.status_code))
finally:
    create_path.unlink(missing_ok=True)
    conflict_path.unlink(missing_ok=True)
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"SUMMARY {passed}/{len(checks)} PASS")
    for label, ok, detail in checks:
        print("RESULT", "PASS" if ok else "FAIL", label, detail)
    client.close()

if checks and not all(ok for _, ok, _ in checks):
    raise SystemExit(1)