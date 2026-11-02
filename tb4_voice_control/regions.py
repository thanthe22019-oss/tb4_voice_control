"""Versioned, UI-independent semantic regions and atomic YAML persistence."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import tempfile
import unicodedata

import yaml


@dataclass(frozen=True)
class GoalPose:
    """A planar navigation goal in the semantic map's ROS frame."""

    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class Region:
    """A named pixel polygon, canonical aliases, and its navigation goal."""

    id: str  # noqa: A003 - public schema field
    name: str
    aliases: tuple[str, ...]
    color: tuple[int, int, int]
    polygon_pixels: tuple[tuple[float, float], ...]
    goal: GoalPose


@dataclass(frozen=True)
class SemanticMap:
    """A versioned semantic document with a resolved occupancy metadata path."""

    schema_version: int
    map_yaml: Path
    frame_id: str
    regions: tuple[Region, ...]


def normalize_alias(alias: str) -> str:
    """Fold Vietnamese accents, case, punctuation, and whitespace for lookup."""
    decomposed = unicodedata.normalize('NFKD', alias.casefold().replace('đ', 'd'))
    text = ''.join(character for character in decomposed
                   if not unicodedata.combining(character))
    return ' '.join(''.join(character if character.isalnum() else ' '
                            for character in text).split())


def _mapping(value, field):
    if not isinstance(value, dict):
        raise ValueError(f'{field} must be a mapping')
    return value


def _sequence(value, field):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{field} must be a sequence')
    return value


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty string')
    return value


def _finite(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{field} must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{field} must be a finite number')


def _validate_structure(document: SemanticMap) -> None:
    """Check schema constraints for loaded or programmatically edited documents."""
    if type(document.schema_version) is not int or document.schema_version != 1:
        raise ValueError('schema_version must be 1')
    if not isinstance(document.map_yaml, Path):
        raise ValueError('map.yaml must be a path')
    _text(document.frame_id, 'map.frame_id')
    ids = set()
    for region in _sequence(document.regions, 'regions'):
        identifier = _text(region.id, 'region.id')
        if identifier in ids:
            raise ValueError(f'duplicate region id: {identifier}')
        ids.add(identifier)
        _text(region.name, f'{identifier}.name')
        for alias in _sequence(region.aliases, f'{identifier}.aliases'):
            if not normalize_alias(_text(alias, f'{identifier}.aliases')):
                raise ValueError(f'{identifier}.aliases must contain words or letters')
        color = _sequence(region.color, f'{identifier}.color')
        if len(color) != 3 or any(type(channel) is not int or not 0 <= channel <= 255
                                  for channel in color):
            raise ValueError(f'{identifier}.color must contain three integers in 0..255')
        polygon = _sequence(region.polygon_pixels, f'{identifier}.polygon_pixels')
        if len(polygon) < 3:
            raise ValueError(f'{identifier}.polygon_pixels needs at least three vertices')
        for point in polygon:
            if len(_sequence(point, f'{identifier}.polygon_pixels')) != 2:
                raise ValueError(f'{identifier}.polygon_pixels vertices need x and y')
            for coordinate in point:
                _finite(coordinate, f'{identifier}.polygon_pixels')
        for field in ('x', 'y', 'yaw'):
            _finite(getattr(region.goal, field), f'{identifier}.goal.{field}')


def load_regions(path: Path) -> SemanticMap:
    """Load schema version 1 and resolve its map YAML relative to this document."""
    path = Path(path).resolve()
    try:
        with path.open(encoding='utf-8') as stream:
            data = _mapping(yaml.safe_load(stream), 'document')
    except yaml.YAMLError as exc:
        raise ValueError(f'invalid regions YAML: {exc}') from exc
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('schema_version must be 1')
    map_data = _mapping(data.get('map'), 'map')
    map_name = _text(map_data.get('yaml'), 'map.yaml')
    regions = []
    for item in _sequence(data.get('regions'), 'regions'):
        item = _mapping(item, 'region')
        goal = _mapping(item.get('goal'), 'region.goal')
        polygon = _sequence(item.get('polygon_pixels'), 'region.polygon_pixels')
        regions.append(Region(
            item.get('id'), item.get('name'),
            tuple(_sequence(item.get('aliases'), 'region.aliases')),
            tuple(_sequence(item.get('color'), 'region.color')),
            tuple(tuple(_sequence(point, 'region.polygon_pixels')) for point in polygon),
            GoalPose(goal.get('x'), goal.get('y'), goal.get('yaw'))))
    document = SemanticMap(data['schema_version'], (path.parent / map_name).resolve(),
                           map_data.get('frame_id'), tuple(regions))
    _validate_structure(document)
    return document


def save_regions(path: Path, document: SemanticMap) -> None:
    """Replace the destination with complete UTF-8 YAML using a sibling temporary file."""
    _validate_structure(document)
    path = Path(path).resolve()
    data = {
        'schema_version': document.schema_version,
        'map': {'yaml': os.path.relpath(document.map_yaml, path.parent),
                'frame_id': document.frame_id},
        'regions': [{
            'id': region.id, 'name': region.name, 'aliases': list(region.aliases),
            'color': list(region.color),
            'polygon_pixels': [list(point) for point in region.polygon_pixels],
            'goal': {'x': region.goal.x, 'y': region.goal.y, 'yaw': region.goal.yaw},
        } for region in document.regions],
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
