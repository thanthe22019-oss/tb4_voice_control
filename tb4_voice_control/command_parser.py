"""Deterministic Vietnamese grammar and semantic region alias lookup."""

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from tb4_voice_control.regions import normalize_alias, SemanticMap


class Intent(str, Enum):
    """Supported navigation command forms."""

    GO_TO = 'GO_TO'
    FROM_TO = 'FROM_TO'


@dataclass(frozen=True)
class VoiceCommand:
    """Resolved region IDs from one utterance."""

    intent: Intent
    source_id: str | None
    destination_id: str


class CommandError(ValueError):
    """A parse failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        """Attach the stable code to the human-readable failure."""
        super().__init__(message)
        self.code = code


def normalize_text(text: str, strip_diacritics: bool = False) -> str:
    """Normalize speech like region aliases, optionally retaining accents."""
    if strip_diacritics:
        return normalize_alias(text)
    normalized = unicodedata.normalize('NFKC', text).casefold()
    return ' '.join(''.join(character if character.isalnum() else ' '
                            for character in normalized).split())


def _alias_index(semantic_map: SemanticMap) -> dict[str, str]:
    """Reject invalid maps instead of choosing one conflicting alias."""
    aliases = {}
    for region in semantic_map.regions:
        for alias in region.aliases:
            key = normalize_alias(alias)
            if key in aliases:
                raise CommandError('duplicate_alias',
                                   f'Duplicate region alias: {alias}')
            aliases[key] = region.id
    return aliases


def _resolve_destination(span: str, aliases: dict[str, str]) -> str:
    """Cover the entire destination with longest aliases before deciding."""
    if not span:
        raise CommandError('missing_destination', 'Missing destination region')
    if span in aliases:
        return aliases[span]
    tokens = span.split()
    matches = []
    position = 0
    while position < len(tokens):
        if tokens[position] in ('va', 'hoac', 'den', 'toi') and matches:
            position += 1
            continue
        options = sorted(
            (key for key in aliases
             if tokens[position:position + len(key.split())] == key.split()),
            key=lambda key: len(key.split()), reverse=True)
        if not options:
            raise CommandError('unknown_region',
                               f'Unknown destination: {span}')
        alias = options[0]
        matches.append(aliases[alias])
        position += len(alias.split())
    if len(matches) > 1:
        raise CommandError('ambiguous_destination',
                           f'Multiple destinations: {span}')
    return matches[0]


def parse_command(text: str, semantic_map: SemanticMap) -> VoiceCommand:
    """Parse move-to or move-from-to commands without substring guessing."""
    aliases = _alias_index(semantic_map)
    normalized = normalize_text(text, strip_diacritics=True)
    pattern = r'(?:di|di chuyen)(?: tu (.+?))? (?:den|toi)(?: (.*))?'
    match = re.fullmatch(pattern, normalized)
    if match is None:
        raise CommandError('invalid_command', 'Unsupported navigation command')
    source, destination = match.groups()
    destination_id = _resolve_destination(destination or '', aliases)
    if source is None:
        return VoiceCommand(Intent.GO_TO, None, destination_id)
    if source not in aliases:
        raise CommandError('unknown_region', f'Unknown source: {source}')
    return VoiceCommand(Intent.FROM_TO, aliases[source], destination_id)
