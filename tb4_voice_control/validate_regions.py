"""Standalone semantic-region validation without ROS or a graphical display."""

import argparse
from pathlib import Path
import sys

from tb4_voice_control.map_model import load_occupancy_map
from tb4_voice_control.region_validation import validate_semantic_map
from tb4_voice_control.regions import load_regions
import yaml


def main(argv=None) -> int:
    """Print all issues and return 2 for an invalid file, or 0 for valid regions."""
    parser = argparse.ArgumentParser(description='Validate semantic map regions')
    parser.add_argument('regions', type=Path, help='Versioned regions YAML file')
    arguments = parser.parse_args(argv)
    try:
        document = load_regions(arguments.regions)
        occupancy = load_occupancy_map(document.map_yaml)
        issues = validate_semantic_map(document, occupancy)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f'invalid_file: {exc}', file=sys.stderr)
        return 2
    for issue in issues:
        print(f'{issue.code} [{issue.region_id or "document"}]: {issue.message}')
    if issues:
        return 2
    print(f'{len(document.regions)} valid regions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
