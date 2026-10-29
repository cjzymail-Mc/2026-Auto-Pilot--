"""Narrow, explicit authorization for historical-sample test drafts only."""
import hashlib
import json
from pathlib import Path

MARKER = "测试、勿流转"


def validate_test_draft_authorization(plan, base_dir=None, verify_sources=True):
    block = plan.get("test_draft_authorization")
    if plan.get("document_type") not in {"travel", "express", "rd_materials"}:
        return False
    if not isinstance(block, dict) or set(block) != {
            "task_id", "document_type", "mode", "allow_submit", "marker",
            "scope", "authorization_path", "authorization_sha256"}:
        return False
    expected = {"task_id": plan.get("task_id"),
                "document_type": plan.get("document_type"), "mode": "save_draft",
                "allow_submit": False, "marker": MARKER, "scope": "historical_sample"}
    if any(type(block.get(k)) is not type(v) or block.get(k) != v for k, v in expected.items()):
        return False
    if "test_context" not in plan or MARKER not in str(plan.get("header", {}).get("description", "")):
        return False
    if not isinstance(block["authorization_path"], str) or not block["authorization_path"]:
        return False
    sha = block["authorization_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return False
    if verify_sources:
        try:
            path = Path(block["authorization_path"])
            if not path.is_absolute():
                path = Path(base_dir or ".") / path
            raw = path.read_bytes()
            proof = json.loads(raw)
            if hashlib.sha256(raw).hexdigest() != sha or not isinstance(proof, dict):
                return False
            if any(type(proof.get(k)) is not type(v) or proof.get(k) != v for k, v in expected.items()):
                return False
            if not isinstance(proof.get("user_statement"), str) or not proof["user_statement"].strip():
                return False
        except (OSError, ValueError, TypeError):
            return False
    return True
