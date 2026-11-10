"""Verify the install manifest and launch-facing delivery assets."""

import os
from pathlib import Path
import runpy
import subprocess

from launch import LaunchContext
from launch.actions import ExecuteProcess, IncludeLaunchDescription
from launch.utilities import perform_substitutions
from packaging.requirements import Requirement
import pytest

from tb4_voice_control import voice_app
import yaml


@pytest.fixture
def project_root():
    """Return the repository checkout under test."""
    return Path(__file__).resolve().parents[1]


def test_voice_config_uses_only_gemini_settings(project_root):
    """The shipped runtime configuration must select the API speech provider."""
    config = yaml.safe_load((project_root / 'config' / 'voice.yaml').read_text())
    assert config == {
        'provider': 'gemini', 'model': 'gemini-3.8-flash', 'language': 'vi',
        'request_timeout_seconds': 120, 'sample_rate': 16000,
        'max_record_seconds': 15,
    }


@pytest.mark.parametrize('key', [None, '', ' \t\n'])
def test_launcher_requires_gemini_key_without_printing_secret(project_root, key):
    """Missing credentials must win over machine-specific ROS setup failures."""
    environment = {**os.environ, 'ROS_SETUP': '/missing/ros/setup.bash',
                   'UNRELATED_SECRET': 'SECRET_SENTINEL'}
    environment.pop('GEMINI_API_KEY', None)
    if key is not None:
        environment['GEMINI_API_KEY'] = key
    result = subprocess.run(
        ['bash', str(project_root / 'scripts' / 'run_voice_control.sh')],
        capture_output=True, text=True, env=environment)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert 'export GEMINI_API_KEY' in output
    assert 'SECRET_SENTINEL' not in output
    assert 'ROS setup not found' not in output


@pytest.mark.parametrize('installed', [False, True])
def test_launcher_has_no_cuda_runtime_mutation(project_root, tmp_path, installed):
    """The real launcher must preserve library/cache paths and quote checkout paths."""
    checkout = tmp_path / 'checkout with spaces'
    scripts = (tmp_path / 'prefix with spaces' / 'share' / 'tb4_voice_control' / 'scripts'
               if installed else checkout / 'scripts')
    scripts.mkdir(parents=True)
    launcher = scripts / 'run_voice_control.sh'
    launcher.write_bytes((project_root / 'scripts' / launcher.name).read_bytes())
    checkout.mkdir(exist_ok=True)
    (checkout / 'setup.py').touch()
    workspace = checkout / 'install'
    workspace.mkdir()
    (workspace / 'setup.bash').write_text('export WORKSPACE_ACTIVE=yes\n')
    ros_setup = tmp_path / 'ros setup.bash'
    ros_setup.write_text('export ROS_ACTIVE=yes\n')
    bin_path = checkout / '.venv-speech' / 'bin'
    bin_path.mkdir(parents=True)
    (bin_path / 'activate').write_text(f'export PATH="{bin_path}:$PATH"\n')
    site = checkout / 'site packages'
    (site / 'nvidia' / 'fake' / 'lib').mkdir(parents=True)
    python = bin_path / 'python'
    python.write_text(f'#!/bin/sh\nprintf "%s\\n" "{site}"\n')
    python.chmod(0o755)
    ros2 = bin_path / 'ros2'
    ros2.write_text(
        '#!/bin/bash\n'
        'printf "%s\\n" "$ROS_ACTIVE" "$WORKSPACE_ACTIVE" '
        '"${HF_HOME-unset}" "$LD_LIBRARY_PATH" "$PYTHONPATH" "$@"\n')
    ros2.chmod(0o755)
    environment = {**os.environ, 'GEMINI_API_KEY': 'SECRET_SENTINEL',
                   'ROS_SETUP': str(ros_setup), 'TB4_VOICE_CONTROL_ROOT': str(checkout),
                   'LD_LIBRARY_PATH': '/existing/libs', 'PYTHONPATH': '/existing/python'}
    environment.pop('HF_HOME', None)
    result = subprocess.run(
        ['bash', str(launcher), '--voice-config', '/config with spaces/voice.yaml'],
        check=True, capture_output=True, text=True, env=environment)
    assert result.stdout.splitlines() == [
        'yes', 'yes', 'unset', '/existing/libs', f'{site}:/existing/python',
        'run', 'tb4_voice_control', 'voice_control', '--voice-config',
        '/config with spaces/voice.yaml',
    ]
    assert 'SECRET_SENTINEL' not in result.stdout + result.stderr


def test_speech_requirements_are_gemini_only_and_bounded(project_root):
    """Only the specified provider and audio dependencies are delivered."""
    requirements = {
        requirement.name: requirement
        for line in (project_root / 'requirements-speech.txt').read_text().splitlines()
        if line.strip() and not line.lstrip().startswith('#')
        for requirement in [Requirement(line.strip())]
    }
    assert {name: str(req.specifier) for name, req in requirements.items()} == {
        'google-genai': '<2.34,>=2.33', 'numpy': '<2',
        'sounddevice': '<1.0,>=0.4.6',
    }


