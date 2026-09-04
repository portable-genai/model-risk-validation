"""Packs-as-data: per-model-class rule packs looked up by name (the model-quality-gate bundle
mechanism).

This module is the single home for the NUMBERS the deterministic engines apply, exactly as
``model-quality-gate``'s ``thresholds.py`` holds ``METRIC_BUNDLES``: a sibling asks for a
pack by name and the engine reads bars from it, so a policy change is a data edit here rather
than a code edit in an engine. Three pack families live here, one per engine:

* :data:`TIERING_PACKS`   - how a model class scores the four tiering dimensions into a tier;
* :data:`BATTERY_PACKS`   - which validation tests apply to a class, and the bar each must clear;
* :data:`MONITORING_PACKS` - the amber/red monitoring thresholds per tier.

Everything is pure data. No engine hard-codes a bar; every bar is a lookup here. A pack asked
for by an unknown name raises (``UnknownPackError``) rather than defaulting, because a silent
default is a policy nobody chose. Bank-owned numbers belong in ``config/settings.yaml`` under a
``policy:`` block eventually (practices B4); these are the shipped, reviewable defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .taxonomy import DIMENSIONS, ModelClass, Tier


class UnknownPackError(KeyError):
    """A pack was requested by a name no family defines. Fail closed, never default."""


@dataclass(frozen=True, slots=True)
class TieringPack:
    """How one model class turns declared dimension levels into a materiality tier.

    ``weights`` multiplies each dimension's level points; ``tier1_floor`` / ``tier2_floor`` are
    the weighted-score floors for TIER_1 and TIER_2 (anything below the TIER_2 floor is TIER_3).
    ``regulatory_capital`` marks a class whose output feeds regulatory capital or provisioning,
    which the engine treats as a hard TIER_1 override regardless of score.
    """

    weights: dict[str, int]
    tier1_floor: int
    tier2_floor: int
    regulatory_capital: bool = False

    def __post_init__(self) -> None:
        missing = set(DIMENSIONS) - set(self.weights)
        if missing:
            raise ValueError(f"tiering pack is missing weights for {sorted(missing)}")
        if self.tier1_floor <= self.tier2_floor:
            raise ValueError("tier1_floor must be strictly above tier2_floor")


@dataclass(frozen=True, slots=True)
class TestBar:
    """One validation test's bar. ``higher_is_better`` picks the comparison direction."""

    metric: str
    bar: float
    higher_is_better: bool = True

    def passes(self, value: float) -> bool:
        """True when ``value`` clears the bar in the configured direction."""
        return value >= self.bar if self.higher_is_better else value <= self.bar


@dataclass(frozen=True, slots=True)
class BatteryPack:
    """The set of validation tests a model class must clear, each with its bar."""

    bars: tuple[TestBar, ...]

    def bar_for(self, metric: str) -> TestBar:
        for bar in self.bars:
            if bar.metric == metric:
                return bar
        raise UnknownPackError(f"battery pack declares no bar for metric {metric!r}")

    @property
    def metrics(self) -> tuple[str, ...]:
        return tuple(bar.metric for bar in self.bars)


@dataclass(frozen=True, slots=True)
class MonitoringBand:
    """A per-metric amber/red band for ongoing monitoring.

    ``amber`` and ``red`` are breach thresholds; ``higher_is_worse`` says whether a rising or a
    falling value is the deterioration. A ``red`` breach is always at least as severe as
    ``amber`` for the same metric; the engine composes worst-wins across metrics.
    """

    metric: str
    amber: float
    red: float
    higher_is_worse: bool = True


@dataclass(frozen=True, slots=True)
class MonitoringPack:
    """The monitoring bands that apply at a given tier."""

    bands: tuple[MonitoringBand, ...] = field(default_factory=tuple)

    def band_for(self, metric: str) -> MonitoringBand | None:
        for band in self.bands:
            if band.metric == metric:
                return band
        return None


# --------------------------------------------------------------------------- #
# Tiering packs: one per model class. Regulatory-capital classes floor at TIER_1.
# --------------------------------------------------------------------------- #
_BALANCED = {"materiality": 3, "complexity": 2, "usage": 2, "regulatory_exposure": 3}
_CAPITAL = {"materiality": 3, "complexity": 3, "usage": 2, "regulatory_exposure": 3}

