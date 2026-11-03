from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'tb4_voice_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['assets/*.ttf', 'assets/*-LICENSE.txt']},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
        (os.path.join('share', package_name, 'artifacts'), glob('artifacts/*')),
        (os.path.join('share', package_name, 'scripts'), glob('scripts/*.sh')),
        (os.path.join('share', package_name, 'docs'), glob('docs/*.md')),
        (os.path.join('share', package_name, 'docs', 'evidence'),
            glob('docs/evidence/*')),
        (os.path.join('share', package_name), ['requirements-speech.txt']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='sumika',
    maintainer_email='sumika@todo.todo',
    description='Semantic map editing and CUDA voice navigation for TurtleBot 4',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'navigate_goals = tb4_voice_control.navigate_goals:main',
            'record_goal = tb4_voice_control.goal_recorder:main',
            'validate_regions = tb4_voice_control.validate_regions:main',
            'map_editor = tb4_voice_control.map_editor:main',
            'render_segmented_map = tb4_voice_control.map_render:main',
            'voice_control = tb4_voice_control.voice_app:main',
        ],
    },
)
