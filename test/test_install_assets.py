"""Verify the install manifest and launch-facing delivery assets."""

from pathlib import Path
import runpy

import pytest

from tb4_voice_control import voice_app


@pytest.fixture
def project_root():
    """Return the repository checkout under test."""
    return Path(__file__).resolve().parents[1]


def _setup_arguments(monkeypatch, project_root):
    captured = {}

    def capture_setup(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('setuptools.setup', capture_setup)
    monkeypatch.chdir(project_root)
    runpy.run_path(str(project_root / 'setup.py'), run_name='__main__')
    return captured


def test_setup_installs_runtime_and_submission_assets(monkeypatch, project_root):
    """Removing any deliverable from the install manifest breaks deployment."""
    arguments = _setup_arguments(monkeypatch, project_root)
    installed = {
        (target, Path(source).as_posix())
        for target, sources in arguments['data_files']
        for source in sources
    }
    required = {
        ('share/tb4_voice_control', 'package.xml'),
        ('share/tb4_voice_control/launch', 'launch/voice_navigation.launch.py'),
        ('share/tb4_voice_control/maps', 'maps/map.yaml'),
        ('share/tb4_voice_control/maps', 'maps/map.pgm'),
        ('share/tb4_voice_control/config', 'config/regions.yaml'),
        ('share/tb4_voice_control/config', 'config/voice.yaml'),
        ('share/tb4_voice_control/artifacts', 'artifacts/segmented_map.png'),
        ('share/tb4_voice_control/scripts', 'scripts/run_voice_control.sh'),
        ('share/tb4_voice_control/docs', 'docs/DEMO.md'),
        ('share/tb4_voice_control/docs', 'docs/TEST_MATRIX.md'),
        ('share/tb4_voice_control/docs/evidence', 'docs/evidence/README.md'),
    }
    assert required <= installed

    console_scripts = set(arguments['entry_points']['console_scripts'])
    assert console_scripts == {
        'navigate_goals = tb4_voice_control.navigate_goals:main',
        'record_goal = tb4_voice_control.goal_recorder:main',
        'validate_regions = tb4_voice_control.validate_regions:main',
        'map_editor = tb4_voice_control.map_editor:main',
        'render_segmented_map = tb4_voice_control.map_render:main',
        'voice_control = tb4_voice_control.voice_app:main',
    }


def test_readme_covers_the_complete_operator_workflow(project_root):
    """Deleting an operator stage leaves the repository unusable as a handoff."""
    readme = (project_root / 'README.md').read_text(encoding='utf-8').casefold()
    for section in (
            'điều kiện tiên quyết', 'build và kiểm thử', 'map editor',
            'nvidia cuda', 'khởi động nav2', 'demo bằng giọng nói',
            'xử lý lỗi', 'cấu trúc repository'):
        assert section in readme


def test_voice_launch_exposes_reuse_and_runtime_switches(
        project_root, monkeypatch, tmp_path):
    """Losing either switch can start duplicate Nav2 or an unwanted voice UI."""
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path / 'ros-log'))
    launch_path = project_root / 'launch' / 'voice_navigation.launch.py'
    assert launch_path.is_file()
    namespace = runpy.run_path(str(launch_path))
    namespace['generate_launch_description'].__globals__[
        'get_package_share_directory'] = lambda _name: str(project_root)
    description = namespace['generate_launch_description']()
    arguments = {
        entity.name: entity
        for entity in description.entities
        if entity.__class__.__name__ == 'DeclareLaunchArgument'
    }
    assert {'start_nav2', 'start_voice_ui', 'regions_file', 'voice_config',
            'use_sim_time'} <= arguments.keys()
    assert arguments['start_nav2'].choices == ['true', 'false']
    assert arguments['start_voice_ui'].choices == ['true', 'false']
    navigation = next(
        entity for entity in description.entities
        if entity.__class__.__name__ == 'IncludeLaunchDescription')
    assert navigation.condition is not None
    assert 'use_sim_time' in dict(navigation.launch_arguments)
    assert any(entity.__class__.__name__ == 'ExecuteProcess'
               and entity.condition is not None
               for entity in description.entities)


def test_runtime_arguments_preserve_ros_use_sim_time():
    """Dropping ROS arguments makes the navigator use wall time in simulation."""
    assert hasattr(voice_app, '_parse_runtime_arguments')
    arguments, ros_arguments = voice_app._parse_runtime_arguments([
        '--regions', '/tmp/regions.yaml',
        '--voice-config', '/tmp/voice.yaml',
        '--ros-args', '-p', 'use_sim_time:=true',
    ])
    assert arguments.regions == Path('/tmp/regions.yaml')
    assert arguments.voice_config == Path('/tmp/voice.yaml')
    assert ros_arguments[-4:] == [
        '--ros-args', '-p', 'use_sim_time:=true', '--',
    ] or ros_arguments[-3:] == ['--ros-args', '-p', 'use_sim_time:=true']


def test_voice_wrapper_quotes_venv_python_in_command_substitution(project_root):
    """A checkout path containing spaces must not split the Python executable."""
    script = (project_root / 'scripts' / 'run_voice_control.sh').read_text(
        encoding='utf-8')
    assert 'VENV_SITE="$("$VENV_PATH/bin/python" -c ' in script
