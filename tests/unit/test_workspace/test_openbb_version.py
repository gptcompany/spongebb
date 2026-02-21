"""Test OpenBB version compatibility.

Catches version drift and import breakage early before production deployment.
"""

import importlib
import importlib.metadata
import shutil

import pytest


def test_openbb_version_in_range():
    """OpenBB SDK version is within the pinned range [4.4.0, 4.7.0)."""
    try:
        meta_version = importlib.metadata.version("openbb")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("openbb package not installed")

    from packaging.version import Version

    v = Version(meta_version)
    assert v >= Version("4.4.0"), f"OpenBB {v} below minimum 4.4.0"
    assert v < Version("4.7.0"), f"OpenBB {v} above maximum 4.7.0"


def test_openbb_platform_api_importable():
    """openbb_platform_api package is importable (provides openbb-api CLI)."""
    try:
        import openbb_platform_api  # noqa: F401
    except ImportError:
        pytest.fail("openbb_platform_api not importable — openbb-api CLI unavailable")


def test_openbb_core_importable():
    """openbb_core package is importable (foundation of OpenBB SDK)."""
    try:
        import openbb_core  # noqa: F401
    except ImportError:
        pytest.fail("openbb_core not importable — OpenBB SDK broken")


def test_openbb_api_cli_exists():
    """openbb-api CLI entry point is installed and on PATH."""
    path = shutil.which("openbb-api")
    assert path is not None, (
        "openbb-api CLI not found on PATH — install openbb-platform-api"
    )
