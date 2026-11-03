"""Launch TurtleBot 4 localization and Nav2 with the packaged warehouse map."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Build the navigation launch description."""
    map_file = os.path.join(
        get_package_share_directory('tb4_voice_control'), 'maps', 'map.yaml'
    )
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('turtlebot4_ignition_bringup'),
            '/launch/turtlebot4_ignition.launch.py',
        ]),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'model': 'standard',
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'nav2': 'true',
            'slam': 'false',
            'localization': 'true',
            'rviz': LaunchConfiguration('rviz'),
            'map': LaunchConfiguration('map'),
        }.items(),
    )
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='warehouse'),
        DeclareLaunchArgument('map', default_value=map_file),
        DeclareLaunchArgument('use_sim_time', default_value='true',
                              choices=['true', 'false']),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        simulation,
    ])
