#!/bin/bash
# tmux 4-pane setup for ROS 2 benchmarking
# Usage: ./tmux_benchmark.sh [topic_name]
# Example: ./tmux_benchmark.sh /image_raw

SESSION_NAME="ros2_bench"
TOPIC=${1:-/chatter}

# Kill existing session if it exists
tmux kill-session -t $SESSION_NAME 2>/dev/null

# Create new session
tmux new-session -d -s $SESSION_NAME -n bench

# Split into 4 panes
tmux split-window -h -t $SESSION_NAME:bench
tmux split-window -v -t $SESSION_NAME:bench.0
tmux split-window -v -t $SESSION_NAME:bench.1

# Source ROS 2 in all panes
for i in 0 1 2 3; do
    tmux send-keys -t $SESSION_NAME:bench.$i 'source /opt/ros/humble/setup.bash' C-m
    if [ -f /ros2_ws/install/setup.bash ]; then
        tmux send-keys -t $SESSION_NAME:bench.$i 'source /ros2_ws/install/setup.bash' C-m
    fi
done

# Setup each pane with pre-loaded commands
# Pane 0: Topic list
tmux send-keys -t $SESSION_NAME:bench.0 "echo '=== Topics ===' && ros2 topic list"

# Pane 1: Frequency monitor (ready to run)
tmux send-keys -t $SESSION_NAME:bench.1 "echo '=== Frequency Monitor ===' && echo 'Press Enter to run: ros2 topic hz $TOPIC'" C-m
tmux send-keys -t $SESSION_NAME:bench.1 "ros2 topic hz $TOPIC"

# Pane 2: Bandwidth monitor (ready to run)
tmux send-keys -t $SESSION_NAME:bench.2 "echo '=== Bandwidth Monitor ===' && echo 'Press Enter to run: ros2 topic bw $TOPIC'" C-m
tmux send-keys -t $SESSION_NAME:bench.2 "ros2 topic bw $TOPIC"

# Pane 3: System monitor
tmux send-keys -t $SESSION_NAME:bench.3 "echo '=== System Monitor ===' && echo 'Commands: htop, iftop -i eth0'" C-m
tmux send-keys -t $SESSION_NAME:bench.3 "htop"

# Select first pane
tmux select-pane -t $SESSION_NAME:bench.0

# Attach to session
tmux attach -t $SESSION_NAME
