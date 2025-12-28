import cv2

# Image
FRAME_W, FRAME_H = 480, 360
FOCAL_LENGTH_PIX = 470
CAMERA_X_OFFSET = -20
BLACK_THRESHOLD = 120

# ROI (Region of interest) 
ROI_TOP_SCALE = 0.9
ROI_TOP = 0.75
ROI_BOTTOM = 0.20
HORIZONTAL_MARGIN = 0.01

# Cluster config
MIN_CLUSTER_ACTIVE_PX = 50
DILATION_ITER_COUNT = 2                         # Good against noise but heavy

# Line config                                   (Thresholds to be considered tape)
MIN_LINE_WIDTH_PX = 4
MAX_LINE_WIDTH_PX = 24
MAX_LINE_THICKNESS_DEVATION = 0.5
MIN_Y_PX_PER_LINE = 10

# Stop line
STOP_LINE_MIN_WIDTH = 0.6 * FRAME_W
STOP_LINE_MIN_HEIGHT = 80
ACTIVATION_SQUARES_OF_ROI = 0.8                 # Size of each quadrants square, <1.0 excludes part of middle

# Lane config
SCANLINES = 6
DEFAULT_LANE_WIDTH_OF_ROI = 0.75
LANE_WIDTH_DECREASE_RATE = 0.06
MAX_BOUNDARY_DEVIATION = 12                     # Max allowed point-to-point deviation

# Target path
LOOKAHEAD_POS = 0.5                             # How far into ROI to compute heading

# Intersections 
DIVERGENCE_THRESHOLD = 1.6  # Test 1
MIN_ABS_DIVERGENCE = 75

DIVERGENCE_THRESHOLD_2 = 2.4    # Test 2
MIN_ABS_DIVERGENCE_2 = 65

ABS_DIVERGENCE_THRESHOLD_TOP = 100                  # Test 3, If top pass => intersection       
DEBUG_INTERSECTION = False
INTERSECTION_HEADING_MULTIPLIER = 1.1

# New section detection
BUFFER_LENGTH = 5
INTO_THRESHOLD = 3
EXIT_THRESHOLD = 4

# Display
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
FONT_THICKNESS = 2
SHOW_CLUSTERS_BB = []                           # ClusterTypes (0...3) bouding box
SHOW_CLUSTERS_TEXT = []                         # ClusterTypes (0...3)

# Other
PERFORMANCE_LOGGING = True
TIME_LOGGING = False

# TCP
PORT = 6000