TIERING_PACKS: dict[ModelClass, TieringPack] = {
    ModelClass.SCORECARD: TieringPack(_BALANCED, tier1_floor=26, tier2_floor=18),
    ModelClass.IFRS9_CECL: TieringPack(
        _CAPITAL, tier1_floor=24, tier2_floor=16, regulatory_capital=True
    ),
    ModelClass.IRB: TieringPack(_CAPITAL, tier1_floor=24, tier2_floor=16, regulatory_capital=True),
    ModelClass.ALM: TieringPack(_BALANCED, tier1_floor=26, tier2_floor=18),
    ModelClass.PRICING: TieringPack(_BALANCED, tier1_floor=28, tier2_floor=20),
    ModelClass.ACTUARIAL: TieringPack(
        _CAPITAL, tier1_floor=24, tier2_floor=16, regulatory_capital=True
    ),
    ModelClass.AML_SCENARIO: TieringPack(_BALANCED, tier1_floor=26, tier2_floor=18),
}


# --------------------------------------------------------------------------- #
# Battery packs: which tests a class must clear. Metric names match the engine.
# --------------------------------------------------------------------------- #
_DISCRIMINATION = TestBar("auc", 0.70, higher_is_better=True)
_GINI = TestBar("gini", 0.40, higher_is_better=True)
_CALIBRATION = TestBar("calibration_error", 0.05, higher_is_better=False)
_STABILITY = TestBar("psi", 0.25, higher_is_better=False)
_BACKTEST = TestBar("exception_rate", 0.05, higher_is_better=False)

BATTERY_PACKS: dict[ModelClass, BatteryPack] = {
    ModelClass.SCORECARD: BatteryPack((_DISCRIMINATION, _GINI, _CALIBRATION, _STABILITY)),
    ModelClass.IFRS9_CECL: BatteryPack((_CALIBRATION, _STABILITY, _BACKTEST)),
    ModelClass.IRB: BatteryPack((_DISCRIMINATION, _GINI, _CALIBRATION, _BACKTEST)),
    ModelClass.ALM: BatteryPack((_CALIBRATION, _BACKTEST, _STABILITY)),
    ModelClass.PRICING: BatteryPack((_CALIBRATION, _BACKTEST)),
    ModelClass.ACTUARIAL: BatteryPack((_CALIBRATION, _STABILITY, _BACKTEST)),
    ModelClass.AML_SCENARIO: BatteryPack((_DISCRIMINATION, _STABILITY)),
}


# --------------------------------------------------------------------------- #
# Monitoring packs: per tier. TIER_1 watches the most metrics at the tightest bands.
# --------------------------------------------------------------------------- #
MONITORING_PACKS: dict[Tier, MonitoringPack] = {
    Tier.TIER_1: MonitoringPack(
        (
            MonitoringBand("psi", amber=0.10, red=0.25, higher_is_worse=True),
            MonitoringBand("auc", amber=0.68, red=0.62, higher_is_worse=False),
            MonitoringBand("exception_rate", amber=0.03, red=0.06, higher_is_worse=True),
        )
    ),
    Tier.TIER_2: MonitoringPack(
        (
            MonitoringBand("psi", amber=0.15, red=0.30, higher_is_worse=True),
            MonitoringBand("auc", amber=0.65, red=0.60, higher_is_worse=False),
        )
    ),
    Tier.TIER_3: MonitoringPack(
        (MonitoringBand("psi", amber=0.25, red=0.40, higher_is_worse=True),)
    ),
}


def tiering_pack(model_class: ModelClass) -> TieringPack:
    """The tiering pack for a class, or :class:`UnknownPackError` when none is defined."""
    try:
        return TIERING_PACKS[model_class]
    except KeyError as exc:  # pragma: no cover - every enum member has a pack; guard for edits
        raise UnknownPackError(f"no tiering pack for model class {model_class!r}") from exc


def battery_pack(model_class: ModelClass) -> BatteryPack:
    """The battery pack for a class, or :class:`UnknownPackError` when none is defined."""
    try:
        return BATTERY_PACKS[model_class]
    except KeyError as exc:  # pragma: no cover - every enum member has a pack; guard for edits
        raise UnknownPackError(f"no battery pack for model class {model_class!r}") from exc


def monitoring_pack(tier: Tier) -> MonitoringPack:
    """The monitoring pack for a tier, or :class:`UnknownPackError` when none is defined."""
    try:
        return MONITORING_PACKS[tier]
    except KeyError as exc:  # pragma: no cover - every tier has a pack; guard for edits
        raise UnknownPackError(f"no monitoring pack for tier {tier!r}") from exc
