# ROS 2 Middleware Benchmarking Container
# Tests: Fast DDS, Cyclone DDS, Zenoh
FROM ros:humble-ros-core-jammy

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-rosdep \
    python3-vcstool \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# bootstrap rosdep
RUN rosdep init && \
  rosdep update --rosdistro $ROS_DISTRO

# setup colcon mixin and metadata
RUN colcon mixin add default \
      https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml && \
    colcon mixin update && \
    colcon metadata add default \
      https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml && \
    colcon metadata update

# install ros2 base packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-ros-base \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# RMW IMPLEMENTATIONS (Middlewares)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Fast DDS (default in Humble)
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-fastrtps \
    # Cyclone DDS
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-cyclonedds \
    && rm -rf /var/lib/apt/lists/*

# Zenoh (install from packages.ros.org or build)
# Note: Zenoh RMW may need to be built from source for Humble
# Uncomment below if available in your ROS repos:
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-rmw-zenoh-cpp \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# BENCHMARKING & DEMO TOOLS
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-demo-nodes-cpp \
    ros-humble-demo-nodes-py \
    ros-humble-topic-tools \
    ros-humble-ros2topic \
    ros-humble-ros2node \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# FOXGLOVE BRIDGE (Visualization)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-foxglove-bridge \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# SYSTEM MONITORING TOOLS
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    htop \
    iftop \
    net-tools \
    iputils-ping \
    iproute2 \
    tcpdump \
    vim \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Python packages for benchmarking scripts
RUN pip3 install \
    matplotlib \
    pandas \
    numpy

# ============================================
# ENVIRONMENT SETUP
# ============================================
# Default to Cyclone DDS (change via docker run -e)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Source ROS 2 and workspace on container start
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc && \
    echo 'if [ -f /ros2_ws/install/setup.bash ]; then source /ros2_ws/install/setup.bash; fi' >> /root/.bashrc && \
    echo 'echo "==================================="' >> /root/.bashrc && \
    echo 'echo "RMW: $RMW_IMPLEMENTATION"' >> /root/.bashrc && \
    echo 'echo "Workspace: /ros2_ws"' >> /root/.bashrc && \
    echo 'echo "==================================="' >> /root/.bashrc

# Workspace will be mounted from host
WORKDIR /ros2_ws

# Entry point
CMD ["bash"]
