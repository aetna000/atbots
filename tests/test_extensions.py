from pathlib import Path

import pytest

from atbots.extensions import load_object


def test_load_object_from_python_file(tmp_path: Path) -> None:
    source = tmp_path / "policy.py"
    source.write_text("configured = {'name': 'safe'}\n", encoding="utf-8")
    assert load_object(f"{source}:configured") == {"name": "safe"}


def test_load_object_rejects_invalid_reference() -> None:
    with pytest.raises(ValueError, match="expected module:object"):
        load_object("missing-separator")


def test_load_native_pydantic_capability(tmp_path: Path) -> None:
    pytest.importorskip("pydantic_ai")
    from atbots.extensions import load_pydantic_capabilities

    source = tmp_path / "rules.py"
    source.write_text(
        "from pydantic_ai.capabilities import Capability\n"
        "rules = Capability(id='test-rules', instructions='Be accurate.')\n",
        encoding="utf-8",
    )
    loaded = load_pydantic_capabilities([f"{source}:rules"])
    assert len(loaded) == 1
    assert loaded[0].id == "test-rules"
