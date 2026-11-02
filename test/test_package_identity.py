"""Check the renamed package identity and excluded perception assets."""

from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """Return the checkout containing the package under test."""
    return Path(__file__).resolve().parents[1]


def test_package_files_use_new_identity(project_root):
    """Package metadata and the resource marker use the new identity."""
    assert '<name>tb4_voice_control</name>' in (project_root / 'package.xml').read_text()
    assert "package_name = 'tb4_voice_control'" in (project_root / 'setup.py').read_text()
    assert (project_root / 'resource' / 'tb4_voice_control').is_file()


def test_yolo_assets_are_not_copied(project_root):
    """Perception assets stay outside the navigation baseline."""
    assert not (project_root / 'models').exists()
    assert not (project_root / 'notebooks').exists()
    assert not (project_root / 'requirements-yolo.txt').exists()
