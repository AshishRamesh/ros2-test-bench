#!/usr/bin/env python3
"""
Benchmark Publisher Node
Runs on Raspberry Pi to capture and publish camera frames with metadata.
Uses OpenCV for camera capture (more compatible with Pi Camera).
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import time
from collections import deque

# Import custom message from separate package
try:
    from image_benchmark_msgs.msg import BenchmarkMetadata
except ImportError:
    BenchmarkMetadata = None


class BenchmarkPublisher(Node):
    def __init__(self):
        super().__init__('benchmark_publisher')

        # Declare parameters
        self.declare_parameter('device', 0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30)

        # Get parameters
        self.device = self.get_parameter('device').value
        self.width = self.get_parameter('width').value
        self.height = self.get_parameter('height').value
        self.target_fps = self.get_parameter('fps').value

        # Initialize camera
        self.get_logger().info(f'Opening camera device {self.device}...')
        self.cap = cv2.VideoCapture(self.device)

        if not self.cap.isOpened():
            self.get_logger().error('Failed to open camera!')
            raise RuntimeError('Camera not available')

        # Configure camera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        # Get actual camera settings
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        self.get_logger().info(
            f'Camera opened: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS (target: {self.target_fps})'
        )

        # Publishers
        self.image_pub = self.create_publisher(Image, '/benchmark/image', 10)

        if BenchmarkMetadata is not None:
            self.meta_pub = self.create_publisher(BenchmarkMetadata, '/benchmark/metadata', 10)
        else:
            self.meta_pub = None
            self.get_logger().warn('BenchmarkMetadata message not available - metadata publishing disabled')

        # CV Bridge for image conversion
        self.bridge = CvBridge()

        # State tracking
        self.sequence = 0
        self.fps_window = deque(maxlen=30)  # Last 30 frame times for FPS calculation
        self.last_frame_time = time.time()
        self.start_time = time.time()

        # Create timer for frame capture at target FPS
        timer_period = 1.0 / self.target_fps
        self.timer = self.create_timer(timer_period, self.capture_and_publish)

        self.get_logger().info('Benchmark publisher started. Publishing to /benchmark/image and /benchmark/metadata')

    def calculate_fps(self):
        """Calculate current FPS from recent frame intervals."""
        if len(self.fps_window) < 2:
            return self.target_fps

        intervals = list(self.fps_window)
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval > 0:
            return 1.0 / avg_interval
        return self.target_fps

    def capture_and_publish(self):
        """Capture a frame and publish it with metadata."""
        ret, frame = self.cap.read()

        if not ret:
            self.get_logger().warn('Failed to capture frame')
            return

        # Get current time
        now = self.get_clock().now()
        current_time = time.time()

        # Track frame timing for FPS calculation
        frame_interval = current_time - self.last_frame_time
        self.fps_window.append(frame_interval)
        self.last_frame_time = current_time

        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create and publish Image message
        img_msg = self.bridge.cv2_to_imgmsg(frame_rgb, encoding='rgb8')
        img_msg.header.stamp = now.to_msg()
        img_msg.header.frame_id = f'benchmark_{self.sequence}'
        self.image_pub.publish(img_msg)

        # Create and publish metadata message
        if self.meta_pub is not None:
            meta_msg = BenchmarkMetadata()
            meta_msg.sequence = self.sequence
            meta_msg.sent_timestamp = now.nanoseconds / 1e9
            meta_msg.current_fps = float(self.calculate_fps())
            meta_msg.image_width = frame_rgb.shape[1]
            meta_msg.image_height = frame_rgb.shape[0]
            meta_msg.encoding = 'rgb8'
            self.meta_pub.publish(meta_msg)

        self.sequence += 1

        # Log progress every 30 frames
        if self.sequence % 30 == 0:
            elapsed = current_time - self.start_time
            current_fps = self.calculate_fps()
            self.get_logger().info(
                f'Frames: {self.sequence} | Elapsed: {elapsed:.1f}s | FPS: {current_fps:.1f}'
            )

    def destroy_node(self):
        """Clean up camera on shutdown."""
        self.get_logger().info(f'Shutting down. Published {self.sequence} frames.')
        if self.cap is not None:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = BenchmarkPublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        print(f'Error: {e}')
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
