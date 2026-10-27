"""Closed document-type registry shared by intake, execution and save binding.

New types may be researched/prepared before their actual editors are modeled.
Merely adding a JSON file never enables a type for production execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path

from bpm.paths import ROOT
_REGISTRY = {
    "travel": ("travel.json", "差旅费", "08", True),
    "express": ("express.json", "快递费", "15", True),
    "rd_materials": ("rd_materials.json", "研发材料费", "11", True),
    # Round-9（ctr-15712bcb）：02/04 首件放量——offline_modeled_live_pending，
    # 离线链可用；真实页面控件测试本轮零动作（待下轮授权）。
    "office_supplies": ("office_supplies.json", "低值易耗品、办公用品采购", "02", True),
    "welfare_labor": ("welfare_labor.json", "福利费、劳保用品", "04", True),
}


class TypeConfigError(ValueError):
    def __init__(self, message, code="TYPE_CONFIG_INVALID"):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class TypeIdentity:
    document_type: str
    path: Path
    config_version: str
    sha256: str
    executable: bool
    config: dict


def resolve_type(document_type, *, require_executable=True):
    if not isinstance(document_type, str) or document_type not in _REGISTRY:
        raise TypeConfigError("unsupported document type", "UNSUPPORTED_TYPE")
    filename, label, code, executable = _REGISTRY[document_type]
    path = ROOT / "automation/document-types" / filename
    raw = path.read_bytes()
    config = json.loads(raw)
    if (config.get("document_type") != document_type
            or config.get("schema_version") != "1.0"
            or config.get("config_version") != "1.0"):
        raise TypeConfigError("type configuration identity/version mismatch")
    if executable:
        if config.get("header", {}).get("submitType", {}).get("allowed_values") != [label]:
            raise TypeConfigError("type configuration category mismatch")
        if document_type != "travel" and (config.get("category") != {"label": label, "api_code": code}
                                            or config.get("execution_state") != "offline_modeled_live_pending"):
            raise TypeConfigError("type configuration category/state mismatch")
    elif (config.get("category") != {"label": label, "api_code": code}
          or config.get("execution_state") != "awaiting_observed_structure"):
        raise TypeConfigError("pending type configuration category/state mismatch")
    # Round-9：文档级发票策略声明（02/04 首件引入）。声明级通道：字段形状封闭，
    # 语义强制（如与行级 no_invoice_rows 并存时的拒绝）在 bpm_plan 授权轮落地。
    policy = config.get("invoice_policy")
    if policy is not None:
        if (not isinstance(policy, dict)
                or set(policy) != {"mode", "required", "evidence"}
                or policy.get("mode") not in ("document_level", "row_level")
                or not isinstance(policy.get("required"), bool)
                or not isinstance(policy.get("evidence"), str) or not policy["evidence"].strip()):
            raise TypeConfigError("invoice_policy must be {mode,required,evidence} with sourced evidence",
                                  "TYPE_CONFIG_INVALID")
    if require_executable and not executable:
        raise TypeConfigError(
            label + " requires complete historical subtables and current editor modeling before execution",
            "NEEDS_INPUT")
    # Preserve every existing travel run/journal's raw-file hash. New types bind
    # the registry implementation as well as configuration bytes and identity.
    if document_type == "travel":
        digest = hashlib.sha256(raw).hexdigest()
    else:
        payload = {"document_type": document_type, "registry": _REGISTRY[document_type],
                   "config_sha256": hashlib.sha256(raw).hexdigest(),
                   "resolver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        if not executable:
            # Pending template research uses this configured scalar projection.
            # Bind it too, even though pending types cannot execute or save.
            projection = ROOT / "automation/document-types/travel.json"
            payload["research_projection_sha256"] = hashlib.sha256(projection.read_bytes()).hexdigest()
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return TypeIdentity(document_type, path, config["config_version"], digest, executable, config)


def type_from_category(value):
    """Only explicit observed codes or exact rendered labels; never infer from number."""
    if isinstance(value, str):
        for document_type, (_, label, code, _) in _REGISTRY.items():
            if value in (label, code):
                return document_type
    raise TypeConfigError("template category missing or not recognized", "UNSUPPORTED_TYPE")


def check_template_type(snapshot, document_type):
    """Legacy travel snapshots without a category remain readable, never contradictory ones."""
    declared = snapshot.get("document_type")
    category = snapshot.get("header", {}).get("submitType")
    if declared is not None and declared != document_type:
        raise TypeConfigError("template belongs to a different document type", "TYPE_MISMATCH")
    if category is not None and type_from_category(category) != document_type:
        raise TypeConfigError("template category differs from task/plan", "TYPE_MISMATCH")
    if document_type != "travel" and (declared is None or category is None):
        raise TypeConfigError("new-type template requires explicit category identity", "NEEDS_INPUT")
    if document_type != "travel" and (not isinstance(snapshot.get("uuid"), str)
                                      or not re.fullmatch(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", snapshot["uuid"])):
        raise TypeConfigError("new-type template requires an exact captured UUID", "NEEDS_INPUT")
