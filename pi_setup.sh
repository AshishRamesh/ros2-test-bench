#!/bin/bash
# =============================================================================
# Raspberry Pi ROS 2 Setup Script
# Ubuntu 22.04 Server + ROS 2 Humble + Middlewares + Pi Camera
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "  Raspberry Pi ROS 2 Middleware Setup"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# SYSTEM UPDATE
# =============================================================================
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# =============================================================================
# LOCALE SETUP
# =============================================================================
print_status "Setting up locale..."
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# =============================================================================
# ROS 2 REPOSITORY SETUP
# =============================================================================
print_status "Adding ROS 2 repository..."
sudo apt install -y software-properties-common curl

# Add ROS 2 GPG key
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

# Add repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update

# =============================================================================
# ROS 2 HUMBLE INSTALLATION (Base - minimal for Pi)
# =============================================================================
print_status "Installing ROS 2 Humble base..."
sudo apt install -y ros-humble-ros-base

# Development tools
print_status "Installing development tools..."
sudo apt install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-pip \
    build-essential \
    git

# Initialize rosdep
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    print_status "Initializing rosdep..."
    sudo rosdep init
fi
rosdep update

# =============================================================================
# RMW IMPLEMENTATIONS (Middlewares)
# =============================================================================
print_status "Installing Fast DDS..."
sudo apt install -y \
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-fastrtps

print_status "Installing Cyclone DDS..."
sudo apt install -y \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-cyclonedds

print_status "Installing Zenoh..."
sudo apt install -y ros-humble-rmw-zenoh-cpp

# =============================================================================
# CAMERA PACKAGES
# =============================================================================
print_status "Installing camera packages..."
sudo apt install -y \
    ros-humble-image-transport \
    ros-humble-image-common \
    ros-humble-cv-bridge \
    ros-humble-vision-opencv \
    ros-humble-v4l2-camera \
    ros-humble-image-transport-plugins

# Camera dependencies
sudo apt install -y \
    v4l-utils \
    libraspberrypi-bin \
    python3-opencv

# =============================================================================
# PI CAMERA SETUP
# =============================================================================
print_status "Configuring Pi Camera..."

# Enable camera in config (for legacy camera stack)
if ! grep -q "start_x=1" /boot/firmware/config.txt 2>/dev/null; then
    print_status "Adding camera config to /boot/firmware/config.txt..."
    echo "" | sudo tee -a /boot/firmware/config.txt
    echo "# Pi Camera" | sudo tee -a /boot/firmware/config.txt
    echo "start_x=1" | sudo tee -a /boot/firmware/config.txt
    echo "gpu_mem=128" | sudo tee -a /boot/firmware/config.txt
fi

# For Pi Camera Module 3 / libcamera stack
if ! grep -q "camera_auto_detect=1" /boot/firmware/config.txt 2>/dev/null; then
    echo "camera_auto_detect=1" | sudo tee -a /boot/firmware/config.txt
fi

# Load v4l2 module for Pi Camera
if ! grep -q "bcm2835-v4l2" /etc/modules 2>/dev/null; then
    echo "bcm2835-v4l2" | sudo tee -a /etc/modules
fi

# Add user to video group
sudo usermod -aG video $USER

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================
print_status "Setting up environment..."

# Backup existing bashrc
cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S)

# Add ROS 2 setup to bashrc
cat >> ~/.bashrc << 'EOF'

# =============================================================================
# ROS 2 Humble Setup
# =============================================================================
source /opt/ros/humble/setup.bash

# Default middleware (Cyclone DDS)
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Domain ID (must match other machines)
export ROS_DOMAIN_ID=0

# Middleware switching aliases
alias use_cyclone='export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp && echo "Switched to Cyclone DDS"'
alias use_fastdds='export RMW_IMPLEMENTATION=rmw_fastrtps_cpp && echo "Switched to Fast DDS"'
alias use_zenoh='export RMW_IMPLEMENTATION=rmw_zenoh_cpp && echo "Switched to Zenoh"'

# Camera aliases
alias cam_list='v4l2-ctl --list-devices'
alias cam_info='v4l2-ctl -d /dev/video0 --all'
alias cam_formats='v4l2-ctl -d /dev/video0 --list-formats-ext'

# Quick camera publisher (default settings)
alias cam_pub='ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0'

# Show current middleware
alias show_rmw='echo "Current RMW: $RMW_IMPLEMENTATION"'

echo "=================================="
echo "ROS 2 Humble loaded"
echo "RMW: $RMW_IMPLEMENTATION"
echo "Domain ID: $ROS_DOMAIN_ID"
echo "=================================="
echo "Commands: use_cyclone, use_fastdds, use_zenoh"
echo "Camera:   cam_pub, cam_list, cam_info"
echo "=================================="
EOF

# =============================================================================
# CREATE CAMERA LAUNCH SCRIPT
# =============================================================================
print_status "Creating camera publisher script..."

mkdir -p ~/ros2_scripts

