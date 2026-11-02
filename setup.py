from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'tb4_voice_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='sumika',
    maintainer_email='sumika@todo.todo',
    description='TurtleBot 4 voice control: SLAM and Nav2 baseline',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'navigate_goals = tb4_voice_control.navigate_goals:main',
            'record_goal = tb4_voice_control.goal_recorder:main',
        ],
    },
)
