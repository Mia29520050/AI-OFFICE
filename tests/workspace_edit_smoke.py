from __future__ import annotations

import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    create_rel = f"tests/workspace-edit-create-{uuid.uuid4().hex[:8]}.txt"
    edit_rel = f"tests/workspace-edit-existing-{uuid.uuid4().hex[:8]}.txt"
    agent_rel = f"tests/workspace-agent-proposal-{uuid.uuid4().hex[:8]}.md"
    edit_path = ROOT / edit_rel
    created_path = ROOT / create_rel
    client = httpx.Client(base_url=BASE, timeout=180)
    try:
        # Create -> review -> apply -> backup -> rollback.
        create = client.post("/api/workspace/changes/propose", json={
            "path": create_rel, "content": "Created safely by workspace editor.\n",
            "summary": "Create smoke-test file", "agent": "Workspace",
        })
        assert create.status_code == 200, create.text
        proposal = create.json()
        assert proposal["status"] == "pending" and proposal["action"] == "create"
        assert "/dev/null" in proposal["diff"]
        assert not created_path.exists()
        assert client.post(f"/api/workspace/changes/{proposal['id']}/approve",
                           json={"confirm": False}).status_code == 403
        applied = client.post(f"/api/workspace/changes/{proposal['id']}/approve",
                              json={"confirm": True})
        assert applied.status_code == 200, applied.text
        applied_data = applied.json()
        assert created_path.read_text(encoding="utf-8") == "Created safely by workspace editor.\n"
        manifest = ROOT / applied_data["backup_path"]
        assert manifest.is_file()
        rolled = client.post(f"/api/workspace/changes/{proposal['id']}/rollback",
                             json={"confirm": True})
        assert rolled.status_code == 200, rolled.text
        assert rolled.json()["status"] == "rolled_back"
        assert not created_path.exists()

        # Edit -> stale-hash conflict must not overwrite an external change.
        edit_path.write_text("original contents\n", encoding="utf-8")
        stale = client.post("/api/workspace/changes/propose", json={
            "path": edit_rel, "content": "proposed contents\n",
            "summary": "Edit existing file", "agent": "Workspace",
        })
        assert stale.status_code == 200, stale.text
        stale_id = stale.json()["id"]
        edit_path.write_text("external change after proposal\n", encoding="utf-8")
        conflict = client.post(f"/api/workspace/changes/{stale_id}/approve",
                               json={"confirm": True})
        assert conflict.status_code == 409
        assert edit_path.read_text(encoding="utf-8") == "external change after proposal\n"

        # Fresh proposal -> backup exact original bytes -> rollback restores them.
        fresh = client.post("/api/workspace/changes/propose", json={
            "path": edit_rel, "content": "approved new contents\n",
            "summary": "Fresh edit", "agent": "Developer",
        })
        assert fresh.status_code == 200, fresh.text
        fresh_id = fresh.json()["id"]
        ok = client.post(f"/api/workspace/changes/{fresh_id}/approve",
                         json={"confirm": True})
        assert ok.status_code == 200, ok.text
        backup = ROOT / ok.json()["backup_path"]
        assert backup.is_file() and backup.read_text(encoding="utf-8") == "external change after proposal\n"
        assert edit_path.read_text(encoding="utf-8") == "approved new contents\n"
        rollback = client.post(f"/api/workspace/changes/{fresh_id}/rollback",
                               json={"confirm": True})
        assert rollback.status_code == 200, rollback.text
        assert edit_path.read_text(encoding="utf-8") == "external change after proposal\n"

        # Path, hidden-directory and extension protections.
        assert client.post("/api/workspace/changes/propose", json={
            "path": "../README.md", "content": "bad"
        }).status_code == 403
        assert client.post("/api/workspace/changes/propose", json={
            "path": "data/forbidden.txt", "content": "bad"
        }).status_code == 403
        assert client.post("/api/workspace/changes/propose", json={
            "path": "tests/unsafe.exe", "content": "bad"
        }).status_code == 415
        assert client.post("/api/workspace/changes/propose", json={
            "path": edit_rel, "content": "not approved"
        }).json()["status"] == "pending"

        # Ask the real local Workspace Agent to create a reviewable proposal.
        agent = client.post("/api/workspace/agent-propose", json={
            "path": agent_rel,
            "goal": "Create a short Markdown note with a heading and three concise bullets about safe local workspace editing.",
            "agent": "Workspace",
        })
        assert agent.status_code == 200, agent.text
        agent_data = agent.json()
        assert agent_data["status"] == "pending" and agent_data["source"] == "agent"
        assert agent_data["diff"] and not (ROOT / agent_rel).exists()
        rejected = client.post(f"/api/workspace/changes/{agent_data['id']}/reject",
                               json={"confirm": True})
        assert rejected.status_code == 200
        assert not (ROOT / agent_rel).exists()

        print("Workspace proposal: PASS - create/edit previewed before apply")
        print("Approval gate: PASS - missing confirmation blocked")
        print("Backup: PASS - original bytes stored before apply")
        print("Rollback: PASS - new file removed and existing file restored")
        print("Conflict guard: PASS - stale diff did not overwrite external change")
        print("Path policy: PASS - traversal, hidden data and unsupported extension blocked")
        print("Workspace Agent: PASS - local model generated pending diff; no disk write before approval")
    finally:
        for path in (created_path, edit_path, ROOT / agent_rel):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        client.close()


if __name__ == "__main__":
    main()
