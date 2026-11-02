"""Qt-independent semantic document with bounded, region-sized undo commands."""

from dataclasses import dataclass, replace

from tb4_voice_control.map_model import OccupancyMap
from tb4_voice_control.region_validation import validate_semantic_map
from tb4_voice_control.regions import _validate_structure, Region, SemanticMap


@dataclass(frozen=True)
class _RegionCommand:
    before: Region | None
    after: Region | None
    index: int
    before_revision: int
    after_revision: int


class EditorDocument:
    """Replace frozen models on edits; keep view and selection out of persistence."""

    def __init__(self, semantic_map: SemanticMap):
        """Start with a clean semantic document and empty history."""
        _validate_structure(semantic_map)
        self.semantic_map = semantic_map
        self.selected_region_id = None
        self._commands = []
        self._cursor = 0
        self._revision = 0
        self._next_revision = 1
        self._saved_revision = 0

    @property
    def selected_region(self) -> Region | None:
        """Resolve selection by stable ID after model replacement."""
        return next((region for region in self.semantic_map.regions
                     if region.id == self.selected_region_id), None)

    @property
    def is_dirty(self) -> bool:
        """Whether the current command state differs from the saved state."""
        return self._revision != self._saved_revision

    @property
    def can_undo(self) -> bool:
        """Whether an older retained command can be reversed."""
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        """Whether an undone command remains on this edit branch."""
        return self._cursor < len(self._commands)

    def mark_saved(self):
        """Mark the current state clean after successful persistence."""
        self._saved_revision = self._revision

    def _index(self, identifier):
        for index, region in enumerate(self.semantic_map.regions):
            if region.id == identifier:
                return index
        raise KeyError(identifier)

    def select_region(self, identifier: str | None):
        """Select an existing region or clear selection without dirtying."""
        if identifier is not None:
            self._index(identifier)
        self.selected_region_id = identifier

    def _replace_region(self, index, before, after):
        regions = list(self.semantic_map.regions)
        if before is None:
            regions.insert(index, after)
        elif after is None:
            del regions[index]
        else:
            regions[index] = after
        updated = replace(self.semantic_map, regions=tuple(regions))
        _validate_structure(updated)
        self.semantic_map = updated
        if (self.selected_region_id is not None
                and not any(region.id == self.selected_region_id for region in regions)):
            self.selected_region_id = None

    def _edit(self, index, before, after):
        if before == after:
            return
        self._replace_region(index, before, after)
        command = _RegionCommand(before, after, index,
                                 self._revision, self._next_revision)
        self._commands[self._cursor:] = [command]
        self._commands = self._commands[-100:]
        self._cursor = len(self._commands)
        self._revision = self._next_revision
        self._next_revision += 1

    def add_region(self, region: Region):
        """Append a structurally valid region with a unique ID."""
        self._edit(len(self.semantic_map.regions), None, region)

    def update_region(self, region: Region):
        """Replace a region while keeping its ID and document position."""
        index = self._index(region.id)
        self._edit(index, self.semantic_map.regions[index], region)

    def delete_region(self, identifier: str):
        """Remove one region, retaining its old position for undo."""
        index = self._index(identifier)
        self._edit(index, self.semantic_map.regions[index], None)

    def undo(self) -> bool:
        """Reverse one command, returning false at the retained history limit."""
        if not self.can_undo:
            return False
        command = self._commands[self._cursor - 1]
        self._replace_region(command.index, command.after, command.before)
        self._cursor -= 1
        self._revision = command.before_revision
        return True

    def redo(self) -> bool:
        """Reapply one undone command, returning false if none remains."""
        if not self.can_redo:
            return False
        command = self._commands[self._cursor]
        self._replace_region(command.index, command.before, command.after)
        self._cursor += 1
        self._revision = command.after_revision
        return True

    def validate(self, occupancy: OccupancyMap):
        """Collect geometry issues without preventing intermediate edits."""
        return validate_semantic_map(self.semantic_map, occupancy)
