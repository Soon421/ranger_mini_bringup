import os, yaml
from launch import LaunchDescription
from launch.actions import GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

cfg_path = os.path.join(
    get_package_share_directory("ranger_mini_bringup"), "config/sensors.yaml"
)

PARAMS = yaml.safe_load(open(cfg_path))
ENABLE = PARAMS["SENSORS"]
PARAMS_LIDAR = PARAMS["LIDAR"]
PARAMS_IMU = PARAMS["IMU"]

# Ouster LiDAR
OUSTER_LAUNCH = GroupAction([
    IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('ouster_ros'), 'launch', 'sensor.launch.xml',
            ])
        ),
        launch_arguments={
            'sensor_hostname': PARAMS_LIDAR['sensor_hostname'],
            'viz': 'false',
            'timestamp_mode': 'TIME_FROM_ROS_TIME',
            'scan_ring': str(PARAMS_LIDAR['scan_ring']),
        }.items(),
    )
])

# base_link → os_sensor 정적 TF (Ouster 장착 위치)
OUSTER_TF_NODE = Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    name='ouster_transform',
    arguments=['-0.09', '0', '0.248', '0', '0', '0', 'base_link', 'os_sensor'],
    output='screen',
)

# RealSense D435
REALSENSE_LAUNCH = GroupAction([
    IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('realsense2_camera'), 'launch', 'rs_launch.py',
            ])
        ),
    )
])

# UM7 IMU
UM7_NODE = Node(
    package='umx_driver',
    executable='um7_driver',
    name='um7_driver',
    output='screen',
    parameters=[PARAMS_IMU],
)


def generate_launch_description():
    actions = []
    if ENABLE['lidar']:
        actions += [OUSTER_LAUNCH, OUSTER_TF_NODE]
    if ENABLE['imu']:
        actions += [UM7_NODE]
    if ENABLE['camera']:
        actions += [REALSENSE_LAUNCH]
    return LaunchDescription(actions)
