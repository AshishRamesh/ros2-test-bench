# ROS 2 Middleware Benchmarking Setup

Docker-based environment for testing Fast DDS, Cyclone DDS, and Zenoh middlewares.

## Quick Start

```bash
# Build
docker compose build

# Run with Cyclone DDS (default)
docker compose run ros2-cyclone

# Run with Fast DDS
docker compose run ros2-fastdds

# Run with Zenoh
docker compose run ros2-zenoh

# Run with tmux (4-pane layout)
docker compose run ros2-cyclone ./tmux_ros2.sh
```

## Middleware Quick Reference

| Middleware | Command | Best For |
|------------|---------|----------|
| Cyclone DDS | `docker compose run ros2-cyclone` | General use, low latency |
| Fast DDS | `docker compose run ros2-fastdds` | Feature-rich, large systems |
| Zenoh | `docker compose run ros2-zenoh` | WAN, cloud, NAT traversal |

## tmux Multi-Pane Setup

```bash
# Start container with tmux
docker compose run ros2-cyclone ./tmux_ros2.sh

# Or start tmux inside container
docker compose run ros2-cyclone
./tmux_ros2.sh

# Benchmarking layout (with topic monitoring)
./tmux_benchmark.sh /image_raw
```

**Layout:**
```
┌─────────────────┬─────────────────┐
│ PANE 0          │ PANE 1          │
│ Publisher       │ Subscriber      │
├─────────────────┼─────────────────┤
│ PANE 2          │ PANE 3          │
│ Monitor         │ System          │
└─────────────────┴─────────────────┘
```

**tmux Shortcuts:**

| Command | Action |
|---------|--------|
| `Ctrl+b %` | Split vertical |
| `Ctrl+b "` | Split horizontal |
| `Ctrl+b arrow` | Navigate panes |
| `Ctrl+b z` | Zoom/unzoom pane |
| `Ctrl+b d` | Detach session |

**Multiple terminals to same container:**
```bash
# Terminal 1
docker compose run --name ros2_test ros2-cyclone

# Terminal 2+
docker exec -it ros2_test bash
```

## Workspace

The `ros2_ws/` directory is mounted at `/ros2_ws` inside the container.

```bash
# Add packages to ./ros2_ws/src/
# Build inside container
colcon build
source install/setup.bash
```

## Topic Commands

```bash
ros2 topic list                    # List topics
ros2 topic hz /topic_name          # Check frequency
ros2 topic bw /topic_name          # Check bandwidth
ros2 topic delay /topic_name       # Check latency
ros2 topic echo /topic_name        # View messages
```

## Pi Camera Integration

### On Raspberry Pi

```bash
# Setup Pi (run once)
./pi_setup.sh

# Start camera (after reboot)
use_cyclone                              # or use_fastdds, use_zenoh
~/ros2_scripts/start_camera.sh 640x480 30
```

### On Docker Container

```bash
# Match middleware with Pi
docker compose run ros2-cyclone

# Verify camera topic
ros2 topic list                    # Should see /image_raw
ros2 topic hz /image_raw
```

### On Host (Visualize)

```bash
# Match middleware
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
ros2 run rqt_image_view rqt_image_view
```

## System Monitoring

```bash
htop                                     # CPU/Memory
iftop -i eth0                            # Network bandwidth
tcpdump -i eth0 port 7400 -w capture.pcap   # Packet capture
```

## Domain ID

All machines must use the same `ROS_DOMAIN_ID` (default: 0).

```bash
# Override via compose
docker compose run -e ROS_DOMAIN_ID=5 ros2-cyclone
```

## Troubleshooting

**Topics not visible:**
1. Same `RMW_IMPLEMENTATION` on all machines
2. Same `ROS_DOMAIN_ID` on all machines
3. Container uses `--net=host` (already configured in compose)

**Pi connectivity:**
```bash
ping <PI_IP>
sudo ufw allow 7400:7500/udp    # On Pi
```

## File Structure

```
docker_ws/
├── dockerfile              # Docker image
├── docker-compose.yml      # Compose services
├── pi_setup.sh             # Raspberry Pi setup script
├── README.md
└── ros2_ws/
    ├── tmux_ros2.sh        # 4-pane tmux layout
    ├── tmux_benchmark.sh   # Benchmarking tmux layout
    └── src/                # Your ROS 2 packages
```
