"""The tiering engine: bands, the regulatory-capital floor, and fail-closed on omissions."""

from __future__ import annotations

from model_risk_validation.domain.inventory import InventoryRecord
from model_risk_validation.domain.taxonomy import ModelClass, Tier
from model_risk_validation.domain.tiering import TieringEngine


def _record(model_class: ModelClass, **dims: str) -> InventoryRecord:
    return InventoryRecord(
        model_id="M-1",
        name="Test (FICTIONAL)",
        model_class=model_class,
        owner="owner@bank.example",
        dimensions=dims,
    )


def _tier(model_class: ModelClass, **dims: str) -> Tier:
    return TieringEngine().assess(_record(model_class, **dims)).tier


def test_all_low_dimensions_land_in_the_lowest_tier() -> None:
    assert (
        _tier(
            ModelClass.PRICING,
            materiality="low",
            complexity="low",
            usage="low",
            regulatory_exposure="low",
        )
        is Tier.TIER_3
    )


def test_all_high_dimensions_land_in_the_top_tier() -> None:
    assert (
        _tier(
            ModelClass.SCORECARD,
            materiality="high",
            complexity="high",
            usage="high",
            regulatory_exposure="high",
        )
        is Tier.TIER_1
    )


def test_medium_dimensions_land_in_the_middle_tier() -> None:
    assert (
        _tier(
            ModelClass.ALM,
            materiality="medium",
            complexity="medium",
            usage="medium",
            regulatory_exposure="medium",
        )
        is Tier.TIER_2
    )


def test_a_regulatory_capital_class_floors_at_tier_1_even_with_all_low_dimensions() -> None:
    assessment = TieringEngine().assess(
        _record(
            ModelClass.IRB,
            materiality="low",
            complexity="low",
            usage="low",
            regulatory_exposure="low",
        )
    )
    assert assessment.tier is Tier.TIER_1
    assert assessment.capital_override is True


def test_an_undeclared_dimension_fails_closed_upward_and_is_recorded() -> None:
    # Same scorecard, but with materiality omitted: the failsafe raises the score and the reason
    # is attributable to the omission rather than to a genuine high-materiality reading.
    declared = TieringEngine().assess(
        _record(
            ModelClass.SCORECARD,
            materiality="low",
            complexity="low",
            usage="low",
            regulatory_exposure="low",
        )
    )
    omitted = TieringEngine().assess(
        _record(ModelClass.SCORECARD, complexity="low", usage="low", regulatory_exposure="low")
    )
    assert omitted.score > declared.score
    assert "materiality" in omitted.failsafe_dimensions
    assert any(f.id == "tiering:failsafe:materiality" for f in omitted.findings)


def test_the_assessment_is_deterministic() -> None:
    record = _record(ModelClass.IRB)
    first = TieringEngine().assess(record)
    second = TieringEngine().assess(record)
    assert (first.tier, first.score) == (second.tier, second.score)