cat > ~/ros2_scripts/start_camera.sh << 'EOF'
#!/bin/bash
# Pi Camera Publisher Script
# Usage: ./start_camera.sh [resolution] [fps]
#   resolution: 640x480, 1280x720, 1920x1080 (default: 640x480)
#   fps: frames per second (default: 30)

RESOLUTION=${1:-"640x480"}
FPS=${2:-30}

# Parse resolution
WIDTH=$(echo $RESOLUTION | cut -d'x' -f1)
HEIGHT=$(echo $RESOLUTION | cut -d'x' -f2)

echo "=============================================="
echo "Starting Pi Camera Publisher"
echo "Resolution: ${WIDTH}x${HEIGHT}"
echo "FPS: ${FPS}"
echo "RMW: ${RMW_IMPLEMENTATION}"
echo "=============================================="

# Check if camera exists
if [ ! -e /dev/video0 ]; then
    echo "ERROR: /dev/video0 not found!"
    echo "Try: sudo modprobe bcm2835-v4l2"
    exit 1
fi

ros2 run v4l2_camera v4l2_camera_node --ros-args \
    -p video_device:=/dev/video0 \
    -p image_size:="[$WIDTH, $HEIGHT]" \
    -p camera_frame_id:=camera_optical_frame \
    -p pixel_format:=YUYV \
    -p time_per_frame:="[1, $FPS]"
EOF

chmod +x ~/ros2_scripts/start_camera.sh

# =============================================================================
# CREATE BENCHMARK PUBLISHER SCRIPT
# =============================================================================
print_status "Creating benchmark publisher script..."

cat > ~/ros2_scripts/benchmark_camera.sh << 'EOF'
#!/bin/bash
# Camera Benchmark Script - runs camera and shows stats
# Usage: ./benchmark_camera.sh [middleware] [resolution]

MIDDLEWARE=${1:-"cyclone"}
RESOLUTION=${2:-"640x480"}

case $MIDDLEWARE in
    cyclone)
        export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
        ;;
    fastdds)
        export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
        ;;
    zenoh)
        export RMW_IMPLEMENTATION=rmw_zenoh_cpp
        ;;
    *)
        echo "Unknown middleware: $MIDDLEWARE"
        echo "Use: cyclone, fastdds, or zenoh"
        exit 1
        ;;
esac

echo "=============================================="
echo "Benchmark Camera Publisher"
echo "Middleware: $MIDDLEWARE ($RMW_IMPLEMENTATION)"
echo "Resolution: $RESOLUTION"
echo "=============================================="

# Start camera
~/ros2_scripts/start_camera.sh $RESOLUTION 30
EOF

chmod +x ~/ros2_scripts/benchmark_camera.sh

# =============================================================================
# CREATE MIDDLEWARE TEST SCRIPT
# =============================================================================
cat > ~/ros2_scripts/test_middleware.sh << 'EOF'
#!/bin/bash
# Quick middleware connectivity test
# Run this to verify middleware is working

echo "Testing ROS 2 middleware: $RMW_IMPLEMENTATION"
echo "Publishing test messages for 5 seconds..."

timeout 5 ros2 run demo_nodes_cpp talker &
TALKER_PID=$!

sleep 1

echo ""
echo "Checking if messages are being published..."
timeout 3 ros2 topic hz /chatter

kill $TALKER_PID 2>/dev/null

echo ""
echo "Test complete. If you saw frequency data, middleware is working."
EOF

chmod +x ~/ros2_scripts/test_middleware.sh

# =============================================================================
# INSTALL PYTHON TOOLS FOR BENCHMARKING
# =============================================================================
print_status "Installing Python benchmarking tools..."
pip3 install --user \
    matplotlib \
    pandas \
    numpy

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  SETUP COMPLETE!${NC}"
echo "=============================================="
echo ""
echo "Installed:"
echo "  - ROS 2 Humble (ros-base)"
echo "  - Fast DDS (rmw_fastrtps_cpp)"
echo "  - Cyclone DDS (rmw_cyclonedds_cpp)"
echo "  - Zenoh (rmw_zenoh_cpp)"
echo "  - Pi Camera packages (v4l2_camera)"
echo ""
echo "Scripts created in ~/ros2_scripts/:"
echo "  - start_camera.sh [resolution] [fps]"
echo "  - benchmark_camera.sh [middleware] [resolution]"
echo "  - test_middleware.sh"
echo ""
echo "Quick commands (after reboot):"
echo "  use_cyclone    - Switch to Cyclone DDS"
echo "  use_fastdds    - Switch to Fast DDS"
echo "  use_zenoh      - Switch to Zenoh"
echo "  cam_pub        - Start camera publisher"
echo "  cam_list       - List camera devices"
echo ""
echo -e "${YELLOW}IMPORTANT: Reboot required for camera to work!${NC}"
echo ""
echo "After reboot, test with:"
echo "  1. cam_list              # Check camera detected"
echo "  2. test_middleware.sh    # Test ROS 2 works"
echo "  3. cam_pub               # Start publishing"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
