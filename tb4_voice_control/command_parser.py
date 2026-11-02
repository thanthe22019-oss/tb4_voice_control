"""Deterministic Vietnamese grammar and semantic region alias lookup."""

from dataclasses import dataclass
from enum import Enum
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
            if position == len(tokens):
                raise CommandError('missing_destination',
                                   'Missing destination after connector')
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


def _parse_from_to(tokens: list[str], aliases: dict[str, str]) -> VoiceCommand:
    """Accept exactly one complete source/destination separator reading."""
    interpretations = []
    errors = []
    for index in range(1, len(tokens)):
        if tokens[index] not in ('den', 'toi'):
            continue
        source = ' '.join(tokens[:index])
        if source not in aliases:
            continue
        try:
            destination = _resolve_destination(' '.join(tokens[index + 1:]),
                                               aliases)
        except CommandError as error:
            errors.append(error)
            continue
        interpretations.append(VoiceCommand(Intent.FROM_TO,
                                            aliases[source], destination))
    if len(interpretations) > 1:
        raise CommandError('ambiguous_command',
                           'Multiple complete source/destination readings')
    if interpretations:
        return interpretations[0]
    for code in ('missing_destination', 'ambiguous_destination'):
        for error in errors:
            if error.code == code:
                raise error
    raise CommandError('unknown_region', 'Unknown source or destination region')


def parse_command(text: str, semantic_map: SemanticMap) -> VoiceCommand:
    """Parse move-to or move-from-to commands without substring guessing."""
    aliases = _alias_index(semantic_map)
    tokens = normalize_text(text, strip_diacritics=True).split()
    if not tokens or tokens[0] != 'di':
        raise CommandError('invalid_command', 'Unsupported navigation command')
    tokens = tokens[2:] if len(tokens) > 1 and tokens[1] == 'chuyen' else tokens[1:]
    if tokens and tokens[0] == 'tu':
        return _parse_from_to(tokens[1:], aliases)
    if not tokens or tokens[0] not in ('den', 'toi'):
        raise CommandError('invalid_command', 'Unsupported navigation command')
    destination = _resolve_destination(' '.join(tokens[1:]), aliases)
    return VoiceCommand(Intent.GO_TO, None, destination)
