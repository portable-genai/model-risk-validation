"""The quantitative model-risk taxonomy this vertical reasons over (pure stdlib).

The nouns of the domain: the CLASSES of quantitative model the second line governs, the TIER a
model lands in, and the LEVEL vocabulary the tiering dimensions are declared in. Kept apart from
``kernel.py`` (which is vertical-neutral) because a fork building a different vertical rewrites
this file and leaves the kernel untouched.

Every taxonomy member IS its wire value (``LenientStrEnum``), so a serialised record round-trips
without a translation table and an unknown string fails closed rather than silently mapping.
"""

from __future__ import annotations

from hex_service_kit.enums import LenientStrEnum


class ModelClass(LenientStrEnum):
    """The quantitative model families in scope (SR 11-7 / PRA SS1/23 / MAS / APRA lens)."""

    SCORECARD = "scorecard"  # application/behavioural credit scorecards
    IFRS9_CECL = "ifrs9_cecl"  # expected-credit-loss provisioning
    IRB = "irb"  # internal-ratings-based regulatory capital (PD/LGD/EAD)
    ALM = "alm"  # asset-liability / interest-rate-risk
    PRICING = "pricing"  # product and derivative pricing
    ACTUARIAL = "actuarial"  # insurance reserving and pricing
    AML_SCENARIO = "aml_scenario"  # transaction-monitoring scenario models


class Tier(LenientStrEnum):
    """Materiality tier. TIER_1 is the highest materiality and the closest supervision.

    Ordered so a numeric rank exists (:func:`tier_rank`); the fail-closed default when an input
    is missing or unknown is always the MORE onerous tier, never the lighter one.
    """

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class Level(LenientStrEnum):
    """The ordinal level a tiering dimension is declared at."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#: The four tiering dimensions, scored per model class by a pack. Order is the reporting order.
DIMENSIONS: tuple[str, ...] = (
    "materiality",
    "complexity",
    "usage",
    "regulatory_exposure",
)

#: Points a declared level contributes before the pack weights it. HIGH is worst.
_LEVEL_POINTS: dict[Level, int] = {Level.LOW: 1, Level.MEDIUM: 2, Level.HIGH: 3}

#: The fail-closed level for a dimension that is missing, unparseable or unknown. A model whose
#: materiality nobody declared is treated as the MOST material, so an omission raises the tier
#: rather than lowering it. Absence of evidence is never evidence of low risk.
FAILSAFE_LEVEL: Level = Level.HIGH

#: Numeric rank per tier, higher is more onerous, so "the higher of two tiers" is a ``max``.
_TIER_RANK: dict[Tier, int] = {Tier.TIER_3: 0, Tier.TIER_2: 1, Tier.TIER_1: 2}


def level_points(level: Level) -> int:
    """The raw points a level contributes (LOW 1, MEDIUM 2, HIGH 3)."""
    return _LEVEL_POINTS[level]


def tier_rank(tier: Tier) -> int:
    """The onerousness rank of a tier: TIER_1 is 2, TIER_3 is 0."""
    return _TIER_RANK[tier]


def higher_tier(left: Tier, right: Tier) -> Tier:
    """The more onerous of two tiers (fail closed: ties and unknowns resolve upward)."""
    return left if tier_rank(left) >= tier_rank(right) else right


def coerce_level(raw: object) -> Level | None:
    """Parse a declared level, returning ``None`` for anything not an exact known member.

    ``None`` is the caller's signal to substitute :data:`FAILSAFE_LEVEL` AND to record a gap:
    the engine must never silently treat an undeclared dimension as LOW.
    """
    if isinstance(raw, Level):
        return raw
    if isinstance(raw, str):
        try:
            return Level(raw)
        except ValueError:
            return None
    return None
