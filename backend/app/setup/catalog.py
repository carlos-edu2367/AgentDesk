from dataclasses import dataclass, asdict
from typing import List
from app.setup.hardware import HardwareInfo


@dataclass
class ModelEntry:
    tag: str
    label: str
    params: str
    approx_size_gb: float
    min_budget_gb: float
    vision: bool
    blurb: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Tier:
    key: str
    label: str
    max_budget_gb: float  # upper bound, exclusive; inf for the top tier
    models: List[ModelEntry]


# Tags + download sizes verified against the Ollama library on 2026-06-23.
# min_budget_gb ~= approx_size_gb * 1.25 (weights + context overhead).
CATALOG: List[Tier] = [
    Tier("light", "Light", 4.0, [
        ModelEntry("qwen3.5:0.8b", "Qwen 3.5 0.8B", "0.8B", 1.0, 1.3, False, "Tiny and fast; runs on almost anything."),
        ModelEntry("qwen3.5:2b", "Qwen 3.5 2B", "2B", 2.7, 3.4, False, "Small but capable general model."),
    ]),
    Tier("balanced_light", "Balanced-light", 8.0, [
        ModelEntry("qwen3.5:4b", "Qwen 3.5 4B", "4B", 3.4, 4.3, False, "Good quality at low memory."),
        ModelEntry("gemma4:e2b-it-qat", "Gemma 4 E2B (QAT)", "2B eff.", 4.3, 5.4, True, "Efficient multimodal, quality-preserving quant."),
        ModelEntry("qwen3.5:9b", "Qwen 3.5 9B", "9B", 6.6, 8.0, False, "Strong all-rounder."),
    ]),
    Tier("balanced", "Balanced", 16.0, [
        ModelEntry("gemma4:12b", "Gemma 4 12B", "12B", 7.6, 9.5, True, "Multimodal, great general reasoning."),
        ModelEntry("gemma4:e4b", "Gemma 4 E4B", "4B eff.", 9.6, 12.0, True, "Higher-quality efficient multimodal."),
        ModelEntry("qwen3.5:9b", "Qwen 3.5 9B", "9B", 6.6, 8.0, False, "Strong all-rounder."),
    ]),
    Tier("strong", "Strong", 32.0, [
        ModelEntry("qwen3.5:27b", "Qwen 3.5 27B", "27B", 17.0, 21.3, False, "High quality; needs a strong GPU or lots of RAM."),
        ModelEntry("gemma4:26b", "Gemma 4 26B (MoE)", "26B MoE", 18.0, 22.5, True, "Mixture-of-experts, ~3.8B active per token."),
    ]),
    Tier("max", "Max", float("inf"), [
        ModelEntry("gemma4:31b", "Gemma 4 31B", "31B", 20.0, 25.0, True, "Dense flagship; best Gemma quality."),
        ModelEntry("qwen3.5:35b", "Qwen 3.5 35B", "35B", 24.0, 30.0, False, "Top-tier quality for capable workstations."),
    ]),
]


def budget_gb(hw: HardwareInfo) -> float:
    return max(hw.vram_gb or 0.0, round(hw.ram_gb * 0.6, 1))


def _tier_index_for_budget(b: float) -> int:
    for i, tier in enumerate(CATALOG):
        if b < tier.max_budget_gb:
            return i
    return len(CATALOG) - 1


def recommend(hw: HardwareInfo) -> dict:
    b = budget_gb(hw)
    idx = _tier_index_for_budget(b)
    tier = CATALOG[idx]
    primary = [m for m in tier.models if m.min_budget_gb <= b] or tier.models
    fallback = CATALOG[idx - 1].models if idx > 0 else []
    return {
        "budget_gb": b,
        "tier": tier.key,
        "tier_label": tier.label,
        "models": [m.to_dict() for m in primary],
        "fallback_models": [m.to_dict() for m in fallback],
    }
