import shutil
from pathlib import Path

from app.storage.appdata import get_appdata_dir

from .manifest import PluginManifest


def copy_plugin_to_appdata(source_dir: str | Path, manifest: PluginManifest) -> Path:
    source = Path(source_dir).resolve()
    target = get_appdata_dir() / "plugins" / "installed" / manifest.id
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target
