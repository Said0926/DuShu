"""Fixtures for the tts tests."""

from pathlib import Path

import pytest
from django.conf import LazySettings


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, settings: LazySettings) -> Path:
    """Send every file written by a test into its own temporary directory.

    Autouse on purpose: the service writes real files through ``FileField``, and
    without this they would pile up in the project's ``media/`` and leak between
    test runs.
    """
    settings.MEDIA_ROOT = tmp_path
    return tmp_path
