from app.setup.catalog import recommend, budget_gb
from app.setup.hardware import HardwareInfo


def test_budget_uses_max_of_vram_and_60pct_ram():
    assert budget_gb(HardwareInfo(ram_gb=16.0, cpu_name="x", cpu_cores=4)) == 9.6
    assert budget_gb(HardwareInfo(ram_gb=16.0, cpu_name="x", cpu_cores=4, vram_gb=12.0)) == 12.0


def test_low_ram_no_gpu_recommends_light_tier():
    rec = recommend(HardwareInfo(ram_gb=4.0, cpu_name="x", cpu_cores=2))  # budget 2.4
    assert rec["tier"] == "light"
    tags = [m["tag"] for m in rec["models"]]
    assert "qwen3.5:0.8b" in tags


def test_midrange_recommends_balanced_and_has_fallback():
    rec = recommend(HardwareInfo(ram_gb=24.0, cpu_name="x", cpu_cores=8))  # budget 14.4
    assert rec["tier"] == "balanced"
    assert any(m["tag"] == "gemma4:12b" for m in rec["models"])
    assert len(rec["fallback_models"]) > 0


def test_high_vram_recommends_max_tier():
    rec = recommend(HardwareInfo(ram_gb=64.0, cpu_name="x", cpu_cores=16, gpu_name="RTX 5090", vram_gb=32.0))
    assert rec["tier"] == "max"
    assert any(m["tag"] == "gemma4:31b" for m in rec["models"])


def test_models_only_include_those_that_fit_budget():
    rec = recommend(HardwareInfo(ram_gb=10.0, cpu_name="x", cpu_cores=4))  # budget 6.0
    for m in rec["models"]:
        assert m["min_budget_gb"] <= 6.0
