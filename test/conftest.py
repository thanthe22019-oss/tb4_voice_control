"""Make the checkout importable for pytest and preserve ROS import paths."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
