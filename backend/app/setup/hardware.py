import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional, Tuple


@dataclass
class HardwareInfo:
    ram_gb: float
    cpu_name: str
    cpu_cores: int
    gpu_name: Optional[str] = None
    vram_gb: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str], timeout: float = 6.0) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _detect_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return 0.0


def _detect_gpu_nvidia() -> Optional[Tuple[str, Optional[float]]]:
    if not shutil.which("nvidia-smi"):
        return None
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if not out:
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 2:
        return None
    name = parts[0]
    try:
        vram_gb: Optional[float] = round(float(parts[1]) / 1024, 1)  # MiB -> GiB
    except ValueError:
        vram_gb = None
    return name, vram_gb


def _detect_gpu_windows_cim() -> Optional[str]:
    out = _run([
        "powershell", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)",
    ])
    return out or None


def _detect_vram_windows_registry() -> Optional[float]:
    ps = (
        "$p='HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*';"
        "Get-ItemProperty -Path $p -Name 'HardwareInformation.qwMemorySize' "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.'HardwareInformation.qwMemorySize' } | "
        "Select-Object -First 1 -ExpandProperty 'HardwareInformation.qwMemorySize'"
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps])
    try:
        return round(int(out) / (1024 ** 3), 1)
    except (ValueError, TypeError):
        return None


def detect() -> HardwareInfo:
    ram = _detect_ram_gb()
    cpu_name = platform.processor() or platform.machine() or "Unknown CPU"
    cores = os.cpu_count() or 1
    gpu_name: Optional[str] = None
    vram: Optional[float] = None

    nv = _detect_gpu_nvidia()
    if nv:
        gpu_name, vram = nv
    else:
        gpu_name = _detect_gpu_windows_cim()
        vram = _detect_vram_windows_registry()

    return HardwareInfo(ram_gb=ram, cpu_name=cpu_name, cpu_cores=cores, gpu_name=gpu_name, vram_gb=vram)
