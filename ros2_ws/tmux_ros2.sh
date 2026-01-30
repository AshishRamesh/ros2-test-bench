#!/bin/bash
# tmux 4-pane setup for ROS 2 development
# Usage: ./tmux_ros2.sh [session_name]

SESSION_NAME=${1:-ros2}

# Kill existing session if it exists
tmux kill-session -t $SESSION_NAME 2>/dev/null

# Create new session
tmux new-session -d -s $SESSION_NAME -n main

# Split into 4 panes
# ┌───────┬───────┐
# │   0   │   1   │
# ├───────┼───────┤
# │   2   │   3   │
# └───────┴───────┘

tmux split-window -h -t $SESSION_NAME:main
tmux split-window -v -t $SESSION_NAME:main.0
tmux split-window -v -t $SESSION_NAME:main.1

# Source ROS 2 in all panes
tmux send-keys -t $SESSION_NAME:main.0 'source /opt/ros/humble/setup.bash && clear' C-m
tmux send-keys -t $SESSION_NAME:main.1 'source /opt/ros/humble/setup.bash && clear' C-m
tmux send-keys -t $SESSION_NAME:main.2 'source /opt/ros/humble/setup.bash && clear' C-m
tmux send-keys -t $SESSION_NAME:main.3 'source /opt/ros/humble/setup.bash && clear' C-m

# Optional: Set pane titles (requires tmux 2.6+)
tmux select-pane -t $SESSION_NAME:main.0 -T "Publisher"
tmux select-pane -t $SESSION_NAME:main.1 -T "Subscriber"
tmux select-pane -t $SESSION_NAME:main.2 -T "Monitor"
tmux select-pane -t $SESSION_NAME:main.3 -T "System"

# Display helpful info in each pane
tmux send-keys -t $SESSION_NAME:main.0 'echo "=== PANE 0: Publisher ===" && echo "RMW: $RMW_IMPLEMENTATION"' C-m
tmux send-keys -t $SESSION_NAME:main.1 'echo "=== PANE 1: Subscriber ==="' C-m
tmux send-keys -t $SESSION_NAME:main.2 'echo "=== PANE 2: Monitor (ros2 topic hz/bw) ==="' C-m
tmux send-keys -t $SESSION_NAME:main.3 'echo "=== PANE 3: System (htop/iftop) ==="' C-m

# Select first pane
tmux select-pane -t $SESSION_NAME:main.0

# Attach to session
tmux attach -t $SESSION_NAME
