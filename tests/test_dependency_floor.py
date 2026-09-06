"""The environment running the suite must satisfy the declared dependencies.

Without this, the suite can pass against a version the package does not claim to
support — which happened here: `pydantic-ai-slim>=2.40` was declared while 1.107
was installed, so every result described a version that would never ship.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

import pytest


PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _declared() -> list[str]:
    if sys.version_info < (3, 11):
        return []
    import tomllib

    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]


DEPENDENCIES = _declared()


@pytest.mark.skipif(not DEPENDENCIES, reason="reading pyproject.toml needs Python 3.11")
@pytest.mark.parametrize("dependency", DEPENDENCIES)
def test_installed_version_satisfies_pyproject(dependency: str) -> None:
    packaging = pytest.importorskip("packaging.requirements")
    requirement = packaging.Requirement(dependency)
    try:
        installed = version(requirement.name)
    except PackageNotFoundError:
        pytest.fail(f"{requirement.name} is declared in pyproject.toml but not installed")
    assert requirement.specifier.contains(installed, prereleases=True), (
        f"{requirement.name} {installed} does not satisfy the declared "
        f"{requirement.specifier}; the suite would be testing a version "
        f"AtBots does not ship"
    )