@pytest.mark.parametrize('key', ['', 'SECRET_SENTINEL'])
def test_setup_reports_gemini_preflight_without_secret_or_gpu(project_root, tmp_path, key):
    """Preflight ignores unrelated system packages and never leaks credentials."""
    checkout = tmp_path / 'checkout with spaces'
    scripts = checkout / 'scripts'
    scripts.mkdir(parents=True)
    setup = scripts / 'setup_speech_venv.sh'
    setup.write_bytes((project_root / 'scripts' / setup.name).read_bytes())
    # Avoid package installation and hardware probes; exercise real Bash output.
    bin_path = checkout / '.venv-speech' / 'bin'
    bin_path.mkdir(parents=True)
    executable = bin_path / 'python'
    executable.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "check" ]; then\n'
        '  echo "unrelated system package conflict" >&2\n'
        '  exit 86\n'
        'fi\n'
        'if [ "$1" = "-" ]; then exec /usr/bin/python3 "$@"; fi\n')
    executable.chmod(0o755)
    fake = tmp_path / 'fake'
    (fake / 'google').mkdir(parents=True)
    (fake / 'google' / '__init__.py').touch()
    (fake / 'google' / 'genai.py').touch()
    (fake / 'sounddevice.py').write_text(
        "def query_devices(kind): return {'name': 'Fake microphone'}\n")
    (fake / 'sitecustomize.py').write_text(
        "import importlib.metadata\nimportlib.metadata.version = lambda name: '1.2.3'\n")
    python3 = bin_path / 'python3'
    python3.write_text('#!/bin/sh\nexit 0\n')
    python3.chmod(0o755)
    result = subprocess.run(
        ['bash', str(setup)], check=True, capture_output=True, text=True,
        env={**os.environ, 'PATH': f'{bin_path}:{os.environ["PATH"]}',
             'PYTHONPATH': str(fake), 'GEMINI_API_KEY': key})
    output = result.stdout + result.stderr
    for name in ('google-genai', 'numpy', 'sounddevice'):
        assert f'{name}==1.2.3' in output
    assert 'Fake microphone' in output
    assert f"GEMINI_API_KEY: {'present' if key else 'absent'}" in output
    assert 'SECRET_SENTINEL' not in output
    assert 'CUDA' not in output
    assert str(scripts / 'run_voice_control.sh') in output


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
        ('share/ament_index/resource_index/packages',
         'resource/tb4_voice_control'),
        ('share/tb4_voice_control', 'package.xml'),
        ('share/tb4_voice_control', 'requirements-speech.txt'),
        ('share/tb4_voice_control/launch', 'launch/tb4_nav2.launch.py'),
        ('share/tb4_voice_control/launch', 'launch/voice_navigation.launch.py'),
        ('share/tb4_voice_control/maps', 'maps/map.yaml'),
        ('share/tb4_voice_control/maps', 'maps/map.pgm'),
        ('share/tb4_voice_control/config', 'config/regions.yaml'),
        ('share/tb4_voice_control/config', 'config/voice.yaml'),
        ('share/tb4_voice_control/artifacts', 'artifacts/segmented_map.png'),
        ('share/tb4_voice_control/scripts', 'scripts/run_voice_control.sh'),
        ('share/tb4_voice_control/scripts', 'scripts/setup_speech_venv.sh'),
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
            'gemini api', 'khởi động nav2', 'demo bằng giọng nói',
            'xử lý lỗi', 'cấu trúc repository'):
        assert section in readme
    for phrase in ('internet', 'quota', 'google', 'đi đến khu vực a',
                   'đi đến phòng thí nghiệm', 'di chuyển từ khu vực a đến khu vực b'):
        assert phrase in readme
    assert 'faster-whisper' not in readme
    assert 'nvidia cuda' not in readme


def test_voice_launch_exposes_reuse_and_runtime_switches(
        project_root, monkeypatch, tmp_path):
    """Wire each switch, include, and runtime argument to its exact target."""
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path / 'ros-log'))
    launch_path = project_root / 'launch' / 'voice_navigation.launch.py'
    assert launch_path.is_file()
    monkeypatch.setattr(
        'ament_index_python.packages.get_package_share_directory',
        lambda _name: str(project_root))
    namespace = runpy.run_path(str(launch_path))
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
        if isinstance(entity, IncludeLaunchDescription))
    voice_runtime = next(
        entity for entity in description.entities
        if isinstance(entity, ExecuteProcess))

    nav2_only = LaunchContext()
    nav2_only.launch_configurations.update({
        'start_nav2': 'true',
        'start_voice_ui': 'false',
        'world': 'warehouse',
        'map': '/tmp/map.yaml',
        'rviz': 'false',
        'use_sim_time': 'false',
        'regions_file': '/tmp/regions.yaml',
        'voice_config': '/tmp/voice.yaml',
    })
    assert navigation.condition.evaluate(nav2_only) is True
    assert voice_runtime.condition.evaluate(nav2_only) is False

    voice_only = LaunchContext()
    voice_only.launch_configurations.update({
        **nav2_only.launch_configurations,
        'start_nav2': 'false',
        'start_voice_ui': 'true',
    })
    assert navigation.condition.evaluate(voice_only) is False
    assert voice_runtime.condition.evaluate(voice_only) is True

    navigation.launch_description_source.get_launch_description(nav2_only)
    include_target = navigation.launch_description_source.location
    assert Path(include_target) == project_root / 'launch' / 'tb4_nav2.launch.py'
    include_arguments = {
        name: perform_substitutions(nav2_only, [value])
        for name, value in navigation.launch_arguments
    }
    assert include_arguments == {
        'world': 'warehouse',
        'map': '/tmp/map.yaml',
        'rviz': 'false',
        'use_sim_time': 'false',
    }

    command = [
        perform_substitutions(voice_only, token)
        for token in voice_runtime.cmd
    ]
    assert command == [
        str(project_root / 'scripts' / 'run_voice_control.sh'),
        '--regions', '/tmp/regions.yaml',
        '--voice-config', '/tmp/voice.yaml',
        '--ros-args', '-p', 'use_sim_time:=false',
    ]


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
