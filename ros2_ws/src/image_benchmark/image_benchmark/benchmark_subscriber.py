#!/usr/bin/env python3
"""
Benchmark Subscriber Node
Runs in Docker container to measure middleware performance.
Subscribes to image and metadata topics, calculates metrics, generates graphs.
"""

import os
import sys
import json
import time
from datetime import datetime
from collections import deque

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

import numpy as np
import pandas as pd

# Matplotlib with non-GUI backend for container
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import custom message from separate package
try:
    from image_benchmark_msgs.msg import BenchmarkMetadata
except ImportError:
    BenchmarkMetadata = None


class BenchmarkSubscriber(Node):
    def __init__(self):
        super().__init__('benchmark_subscriber')

        # Declare parameters
        self.declare_parameter('image_topic', '/benchmark/image')
        self.declare_parameter('meta_topic', '/benchmark/metadata')
        self.declare_parameter('duration', 30)
        self.declare_parameter('output_dir', '/ros2_ws/results')
        self.declare_parameter('warmup', 3)

        # Get parameters
        self.image_topic = self.get_parameter('image_topic').value
        self.meta_topic = self.get_parameter('meta_topic').value
        self.duration = self.get_parameter('duration').value
        self.output_dir = self.get_parameter('output_dir').value
        self.warmup = self.get_parameter('warmup').value

        # Get middleware name from environment
        rmw = os.environ.get('RMW_IMPLEMENTATION', 'unknown')
        self.middleware = rmw.replace('rmw_', '').replace('_cpp', '')

        # Data collection
        self.received_sequences = []
        self.recv_timestamps = []
        self.sent_timestamps = []
        self.message_sizes = []
        self.publisher_fps_values = []
        self.image_info = {'width': 0, 'height': 0, 'encoding': ''}

        # Metadata cache (sequence -> metadata)
        self.metadata_cache = {}

        # State
        self.start_time = None
        self.warmup_complete = False
        self.first_sequence = None
        self.last_sequence = None
        self.frames_during_warmup = 0

        # Real-time stats
        self.recent_latencies = deque(maxlen=30)
        self.recent_recv_times = deque(maxlen=30)

        # Subscribers
        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            10
        )

        if BenchmarkMetadata is not None:
            self.meta_sub = self.create_subscription(
                BenchmarkMetadata,
                self.meta_topic,
                self.metadata_callback,
                10
            )
        else:
            self.meta_sub = None
            self.get_logger().warn('BenchmarkMetadata not available - using image timestamps only')

        # Timer for completion
        self.test_timer = self.create_timer(float(self.duration + self.warmup), self.finish_benchmark)

        # Timer for progress display (every second)
        self.progress_timer = self.create_timer(1.0, self.display_progress)

        # Timeout timer for no messages
        self.timeout_timer = self.create_timer(10.0, self.check_timeout)
        self.received_any = False

        self.get_logger().info(f'Benchmark subscriber started')
        self.get_logger().info(f'  Middleware: {self.middleware}')
        self.get_logger().info(f'  Duration: {self.duration}s (+ {self.warmup}s warmup)')
        self.get_logger().info(f'  Image topic: {self.image_topic}')
        self.get_logger().info(f'  Metadata topic: {self.meta_topic}')
        self.get_logger().info(f'Waiting for messages...')

    def metadata_callback(self, msg):
        """Cache metadata for matching with images."""
        self.metadata_cache[msg.sequence] = msg
        self.publisher_fps_values.append(msg.current_fps)

        # Store image info
        if msg.image_width > 0:
            self.image_info['width'] = msg.image_width
            self.image_info['height'] = msg.image_height
            self.image_info['encoding'] = msg.encoding

    def image_callback(self, msg):
        """Process received image and calculate metrics."""
        recv_time = self.get_clock().now().nanoseconds / 1e9
        self.received_any = True

        # Initialize start time on first message
        if self.start_time is None:
            self.start_time = recv_time
            self.get_logger().info(f'First message received. Starting {self.warmup}s warmup...')

        elapsed = recv_time - self.start_time

        # Handle warmup period
        if elapsed < self.warmup:
            self.frames_during_warmup += 1
            return

        if not self.warmup_complete:
            self.warmup_complete = True
            self.get_logger().info(f'Warmup complete. Recording for {self.duration}s...')

        # Extract sequence number from frame_id
        try:
            seq = int(msg.header.frame_id.split('_')[-1])
        except (ValueError, IndexError):
            seq = len(self.received_sequences)

        # Track first/last sequence
        if self.first_sequence is None:
            self.first_sequence = seq
        self.last_sequence = seq

        # Store data
        self.received_sequences.append(seq)
        self.recv_timestamps.append(recv_time)
        self.recent_recv_times.append(recv_time)

        # Calculate message size (approximate)
        msg_size = len(msg.data)
        self.message_sizes.append(msg_size)

        # Calculate latency using metadata
        if seq in self.metadata_cache:
            meta = self.metadata_cache[seq]
            sent_time = meta.sent_timestamp
            self.sent_timestamps.append(sent_time)

            latency_ms = (recv_time - sent_time) * 1000
            self.recent_latencies.append(latency_ms)

            # Clean up old metadata
            keys_to_remove = [k for k in self.metadata_cache if k < seq - 100]
            for k in keys_to_remove:
                del self.metadata_cache[k]
        else:
            # Use header timestamp if no metadata
            header_time = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
            self.sent_timestamps.append(header_time)
            latency_ms = (recv_time - header_time) * 1000
            self.recent_latencies.append(latency_ms)

    def display_progress(self):
        """Display real-time benchmark progress."""
        if self.start_time is None:
            return

        elapsed = time.time() - self.start_time
        total_duration = self.duration + self.warmup

        if not self.warmup_complete:
            phase = "WARMUP"
            phase_elapsed = elapsed
            phase_total = self.warmup
        else:
            phase = "RECORDING"
            phase_elapsed = elapsed - self.warmup
            phase_total = self.duration

        # Calculate progress bar
        progress = min(elapsed / total_duration, 1.0)
        bar_width = 20
        filled = int(bar_width * progress)
        bar = '█' * filled + '░' * (bar_width - filled)

        # Calculate current FPS
        if len(self.recent_recv_times) >= 2:
            times = list(self.recent_recv_times)
            intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
            if intervals:
                current_fps = 1.0 / (sum(intervals) / len(intervals))
            else:
                current_fps = 0
        else:
            current_fps = 0

        # Calculate stats
        frames_recv = len(self.received_sequences)
        avg_latency = np.mean(list(self.recent_latencies)) if self.recent_latencies else 0
        current_latency = list(self.recent_latencies)[-1] if self.recent_latencies else 0

        # Calculate frame loss (approximate)
        if self.first_sequence is not None and self.last_sequence is not None:
            expected = self.last_sequence - self.first_sequence + 1
            loss_pct = ((expected - frames_recv) / expected * 100) if expected > 0 else 0
        else:
            loss_pct = 0

        # Publisher FPS
        pub_fps = np.mean(self.publisher_fps_values[-30:]) if self.publisher_fps_values else 0

        # Clear line and print progress
        print('\033[2K\033[1G', end='')  # Clear line
        print(f'\n╔{"═"*58}╗')
        print(f'║ Middleware Benchmark - {self.middleware.upper():33}║')
        print(f'╠{"═"*58}╣')
        print(f'║ {phase:10} {phase_elapsed:5.1f}s / {phase_total:5.1f}s  [{bar}] {progress*100:3.0f}%   ║')
        print(f'║{" "*58}║')
        print(f'║ Publisher FPS: {pub_fps:5.1f}    Received FPS: {current_fps:5.1f}          ║')
        print(f'║ Frames Recv:   {frames_recv:5d}    Frame Loss:   {loss_pct:5.1f}%         ║')
        print(f'║ Avg Latency:   {avg_latency:5.1f}ms  Current:      {current_latency:5.1f}ms        ║')
        print(f'╚{"═"*58}╝')
        print('\033[9A', end='')  # Move cursor up

    def check_timeout(self):
        """Check if we've received any messages."""
        if not self.received_any:
            self.get_logger().error('No messages received after 10 seconds!')
            self.get_logger().error('Check that the publisher is running and middleware matches.')
            self.timeout_timer.cancel()
            rclpy.shutdown()

    def finish_benchmark(self):
        """Generate results and shut down."""
        self.test_timer.cancel()
        self.progress_timer.cancel()
        self.timeout_timer.cancel()

        # Clear progress display
        print('\n' * 10)

        if len(self.received_sequences) < 10:
            self.get_logger().error(f'Too few frames received ({len(self.received_sequences)}). Cannot generate results.')
            rclpy.shutdown()
            return

        self.get_logger().info('Benchmark complete. Generating results...')

        # Calculate all metrics
        results = self.calculate_metrics()

        # Create output directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        topic_safe = self.image_topic.replace('/', '_').strip('_')
        output_name = f'{self.middleware}_{timestamp}_{topic_safe}'
        output_path = os.path.join(self.output_dir, output_name)
        os.makedirs(output_path, exist_ok=True)

        # Save results
        self.save_results(results, output_path)
        self.generate_plots(results, output_path)

        self.get_logger().info(f'Results saved to: {output_path}')
        self.get_logger().info('Shutting down...')

        rclpy.shutdown()

    def calculate_metrics(self):
        """Calculate all benchmark metrics."""
        results = {
            'metadata': {
                'middleware': self.middleware,
                'image_topic': self.image_topic,
                'meta_topic': self.meta_topic,
                'duration_sec': self.duration,
                'warmup_sec': self.warmup,
                'timestamp': datetime.now().isoformat(),
                'ros_domain_id': int(os.environ.get('ROS_DOMAIN_ID', 0))
            },
            'publisher_stats': {},
            'subscriber_stats': {},
            'latency_ms': {},
            'jitter_ms': {},
            'bandwidth': {},
            'missing_sequences': []
        }

        # Publisher stats
        if self.publisher_fps_values:
            results['publisher_stats'] = {
                'avg_fps_reported': float(np.mean(self.publisher_fps_values)),
                'image_resolution': f"{self.image_info['width']}x{self.image_info['height']}",
                'encoding': self.image_info['encoding']
            }

        # Frame loss calculation
        received_set = set(self.received_sequences)
        if self.first_sequence is not None and self.last_sequence is not None:
            expected_set = set(range(self.first_sequence, self.last_sequence + 1))
            missing = sorted(expected_set - received_set)
            results['missing_sequences'] = missing[:100]  # Limit to first 100

            total_expected = self.last_sequence - self.first_sequence + 1
            frame_loss_count = len(missing)
            frame_loss_pct = (frame_loss_count / total_expected * 100) if total_expected > 0 else 0
        else:
            total_expected = len(self.received_sequences)
            frame_loss_count = 0
            frame_loss_pct = 0

        # Out of order detection
        out_of_order = 0
        for i in range(1, len(self.received_sequences)):
            if self.received_sequences[i] < self.received_sequences[i-1]:
                out_of_order += 1

        # Subscriber stats
        if len(self.recv_timestamps) >= 2:
            total_time = self.recv_timestamps[-1] - self.recv_timestamps[0]
            avg_fps = len(self.recv_timestamps) / total_time if total_time > 0 else 0

            # Calculate FPS over 1-second windows for std calculation
            fps_windows = []
            window_start = self.recv_timestamps[0]
            count = 0
            for t in self.recv_timestamps:
                if t - window_start < 1.0:
                    count += 1
                else:
                    fps_windows.append(count)
                    window_start = t
                    count = 1
            if count > 0:
                fps_windows.append(count)

            fps_std = float(np.std(fps_windows)) if fps_windows else 0
        else:
            avg_fps = 0
            fps_std = 0

        results['publisher_stats']['total_frames_sent'] = total_expected
        results['subscriber_stats'] = {
            'total_frames_received': len(self.received_sequences),
            'frame_loss_count': frame_loss_count,
            'frame_loss_percent': float(frame_loss_pct),
            'out_of_order_count': out_of_order,
            'avg_fps_received': float(avg_fps),
            'fps_std': float(fps_std)
        }

        # Latency calculation
        if len(self.recv_timestamps) == len(self.sent_timestamps) and len(self.recv_timestamps) > 0:
            latencies = [(r - s) * 1000 for r, s in zip(self.recv_timestamps, self.sent_timestamps)]
            # Filter out negative latencies (clock sync issues)
            valid_latencies = [l for l in latencies if l >= 0]

            if valid_latencies:
                results['latency_ms'] = {
                    'mean': float(np.mean(valid_latencies)),
                    'std': float(np.std(valid_latencies)),
                    'min': float(np.min(valid_latencies)),
                    'max': float(np.max(valid_latencies)),
                    'p50': float(np.percentile(valid_latencies, 50)),
                    'p95': float(np.percentile(valid_latencies, 95)),
                    'p99': float(np.percentile(valid_latencies, 99))
                }

                if len(latencies) - len(valid_latencies) > 0:
                    results['latency_ms']['clock_sync_warnings'] = len(latencies) - len(valid_latencies)

        # Jitter calculation (inter-frame times)
        if len(self.recv_timestamps) >= 2:
            inter_frame_times = [
                (self.recv_timestamps[i+1] - self.recv_timestamps[i]) * 1000
                for i in range(len(self.recv_timestamps) - 1)
            ]
            expected_interval = 1000.0 / avg_fps if avg_fps > 0 else 33.3

            results['jitter_ms'] = {
                'mean_interval': float(np.mean(inter_frame_times)),
                'std': float(np.std(inter_frame_times)),
                'min': float(np.min(inter_frame_times)),
                'max': float(np.max(inter_frame_times)),
                'expected_interval': float(expected_interval)
            }

        # Bandwidth calculation
        if self.message_sizes and len(self.recv_timestamps) >= 2:
            total_bytes = sum(self.message_sizes)
            total_time = self.recv_timestamps[-1] - self.recv_timestamps[0]

            if total_time > 0:
                avg_mbps = (total_bytes / total_time) / 1_000_000

                # Calculate bandwidth in 1-second windows
                bw_windows = []
                window_start = self.recv_timestamps[0]
                window_bytes = 0
                for i, t in enumerate(self.recv_timestamps):
                    if t - window_start < 1.0:
                        window_bytes += self.message_sizes[i]
                    else:
                        bw_windows.append(window_bytes / 1_000_000)
                        window_start = t
                        window_bytes = self.message_sizes[i]

                peak_mbps = max(bw_windows) if bw_windows else avg_mbps

                results['bandwidth'] = {
                    'avg_mbps': float(avg_mbps),
                    'peak_mbps': float(peak_mbps),
                    'total_mb': float(total_bytes / 1_000_000)
                }

        return results

    def save_results(self, results, output_path):
        """Save results to JSON and CSV."""
        # Save summary JSON
        json_path = os.path.join(output_path, 'summary.json')
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        self.get_logger().info(f'Saved: summary.json')

        # Save raw data CSV
        if len(self.recv_timestamps) == len(self.sent_timestamps):
            latencies = [(r - s) * 1000 for r, s in zip(self.recv_timestamps, self.sent_timestamps)]
        else:
            latencies = [0] * len(self.recv_timestamps)

        inter_frame = [0] + [
            (self.recv_timestamps[i+1] - self.recv_timestamps[i]) * 1000
            for i in range(len(self.recv_timestamps) - 1)
        ]

        df = pd.DataFrame({
            'sequence': self.received_sequences,
            'recv_timestamp': self.recv_timestamps,
            'sent_timestamp': self.sent_timestamps if len(self.sent_timestamps) == len(self.recv_timestamps) else [0]*len(self.recv_timestamps),
            'latency_ms': latencies,
            'inter_frame_ms': inter_frame,
            'message_size_bytes': self.message_sizes
        })

        csv_path = os.path.join(output_path, 'raw_data.csv')
        df.to_csv(csv_path, index=False)
        self.get_logger().info(f'Saved: raw_data.csv')

    def generate_plots(self, results, output_path):
        """Generate visualization plots."""
        plt.style.use('seaborn-v0_8-darkgrid')

        # 1. Frame Rate Over Time
        if len(self.recv_timestamps) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Calculate FPS in 1-second windows
            window_times = []
            window_fps = []
            window_start = self.recv_timestamps[0]
            count = 0

            for t in self.recv_timestamps:
                if t - window_start < 1.0:
                    count += 1
                else:
                    window_times.append(window_start - self.recv_timestamps[0])
                    window_fps.append(count)
                    window_start = t
                    count = 1

            if window_times:
                ax.plot(window_times, window_fps, 'b-', linewidth=2, label='Received FPS')
                ax.axhline(y=results['subscriber_stats']['avg_fps_received'], color='r',
                          linestyle='--', label=f"Average: {results['subscriber_stats']['avg_fps_received']:.1f}")
                ax.set_xlabel('Time (seconds)')
                ax.set_ylabel('Frames per Second')
                ax.set_title(f'Frame Rate Over Time - {self.middleware.upper()}')
                ax.legend()
                ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(os.path.join(output_path, 'frame_rate.png'), dpi=150)
            plt.close()
            self.get_logger().info('Saved: frame_rate.png')

        # 2. Latency Distribution
        if results.get('latency_ms') and 'mean' in results['latency_ms']:
            fig, ax = plt.subplots(figsize=(10, 6))

            if len(self.recv_timestamps) == len(self.sent_timestamps):
                latencies = [(r - s) * 1000 for r, s in zip(self.recv_timestamps, self.sent_timestamps)]
                latencies = [l for l in latencies if l >= 0]

                ax.hist(latencies, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
                ax.axvline(x=results['latency_ms']['mean'], color='red', linestyle='-',
                          linewidth=2, label=f"Mean: {results['latency_ms']['mean']:.2f}ms")
                ax.axvline(x=results['latency_ms']['p95'], color='orange', linestyle='--',
                          linewidth=2, label=f"95th: {results['latency_ms']['p95']:.2f}ms")
                ax.set_xlabel('Latency (ms)')
                ax.set_ylabel('Count')
                ax.set_title(f'Latency Distribution - {self.middleware.upper()}')
                ax.legend()

            plt.tight_layout()
            plt.savefig(os.path.join(output_path, 'latency.png'), dpi=150)
            plt.close()
            self.get_logger().info('Saved: latency.png')

        # 3. Jitter (Inter-frame time)
        if results.get('jitter_ms') and len(self.recv_timestamps) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))

            inter_frame_times = [
                (self.recv_timestamps[i+1] - self.recv_timestamps[i]) * 1000
                for i in range(len(self.recv_timestamps) - 1)
            ]

            ax.plot(inter_frame_times, 'b-', alpha=0.7, linewidth=0.5)
            ax.axhline(y=results['jitter_ms']['expected_interval'], color='green',
                      linestyle='--', linewidth=2,
                      label=f"Expected: {results['jitter_ms']['expected_interval']:.1f}ms")
            ax.axhline(y=results['jitter_ms']['mean_interval'], color='red',
                      linestyle='-', linewidth=2,
                      label=f"Mean: {results['jitter_ms']['mean_interval']:.1f}ms")
            ax.set_xlabel('Frame Number')
            ax.set_ylabel('Inter-frame Time (ms)')
            ax.set_title(f'Jitter Analysis - {self.middleware.upper()}')
            ax.legend()
            ax.set_ylim(0, min(results['jitter_ms']['max'] * 1.5, 200))

            plt.tight_layout()
            plt.savefig(os.path.join(output_path, 'jitter.png'), dpi=150)
            plt.close()
            self.get_logger().info('Saved: jitter.png')

        # 4. Bandwidth Over Time
        if results.get('bandwidth') and self.message_sizes:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Calculate bandwidth in 1-second windows
            bw_times = []
            bw_values = []
            window_start = self.recv_timestamps[0]
            window_bytes = 0

            for i, t in enumerate(self.recv_timestamps):
                if t - window_start < 1.0:
                    window_bytes += self.message_sizes[i]
                else:
                    bw_times.append(window_start - self.recv_timestamps[0])
                    bw_values.append(window_bytes / 1_000_000)
                    window_start = t
                    window_bytes = self.message_sizes[i]

            if bw_times:
                ax.plot(bw_times, bw_values, 'b-', linewidth=2)
                ax.axhline(y=results['bandwidth']['avg_mbps'], color='red',
                          linestyle='--', label=f"Average: {results['bandwidth']['avg_mbps']:.2f} MB/s")
                ax.set_xlabel('Time (seconds)')
                ax.set_ylabel('Bandwidth (MB/s)')
                ax.set_title(f'Bandwidth Over Time - {self.middleware.upper()}')
                ax.legend()

            plt.tight_layout()
            plt.savefig(os.path.join(output_path, 'bandwidth.png'), dpi=150)
            plt.close()
            self.get_logger().info('Saved: bandwidth.png')


def main(args=None):
    rclpy.init(args=args)

    try:
        node = BenchmarkSubscriber()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\nBenchmark interrupted. Generating partial results...')
        if 'node' in locals() and hasattr(node, 'received_sequences') and len(node.received_sequences) >= 10:
            node.finish_benchmark()
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
