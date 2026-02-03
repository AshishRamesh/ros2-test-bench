# Lightweight metadata published alongside each image frame
# Used for accurate latency and frame loss measurement

uint32 sequence          # Frame sequence number (starts at 0)
float64 sent_timestamp   # Time when frame was captured/sent (seconds since epoch)
float32 current_fps      # Publisher's current measured FPS
uint32 image_width       # Image width in pixels
uint32 image_height      # Image height in pixels
string encoding          # Image encoding (e.g., "rgb8", "bgr8", "mono8")
