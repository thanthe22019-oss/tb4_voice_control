"""Vietnamese command grammar and unambiguous semantic alias resolution."""

from pathlib import Path

import pytest

from tb4_voice_control.command_parser import (
    CommandError, Intent, normalize_text, parse_command,
)
from tb4_voice_control.regions import GoalPose, Region, SemanticMap


def semantic_map(*extra):
    """Provide short and long aliases for two distinct destinations."""
    b_aliases = ('B', 'khu B', 'khu vực B', 'phòng thí nghiệm')
    regions = (
        Region('zone_a', 'Khu vực A', ('A', 'khu vực A'), (1, 2, 3),
               ((0, 0), (1, 0), (1, 1)), GoalPose(0, 0, 0)),
        Region('zone_b', 'Khu vực B', b_aliases,
               (4, 5, 6), ((2, 0), (3, 0), (3, 1)), GoalPose(2, 0, 0)),
    )
    return SemanticMap(1, Path('map.yaml'), 'map', regions + extra)


@pytest.mark.parametrize('utterance,destination', [
    ('Đi đến khu vực A.', 'zone_a'),
    ('di chuyen toi khu b', 'zone_b'),
    ('  ĐI   ĐẾN  PHÒNG  THÍ   NGHIỆM!!! ', 'zone_b'),
    ('đi đến phòng thí nghiệm', 'zone_b'),
])
def test_go_to_grammar_and_normalized_aliases(utterance, destination):
    """Spoken accent, case, Unicode form, and spacing variations resolve."""
    command = parse_command(utterance, semantic_map())
    assert command.intent is Intent.GO_TO
    assert command.source_id is None
    assert command.destination_id == destination


def test_from_to_grammar():
    """Source and destination spans are resolved independently."""
    command = parse_command('Di chuyển từ A đến B', semantic_map())
    assert (command.intent, command.source_id, command.destination_id) == (
        Intent.FROM_TO, 'zone_a', 'zone_b')


def test_source_alias_containing_folded_connector_word():
    """A folded đèn inside the full source alias is not the separator."""
    room = Region('lamp_room', 'Phòng đèn', ('phòng đèn',), (7, 8, 9),
                  ((4, 0), (5, 0), (5, 1)), GoalPose(4, 0, 0))
    command = parse_command('đi từ phòng đèn đến B', semantic_map(room))
    assert (command.intent, command.source_id, command.destination_id) == (
        Intent.FROM_TO, 'lamp_room', 'zone_b')


def test_multiple_complete_from_to_interpretations_are_ambiguous():
    """A separator in a source or destination alias cannot force a guess."""
    long_source = Region('long_source', 'Long source', ('A đến B',),
                         (7, 8, 9), ((4, 0), (5, 0), (5, 1)),
                         GoalPose(4, 0, 0))
    long_destination = Region('long_destination', 'Long destination',
                              ('B đến C',), (10, 11, 12),
                              ((6, 0), (7, 0), (7, 1)), GoalPose(6, 0, 0))
    c = Region('zone_c', 'C', ('C',), (13, 14, 15),
               ((8, 0), (9, 0), (9, 1)), GoalPose(8, 0, 0))
    with pytest.raises(CommandError) as error:
        parse_command('đi từ A đến B đến C',
                      semantic_map(long_source, long_destination, c))
    assert error.value.code == 'ambiguous_command'


def test_normalization_preserves_or_folds_vietnamese_diacritics():
    """Optional accent folding uses the persisted alias key."""
    phrase = '  PHÒNG---Thí  nghiệm! '
    assert normalize_text(phrase) == 'phòng thí nghiệm'
    assert normalize_text(phrase, True) == 'phong thi nghiem'
    assert normalize_text('ĐI ĐẾN', True) == 'di den'


def test_longest_alias_consumes_the_full_destination():
    """A long alias wins before its embedded short alias can be considered."""
    extra = Region('zone_lab', 'Laboratory', ('thí nghiệm',), (7, 8, 9),
                   ((4, 0), (5, 0), (5, 1)), GoalPose(4, 0, 0))
    assert parse_command('đi đến phòng thí nghiệm',
                         semantic_map(extra)).destination_id == 'zone_b'


@pytest.mark.parametrize('utterance,code', [
    ('đi đến bản đồ', 'unknown_region'),
    ('đi đến X', 'unknown_region'),
    ('đi đến', 'missing_destination'),
    ('di chuyển từ A đến', 'missing_destination'),
    ('đi đến A và B', 'ambiguous_destination'),
    ('đi đến A hoặc B', 'ambiguous_destination'),
    ('đi đến A đến B', 'ambiguous_destination'),
    ('đi đến A hoặc', 'missing_destination'),
    ('đi đến A đến', 'missing_destination'),
    ('đi từ A đến B hoặc', 'missing_destination'),
    ('đi đến khu vực A B', 'ambiguous_destination'),
    ('đi từ X đến B', 'unknown_region'),
])
def test_bad_commands_have_stable_codes(utterance, code):
    """A short A alias never silently matches text in an unresolved span."""
    with pytest.raises(CommandError) as error:
        parse_command(utterance, semantic_map())
    assert error.value.code == code


def test_duplicate_normalized_alias_is_rejected():
    """One normalized key cannot silently identify two regions."""
    other = Region('zone_other', 'Other', ('KHU VUC A!',), (7, 8, 9),
                   ((4, 0), (5, 0), (5, 1)), GoalPose(4, 0, 0))
    with pytest.raises(CommandError) as error:
        parse_command('đi đến A', semantic_map(other))
    assert error.value.code == 'duplicate_alias'
