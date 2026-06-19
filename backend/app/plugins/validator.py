import json
import re
from pathlib import Path

from app.tools.registry import tool_registry

from .errors import PluginValidationError
from .manifest import PluginManifest

RESERVED_NAMESPACES = {
    "filesystem",
    "terminal",
    "memory",
    "agent",
    "team",
    "workspace",
    "logs",
    "http",
    "mcp",
}


def validate_manifest(plugin_dir: str | Path) -> PluginManifest:
    root = Path(plugin_dir).resolve()
    manifest_path = root / "plugin.json"
    if not manifest_path.exists():
        raise PluginValidationError("plugin.json not found")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = PluginManifest.model_validate(raw)
    except PluginValidationError:
        raise
    except Exception as exc:
        raise PluginValidationError(f"Invalid plugin.json: {exc}") from exc

    if not re.fullmatch(r"plugin_[a-z0-9_]+", manifest.id):
        raise PluginValidationError("Plugin id must match plugin_[a-z0-9_]+")

    if not _is_agentdesk_version_compatible(manifest.agentdesk_version):
        raise PluginValidationError("Incompatible agentdesk_version")

    names: set[str] = set()
    for tool in manifest.tools:
        name = tool.name
        if "." not in name:
            raise PluginValidationError(f"Tool '{name}' must use a namespace prefix")
        if tool_registry.exists(name):
            existing = tool_registry.get(name)
            if getattr(existing, "source", "") != "plugin" or getattr(existing, "plugin_id", "") != manifest.id:
                raise PluginValidationError(f"Tool '{name}' conflicts with an existing core or reserved tool")
        namespace = name.split(".", 1)[0]
        if namespace in RESERVED_NAMESPACES:
            raise PluginValidationError(f"Tool namespace '{namespace}' is reserved")
        if name in names:
            raise PluginValidationError(f"Duplicate tool name '{name}'")
        names.add(name)
        if tool.capability not in manifest.permissions:
            raise PluginValidationError(f"Tool '{name}' uses undeclared capability '{tool.capability}'")
        _resolve_inside(root, tool.entrypoint, "entrypoint")

    for skill_path in manifest.skills:
        _resolve_inside(root, skill_path, "skill")

    return manifest


def _resolve_inside(root: Path, relative_path: str, label: str) -> Path:
    candidate = (root / relative_path).resolve()
    if root != candidate and root not in candidate.parents:
        raise PluginValidationError(f"{label} path is outside plugin folder")
    if not candidate.exists():
        raise PluginValidationError(f"{label} does not exist: {relative_path}")
    return candidate


def _is_agentdesk_version_compatible(spec: str) -> bool:
    return not spec or spec.strip() in {">=0.1.0", "0.1.0", "*"}
