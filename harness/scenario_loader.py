"""Load ScenarioSpec objects from YAML files on disk."""

from pathlib import Path

import yaml

from harness.schema import ScenarioSpec


def load_scenario(path: Path) -> ScenarioSpec:
    with path.open() as f:
        data = yaml.safe_load(f)
    return ScenarioSpec.model_validate(data)


def load_scenarios(directory: Path) -> list[ScenarioSpec]:
    return [load_scenario(p) for p in sorted(directory.glob("*.yaml"))]
