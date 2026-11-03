"""Start or reuse Nav2 and launch the CUDA voice-control application."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Build one switchable Nav2 and voice runtime launch description."""
    share = get_package_share_directory('tb4_voice_control')
    map_file = os.path.join(share, 'maps', 'map.yaml')
    regions_file = os.path.join(share, 'config', 'regions.yaml')
    voice_config = os.path.join(share, 'config', 'voice.yaml')
    voice_wrapper = os.path.join(share, 'scripts', 'run_voice_control.sh')

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(share, 'launch', 'tb4_nav2.launch.py')),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'map': LaunchConfiguration('map'),
            'rviz': LaunchConfiguration('rviz'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
        condition=IfCondition(LaunchConfiguration('start_nav2')),
    )
    voice_runtime = ExecuteProcess(
        cmd=[
            voice_wrapper,
            '--regions', LaunchConfiguration('regions_file'),
            '--voice-config', LaunchConfiguration('voice_config'),
            '--ros-args', '-p',
            ['use_sim_time:=', LaunchConfiguration('use_sim_time')],
        ],
        output='screen',
        condition=IfCondition(LaunchConfiguration('start_voice_ui')),
    )
    return LaunchDescription([
        DeclareLaunchArgument('start_nav2', default_value='true',
                              choices=['true', 'false']),
        DeclareLaunchArgument('start_voice_ui', default_value='true',
                              choices=['true', 'false']),
        DeclareLaunchArgument('use_sim_time', default_value='true',
                              choices=['true', 'false']),
        DeclareLaunchArgument('world', default_value='warehouse'),
        DeclareLaunchArgument('map', default_value=map_file),
        DeclareLaunchArgument('rviz', default_value='true',
                              choices=['true', 'false']),
        DeclareLaunchArgument('regions_file', default_value=regions_file),
        DeclareLaunchArgument('voice_config', default_value=voice_config),
        navigation,
        voice_runtime,
    ])
