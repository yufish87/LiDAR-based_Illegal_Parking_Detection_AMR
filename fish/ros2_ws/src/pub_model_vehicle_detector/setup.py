from setuptools import setup
import os
from glob import glob

package_name = 'pub_model_vehicle_detector'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name] if os.path.exists('resource/' + package_name) else []),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='fish',
    maintainer_email='fish@todo.todo',
    description='PointPillars pre-trained model detector for ROS 2',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'detector_node = pub_model_vehicle_detector.detector_node:main',
            'map_server_node = pub_model_vehicle_detector.map_server_node:main',
            'localizer_node = pub_model_vehicle_detector.localizer_node:main',
        ],
    },
)
