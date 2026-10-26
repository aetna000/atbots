from atbots import __version__


def test_package_version() -> None:
    assert __version__ == "0.3.0b2"
