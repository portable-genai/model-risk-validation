"""Deterministic model tiering (slice 2): materiality tier from declared dimensions.

Pure, explicit and replayable. A model's four tiering dimensions are scored by its class's
:class:`~.packs.TieringPack` (packs-as-data, the Hrz4 named-bundle shape), summed with the
pack's weights, and banded into a :class:`~.taxonomy.Tier`. Two fail-closed rules make the tier
trustworthy under incomplete data:

* an undeclared or unparseable dimension is scored at :data:`~.taxonomy.FAILSAFE_LEVEL` (HIGH),
  so an omission RAISES the tier and is recorded as a reason, never silently lowers it;
* a regulatory-capital class (IRB, IFRS9/CECL, actuarial reserving) floors at TIER_1 whatever
  the score, because a model feeding capital or provisioning is material by definition.

The LLM plays no part: it never sees this function and never produces a tier.
"""

from __future__ import annotations

from dataclasses import dataclass

from .inventory import InventoryRecord
from .kernel import Finding, Severity
from .packs import TieringPack, tiering_pack
from .taxonomy import DIMENSIONS, FAILSAFE_LEVEL, Level, Tier, level_points


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """One dimension's contribution: the level used, whether it was a failsafe, and the points."""

    dimension: str
    level: Level
    weight: int
    failsafe: bool

    @property
    def points(self) -> int:
        return level_points(self.level) * self.weight


@dataclass(frozen=True, slots=True)
class TierAssessment:
    """The tier a model lands in, with the full deterministic derivation behind it."""

    model_id: str
    tier: Tier
    score: int
    breakdown: tuple[DimensionScore, ...]
    reasons: tuple[str, ...]
    findings: tuple[Finding, ...]
    capital_override: bool

    @property
    def failsafe_dimensions(self) -> tuple[str, ...]:
        """Dimensions whose level was substituted because the record did not declare one."""
        return tuple(d.dimension for d in self.breakdown if d.failsafe)


class TieringEngine:
    """Assign a materiality tier from an inventory record. Same inputs, same tier."""

    def assess(self, record: InventoryRecord) -> TierAssessment:
        pack = tiering_pack(record.model_class)
        breakdown = self._score(record, pack)
        score = sum(d.points for d in breakdown)
        scored_tier = self._band(score, pack)
        capital = pack.regulatory_capital
        tier = Tier.TIER_1 if capital else scored_tier
        reasons = self._reasons(record, breakdown, score, pack, scored_tier, capital)
        findings = self._findings(record, breakdown, capital)
        return TierAssessment(
            model_id=record.model_id,
            tier=tier,
            score=score,
            breakdown=breakdown,
            reasons=reasons,
            findings=findings,
            capital_override=capital and scored_tier is not Tier.TIER_1,
        )

    @staticmethod
    def _score(record: InventoryRecord, pack: TieringPack) -> tuple[DimensionScore, ...]:
        out: list[DimensionScore] = []
        for dimension in DIMENSIONS:
            declared = record.level(dimension)
            failsafe = declared is None
            level = declared if declared is not None else FAILSAFE_LEVEL
            out.append(
                DimensionScore(
                    dimension=dimension,
                    level=level,
                    weight=pack.weights[dimension],
                    failsafe=failsafe,
                )
            )
        return tuple(out)

    @staticmethod
    def _band(score: int, pack: TieringPack) -> Tier:
        if score >= pack.tier1_floor:
            return Tier.TIER_1
        if score >= pack.tier2_floor:
            return Tier.TIER_2
        return Tier.TIER_3

    @staticmethod
    def _reasons(
        record: InventoryRecord,
        breakdown: tuple[DimensionScore, ...],
        score: int,
        pack: TieringPack,
        scored_tier: Tier,
        capital: bool,
    ) -> tuple[str, ...]:
        reasons = [
            f"weighted score {score} (TIER_1 floor {pack.tier1_floor}, "
            f"TIER_2 floor {pack.tier2_floor}) places the model at {scored_tier.value}"
        ]
        for dim in breakdown:
            if dim.failsafe:
                reasons.append(
                    f"{dim.dimension} undeclared, scored at the {FAILSAFE_LEVEL.value} failsafe"
                )
        if capital:
            reasons.append(
                f"{record.model_class.value} feeds regulatory capital or provisioning, "
                "so it floors at tier_1 regardless of score"
            )
        return tuple(reasons)

    @staticmethod
    def _findings(
        record: InventoryRecord, breakdown: tuple[DimensionScore, ...], capital: bool
    ) -> tuple[Finding, ...]:
        out: list[Finding] = []
        for dim in breakdown:
            if dim.failsafe:
                out.append(
                    Finding(
                        id=f"tiering:failsafe:{dim.dimension}",
                        severity=Severity.MEDIUM,
                        summary=f"{dim.dimension} undeclared; used the onerous failsafe level",
                        detail="Declare the dimension to replace the failsafe with an assessment.",
                        citations=(record.citation(),),
                    )
                )
        return tuple(sorted(out, key=lambda f: f.sort_key))
