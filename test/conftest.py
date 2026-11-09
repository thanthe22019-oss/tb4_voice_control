"""Make the checkout importable for pytest and preserve ROS import paths."""

import os
from pathlib import Path
import sys


# Qt tests must also be safe under ``colcon test`` on a headless runner.  Keep
# an explicitly selected platform, but make offscreen the deterministic test
# default before any test module imports PyQt5.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_addoption(parser):
    """Keep portable ROS tests separate from mandatory speech SDK acceptance."""
    parser.addoption('--run-speech-sdk', action='store_true', default=False,
                     help='run offline speech acceptance with google-genai 2.33.x')
