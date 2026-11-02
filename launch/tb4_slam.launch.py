"""Launch TurtleBot 4 simulation and SLAM Toolbox in the warehouse world."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Build the mapping launch description."""
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('turtlebot4_ignition_bringup'),
            '/launch/turtlebot4_ignition.launch.py',
        ]),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'model': 'standard',
            'use_sim_time': 'true',
            'slam': 'true',
            'nav2': 'false',
            'localization': 'false',
            'rviz': LaunchConfiguration('rviz'),
        }.items(),
    )
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='warehouse'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        simulation,
    ])
