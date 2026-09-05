"""Day 17: judge calibration.

Hand-labeled examples (harness/calibration_dataset.py) are the ground
truth for whether the LLM-judge is trustworthy. calibrate() runs the
judge against each labeled example and reports the agreement rate
between the judge's verdict and the human label — not whether the judge
agrees with some other AI's opinion.

CALIBRATION_THRESHOLD and is_calibrated() encode the project's own
policy from docs/PLAN.md: if agreement is low, iterate on the rubric
(or the dataset, or the judge's prompt) before trusting the judge for
anything — including, per day 23, ever using it as a CI gate, which it
never becomes regardless of how well-calibrated it gets.

Run this module directly to calibrate the real judge against a real
model (requires ANTHROPIC_API_KEY and the anthropic package):

    python -m harness.calibration
"""

from dataclasses import dataclass, field

from harness.calibration_dataset import CALIBRATION_SET, LabeledExample
from harness.llm_judge import LLMJudgeEvaluator

CALIBRATION_THRESHOLD = 0.8


@dataclass(frozen=True)
class CalibrationResult:
    total: int
    agreements: int
    disagreements: list[str] = field(default_factory=list)

    @property
    def agreement_rate(self) -> float:
        return self.agreements / self.total if self.total else 0.0


def calibrate(examples: list[LabeledExample], judge: LLMJudgeEvaluator) -> CalibrationResult:
    agreements = 0
    disagreements = []

    for example in examples:
        outcome = judge.evaluate(example.scenario, example.result)
        if outcome.passed == example.human_label:
            agreements += 1
        else:
            disagreements.append(example.name)

    return CalibrationResult(total=len(examples), agreements=agreements, disagreements=disagreements)


def is_calibrated(result: CalibrationResult, threshold: float = CALIBRATION_THRESHOLD) -> bool:
    return result.agreement_rate >= threshold


def _print_report(result: CalibrationResult) -> None:
    print(f"Agreement: {result.agreements}/{result.total} ({result.agreement_rate:.0%})")
    if result.disagreements:
        print("Disagreements:")
        for name in result.disagreements:
            print(f"  - {name}")
    status = "CALIBRATED" if is_calibrated(result) else "NOT CALIBRATED"
    print(f"[{status}] (threshold: {CALIBRATION_THRESHOLD:.0%})")


if __name__ == "__main__":
    real_judge = LLMJudgeEvaluator()
    _print_report(calibrate(CALIBRATION_SET, real_judge))
