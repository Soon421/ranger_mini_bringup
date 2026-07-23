# Bringup

Ranger Mini 3.0 로봇의 최상위 실행(bringup) ROS2 패키지. 센서 드라이버와 로봇 베이스(주행 모터)를 한 번에 띄워 자율주행 파이프라인의 하드웨어 인터페이스를 구성합니다.

**참고:** 전체 시스템 통합 실행에 대한 자세한 내용은 [워크스페이스 메인 README](../../README.md)를 참고하세요.

> 이 패키지는 자율주행 로직 자체는 아니지만, 자율주행을 돌리기 위한 **선제 조건(센서·로봇 드라이버 bringup)** 을 한 번에 띄울 수 있도록 편의상 제공합니다. 그대로 쓰셔도 되고, 로봇·센서 드라이버 구성은 환경에 맞게 직접 설정하셔도 됩니다.

## 개요

Bringup은 실제 로봇 구동에 필요한 하드웨어 노드들을 묶어 실행하며 다음을 제공합니다:
- **센서 일괄 실행 (Sensors)**: Ouster LiDAR, UM7 IMU, (옵션) RealSense 카메라를 한 번에 구동
- **로봇 베이스 실행 (Robot Base)**: Ranger Mini 3.0 주행 모터 및 베이스 제어 노드 구동
- **통합 실행 (Bringup)**: 센서 + 베이스를 단일 명령으로 실행

## 구성 요소

### 1. 통합 런치 (`bringup.launch.py`)
`sensors.launch.py`와 `robot.launch.py`를 함께 실행하는 최상위 런치 파일입니다. 실제 로봇 운용 시 이 파일 하나로 센서와 베이스를 모두 띄웁니다.

**구현 코드 위치:** `launch/bringup.launch.py`

### 2. 센서 런치 (`sensors.launch.py`)
자율주행에 필요한 센서 드라이버들을 실행합니다.

**실행되는 센서:**
- **Ouster LiDAR** (`ouster_ros`): 3D point cloud 및 `/ouster/scan` 2D LaserScan 발행. 자율주행/위치추정의 핵심 입력
- **UM7 IMU** (`umx_driver`): 200Hz 자세/각속도 데이터 발행 (`imu_link` 프레임). LiDAR-Inertial SLAM 및 위치추정에 사용
- **RealSense D435** (`realsense2_camera`): 자율주행 자체는 LiDAR+IMU만 사용하므로 필요 없으면 끌 수 있음

**센서 선택 및 파라미터 (`config/sensors.yaml`):**

어떤 센서를 띄울지는 `SENSORS:` 섹션의 true/false로 선택합니다.

```yaml
SENSORS:
  lidar: true
  imu: true
  camera: true
```

LiDAR IP(`sensor_hostname`), UM7 포트(`port`), LaserScan 빔 인덱스(`scan_ring`, OS-32 기준 16이 수평·14는 약간 위) 등 파라미터도 같은 파일에서 수정합니다. 수정 후에는 `colcon build --packages-select ranger_mini_bringup`으로 반영해야 합니다 (`--symlink-install` 빌드면 즉시 반영).

**구현 코드 위치:** `launch/sensors.launch.py`, `config/sensors.yaml`

### 3. 로봇 베이스 런치 (`robot.launch.py`)
Ranger Mini 3.0 베이스 제어 노드를 실행합니다. `ranger_bringup` 패키지의 `ranger_mini_v3.launch.py`를 포함하여 주행 모터 제어 및 odometry를 구동합니다.

**구현 코드 위치:** `launch/robot.launch.py`

## 센서 드라이버 출처

bringup이 의존하는 드라이버는 **워크스페이스 소스에 포함된 것**과 **별도로 설치가 필요한 것**으로 나뉩니다.

### 워크스페이스 소스에 포함 (`src/` 내에서 빌드)

