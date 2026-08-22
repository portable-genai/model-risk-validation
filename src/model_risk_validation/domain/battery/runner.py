"""The battery runner (slice 3): compute each required statistic and verdict against its bar.

The runner reads the model class's :class:`~..packs.BatteryPack`, computes every required
statistic from the supplied samples with the pure functions in :mod:`.stats`, and returns a
pass/fail per test plus a gap where a required input was not supplied. A missing input is a named
GAP, never a pass: a test that cannot be run has not been passed, and the overall battery does
not go GREEN while a required test is missing its data.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ..kernel import Citation, Finding, Severity
from ..packs import BatteryPack, TestBar, battery_pack
from ..taxonomy import ModelClass
from .stats import StatInputError, auc, calibration_error, exception_rate, gini, psi


@dataclass(frozen=True, slots=True)
class BatterySample:
    """The raw samples a model's validation tests are computed over (any subset may be present).

    Each field feeds specific metrics; a metric whose inputs are absent becomes a gap, so a
    caller supplies exactly what the model class's pack requires and the runner reports the rest.
    """

    scores: Sequence[float] | None = None  # discrimination: model output per obligor
    labels: Sequence[int] | None = None  # discrimination: realised 0/1 outcome
    predicted: Sequence[float] | None = None  # calibration: predicted probability
    outcomes: Sequence[int] | None = None  # calibration: realised 0/1 outcome
    psi_expected: Sequence[float] | None = None  # stability: development distribution
    psi_actual: Sequence[float] | None = None  # stability: current distribution
    exceptions: Sequence[int] | None = None  # backtesting: 0/1 breach series


@dataclass(frozen=True, slots=True)
class TestOutcome:
    """One validation test's computed statistic and its verdict against the pack bar."""

    metric: str
    value: float
    bar: float
    higher_is_better: bool
    passed: bool


@dataclass(frozen=True, slots=True)
class BatteryReport:
    """The full battery outcome for one model: every test, plus gaps for missing inputs."""

    model_id: str
    model_class: ModelClass
    outcomes: tuple[TestOutcome, ...]
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def failed(self) -> tuple[TestOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.passed)

    @property
    def has_gap(self) -> bool:
        return any(f.id.startswith("battery:gap:") for f in self.findings)

    @property
    def passed(self) -> bool:
        """GREEN only when every required test ran AND cleared its bar. A gap is not a pass."""
        return not self.failed and not self.has_gap


class BatteryRunner:
    """Compute a model class's required validation tests from supplied samples. Pure."""

    def run(self, model_id: str, model_class: ModelClass, sample: BatterySample) -> BatteryReport:
        pack = battery_pack(model_class)
        outcomes: list[TestOutcome] = []
        findings: list[Finding] = []
        for bar in pack.bars:
            self._one(model_id, bar, sample, outcomes, findings, pack)
        return BatteryReport(
            model_id=model_id,
            model_class=model_class,
            outcomes=tuple(outcomes),
            findings=tuple(sorted(findings, key=lambda f: f.sort_key)),
        )

    def _one(
        self,
        model_id: str,
        bar: TestBar,
        sample: BatterySample,
        outcomes: list[TestOutcome],
        findings: list[Finding],
        pack: BatteryPack,
    ) -> None:
        computer = self._COMPUTERS[bar.metric]
        try:
            value = computer(sample)
        except _MissingInput as exc:
            findings.append(
                Finding(
                    id=f"battery:gap:{bar.metric}",
                    severity=Severity.HIGH,
                    summary=f"Required test {bar.metric} could not run: {exc}",
                    detail="A missing input is a gap, not a pass; supply the sample.",
                    citations=(_metric_citation(model_id, bar.metric),),
                )
            )
            return
        outcome = TestOutcome(
            metric=bar.metric,
            value=round(value, 6),
            bar=bar.bar,
            higher_is_better=bar.higher_is_better,
            passed=bar.passes(value),
        )
        outcomes.append(outcome)
        if not outcome.passed:
            findings.append(
                Finding(
                    id=f"battery:fail:{bar.metric}",
                    severity=Severity.HIGH,
                    summary=f"{bar.metric} {outcome.value} does not clear the bar {bar.bar}",
                    detail=f"{'higher' if bar.higher_is_better else 'lower'} is better here.",
                    citations=(_metric_citation(model_id, bar.metric),),
                )
            )

    # metric -> a function from the sample to the statistic, raising _MissingInput when absent.
    _COMPUTERS: dict[str, Callable[[BatterySample], float]]


class _MissingInput(StatInputError):
    """A required sample field for a metric was not supplied."""


def _metric_citation(model_id: str, metric: str) -> Citation:
    return Citation(
        source_id=f"battery:{model_id}:{metric}",
        title=f"Validation test {metric}",
        snippet=f"model {model_id}",
    )


def _require(value: object, name: str) -> None:
    if value is None:
        raise _MissingInput(f"sample.{name} was not supplied")


def _auc(sample: BatterySample) -> float:
    _require(sample.scores, "scores")
    _require(sample.labels, "labels")
    assert sample.scores is not None and sample.labels is not None
    return auc(sample.scores, sample.labels)


def _gini(sample: BatterySample) -> float:
    _require(sample.scores, "scores")
    _require(sample.labels, "labels")
    assert sample.scores is not None and sample.labels is not None
    return gini(sample.scores, sample.labels)


def _calibration(sample: BatterySample) -> float:
    _require(sample.predicted, "predicted")
    _require(sample.outcomes, "outcomes")
    assert sample.predicted is not None and sample.outcomes is not None
    return calibration_error(sample.predicted, sample.outcomes)


def _psi(sample: BatterySample) -> float:
    _require(sample.psi_expected, "psi_expected")
    _require(sample.psi_actual, "psi_actual")
    assert sample.psi_expected is not None and sample.psi_actual is not None
    return psi(sample.psi_expected, sample.psi_actual)


def _exception_rate(sample: BatterySample) -> float:
    _require(sample.exceptions, "exceptions")
    assert sample.exceptions is not None
    return exception_rate(sample.exceptions)


BatteryRunner._COMPUTERS = {
    "auc": _auc,
    "gini": _gini,
    "calibration_error": _calibration,
    "psi": _psi,
    "exception_rate": _exception_rate,
}
