from app.setup import hardware
from app.setup.hardware import HardwareInfo


def test_detect_uses_components(monkeypatch):
    monkeypatch.setattr(hardware, "_detect_ram_gb", lambda: 16.0)
    monkeypatch.setattr(hardware, "_detect_gpu_nvidia", lambda: ("NVIDIA RTX 4060", 8.0))
    info = hardware.detect()
    assert info.ram_gb == 16.0
    assert info.gpu_name == "NVIDIA RTX 4060"
    assert info.vram_gb == 8.0
    assert info.cpu_cores >= 1


def test_detect_falls_back_to_cim_when_no_nvidia(monkeypatch):
    monkeypatch.setattr(hardware, "_detect_ram_gb", lambda: 8.0)
    monkeypatch.setattr(hardware, "_detect_gpu_nvidia", lambda: None)
    monkeypatch.setattr(hardware, "_detect_gpu_windows_cim", lambda: "Intel Iris Xe")
    monkeypatch.setattr(hardware, "_detect_vram_windows_registry", lambda: None)
    info = hardware.detect()
    assert info.gpu_name == "Intel Iris Xe"
    assert info.vram_gb is None


def test_to_dict_is_serializable():
    info = HardwareInfo(ram_gb=8.0, cpu_name="x", cpu_cores=4)
    d = info.to_dict()
    assert d["ram_gb"] == 8.0 and d["gpu_name"] is None
