#!/usr/bin/env python3
"""
Video File Publisher Node
Publishes frames from an MP4 video file at a consistent rate.
Useful for benchmarking middleware performance without camera variability.
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


class VideoPublisher(Node):
    def __init__(self):
        super().__init__('video_publisher')

        # Declare parameters
        self.declare_parameter('video_file', '~/ros2-test-bench/video.mp4')
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30)
        self.declare_parameter('loop', True)

        # Get parameters
        self.video_file = self.get_parameter('video_file').value
        self.width = self.get_parameter('width').value
        self.height = self.get_parameter('height').value
        self.target_fps = self.get_parameter('fps').value
        self.loop = self.get_parameter('loop').value

        # Validate video file
        if not self.video_file:
            self.get_logger().error('No video file specified!')
            raise RuntimeError('video_file parameter is required')

        # Open video file
        self.get_logger().info(f'Opening video file: {self.video_file}')
        self.cap = cv2.VideoCapture(self.video_file)

        if not self.cap.isOpened():
            self.get_logger().error(f'Failed to open video file: {self.video_file}')
            raise RuntimeError('Video file not available')

        # Get video properties
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Determine output dimensions
        self.output_width = self.width if self.width > 0 else self.video_width
        self.output_height = self.height if self.height > 0 else self.video_height
        self.needs_resize = (self.output_width != self.video_width or
                            self.output_height != self.video_height)

        self.get_logger().info(
            f'Video opened: {self.video_width}x{self.video_height} @ {self.video_fps:.1f} FPS, '
            f'{self.total_frames} frames'
        )
        self.get_logger().info(
            f'Output: {self.output_width}x{self.output_height} @ {self.target_fps} FPS '
            f'(resize: {self.needs_resize}, loop: {self.loop})'
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
        self.video_frame_idx = 0
        self.loop_count = 0
        self.fps_window = deque(maxlen=30)  # Last 30 frame times for FPS calculation
        self.last_frame_time = time.time()
        self.start_time = time.time()

        # Create timer for frame publishing at target FPS
        timer_period = 1.0 / self.target_fps
        self.timer = self.create_timer(timer_period, self.publish_frame)

        self.get_logger().info('Video publisher started. Publishing to /benchmark/image and /benchmark/metadata')

    def calculate_fps(self):
        """Calculate current FPS from recent frame intervals."""
        if len(self.fps_window) < 2:
            return self.target_fps

        intervals = list(self.fps_window)
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval > 0:
            return 1.0 / avg_interval
        return self.target_fps

    def publish_frame(self):
        """Read a frame from video and publish it with metadata."""
        ret, frame = self.cap.read()

        if not ret:
            if self.loop:
                # Reset to beginning of video
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.video_frame_idx = 0
                self.loop_count += 1
                self.get_logger().info(f'Video looped (loop #{self.loop_count})')
                ret, frame = self.cap.read()
                if not ret:
                    self.get_logger().error('Failed to read frame after loop reset')
                    return
            else:
                self.get_logger().info('Video finished (loop disabled)')
                self.timer.cancel()
                return

        self.video_frame_idx += 1

        # Resize if needed
        if self.needs_resize:
            frame = cv2.resize(frame, (self.output_width, self.output_height))

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
                f'Frames: {self.sequence} | Video: {self.video_frame_idx}/{self.total_frames} | '
                f'Loop: {self.loop_count} | FPS: {current_fps:.1f}'
            )

    def destroy_node(self):
        """Clean up video capture on shutdown."""
        self.get_logger().info(f'Shutting down. Published {self.sequence} frames ({self.loop_count} loops).')
        if self.cap is not None:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = VideoPublisher()
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