| 패키지 | 위치 | 비고 |
| --- | --- | --- |
| `umx_driver` (UM7 IMU) | `sensors/um7` | UM7 IMU 드라이버 |
| `serial` | `sensors/serial-ros2` | `umx_driver`가 의존하는 시리얼 통신 라이브러리 |
| `ranger_bringup` (로봇 베이스) | `robot/ranger_ros2/ranger_bringup` | Ranger Mini 3.0 베이스 제어 |

이 패키지들은 워크스페이스를 빌드하면 함께 빌드됩니다.

### apt로 설치 필요 (외부 의존성)

| 패키지 | 설치 명령 | 비고 |
| --- | --- | --- |
| `ouster_ros` (Ouster LiDAR) | `sudo apt install ros-humble-ouster-ros` | Ouster LiDAR 드라이버 |
| `realsense2_camera` (RealSense) | `sudo apt install ros-humble-realsense2-camera` | RealSense 카메라 드라이버 (옵션) |

## 설치

### 사전 요구사항
- Ubuntu 22.04
- ROS2 Humble

### 외부 센서 드라이버 설치 (apt)
워크스페이스에 포함되지 않은 LiDAR/카메라 드라이버는 apt로 설치합니다.

```bash
sudo apt install ros-humble-ouster-ros          # Ouster LiDAR
sudo apt install ros-humble-realsense2-camera   # RealSense 카메라
```

### 로봇 베이스 CAN 설정
로봇 베이스(`ranger_base`)는 `can0` CAN 버스로 통신합니다. `robot.launch.py` 실행 전 CAN 인터페이스를 활성화해야 합니다.

```bash
sudo modprobe gs_usb                                  # CAN-USB 커널 모듈 로드
sudo ip link set can0 up type can bitrate 500000      # can0 인터페이스 활성화
```
> ranger_bringup에 포함된 `scripts/setup_can2usb.bash`로도 한 번에 실행할 수 있습니다.

연결이 정상인지 확인하려면 `candump`로 CAN 메시지가 들어오는지 봅니다 (로봇 전원이 켜져 있어야 함):

```bash
sudo apt install can-utils   # 최초 1회
candump can0                 # 메시지가 흐르면 정상 연결
```

### 장치 권한 (시리얼 / 카메라)
UM7 IMU(`/dev/ttyUSB*`)와 RealSense 카메라(`/dev/video*`) 접근 권한이 없으면 드라이버가 장치를 열지 못합니다. 현재 사용자를 관련 그룹에 추가하면 됩니다 (재로그인 후 적용).

```bash
sudo usermod -aG dialout,video $USER
```
> 일시적으로는 `sudo chmod 666 /dev/ttyUSB0`, `sudo chmod 666 /dev/video0`처럼 직접 권한을 줄 수도 있습니다.

### 빌드

```bash
# 워크스페이스로 이동
cd <your_workspace>

# ROS 의존성 설치 (ouster_ros, realsense2_camera 등 외부 의존성 포함)
rosdep update
rosdep install --from-paths src --ignore-src -y

# 빌드 (bringup과 이 레포에 포함된 드라이버 패키지들을 함께 빌드)
colcon build --packages-up-to ranger_mini_bringup

# Source
source install/setup.bash
```

## 사용법

### 통합 실행 (센서 + 로봇 베이스)

```bash
ros2 launch ranger_mini_bringup bringup.launch.py
```

### 개별 실행

```bash
ros2 launch ranger_mini_bringup sensors.launch.py   # 센서만
ros2 launch ranger_mini_bringup robot.launch.py     # 로봇 베이스만
```

### 센서 구성 변경

센서 on/off와 파라미터(LiDAR IP, IMU 포트 등)는 `config/sensors.yaml`에서 수정합니다.

```bash
# 예: 카메라 끄기 → config/sensors.yaml 에서 camera: false 로 변경 후
colcon build --packages-select ranger_mini_bringup && source install/setup.bash
ros2 launch ranger_mini_bringup bringup.launch.py
```
