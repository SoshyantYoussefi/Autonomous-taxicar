import cv2
import numpy as np
import math
from enum import Enum
import cluster as cl
import line_detection as ld
import find_boundries as fb
import find_path as fp
import config
from dataclasses import dataclass
from typing import Optional, Tuple

if config.TIME_LOGGING:
    import time

class Direction(Enum):
    LEFT = 0
    RIGHT = 1

@dataclass
class FrameResult:
    heading: float
    dist_to_stopline: Optional[np.ndarray]
    stop_point: Optional[Tuple[int, int]]
    target_point: np.ndarray
    target_path: np.ndarray
    other_path: Optional[np.ndarray]
    both_edges_found: bool
    roi: np.ndarray
    roi_offset: Tuple[int, int]
    labeled_binary: np.ndarray
    clusters: cl.Cluster
    boundaries: Tuple[np.ndarray, np.ndarray]
    median_lane_width: Optional[float]

def _extract_roi(frame):
    frame = cv2.resize(frame, (config.FRAME_W, config.FRAME_H))

    top = int(config.FRAME_H * (1.0-config.ROI_TOP))
    bottom = int(config.FRAME_H * (1.0 - config.ROI_BOTTOM))
    left = int(config.FRAME_W * config.HORIZONTAL_MARGIN)
    right = int(config.FRAME_W * (1.0 - config.HORIZONTAL_MARGIN))

    roi = frame[top:bottom, left:right]
    return roi, (left, top)


def _build_trapezoid_mask(width: int, height: int, top_scale: float) -> np.ndarray:
    """
    Create a single-channel (uint8) mask with a trapezoid:
    """
    top_scale = max(0.0, min(1.0, top_scale))

    mask = np.zeros((height, width), dtype=np.uint8)

    mid_x = width / 2.0
    half_bottom = width / 2.0
    half_top = half_bottom * top_scale

    # Trapezoid corners (x, y)
    top_left  = (int(mid_x - half_top), 0)
    top_right = (int(mid_x + half_top), 0)
    bot_right = (width - 1, height - 1)
    bot_left  = (0, height - 1)

    pts = np.array([top_left, top_right, bot_right, bot_left], dtype=np.int32)
    cv2.fillConvexPoly(mask, pts, 255)

    return mask


def _preprocess(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, binary = cv2.threshold(blur, config.BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    if config.ROI_TOP_SCALE < 1.0:
        h, w = binary.shape[:2]
        trap_mask = _build_trapezoid_mask(w, h, config.ROI_TOP_SCALE)
        binary = cv2.bitwise_and(binary, trap_mask)

    return binary


def _compute_heading(center_x_fullframe: float) -> float:
    """
    Find horizontal offset angle where 0 = camera's forward direction
    """
    image_center_x = config.FRAME_W / 2.0 + config.CAMERA_X_OFFSET
    dx = center_x_fullframe - image_center_x
    angle_rad = math.atan(dx / config.FOCAL_LENGTH_PIX)
    return math.degrees(angle_rad)


def _choose_lookahead_point(centers_roi, roi_h):
    if centers_roi is None or len(centers_roi) == 0:
        return None
    target_y = (roi_h - 1) * (1.0 - config.LOOKAHEAD_POS)

    # Find the centerline point whose y is closest to target_y
    look_cx_roi, look_cy_roi = min(
        centers_roi,
        key=lambda p: abs(p[1] - target_y)
    )
    return look_cx_roi, look_cy_roi


def _roi_to_fullframe(point, offsets):
    """
    Convert from ROI coordinates to full-frame coordinates.
    """
    return np.add(point, offsets)

_prev_heading = 0.0

def process_frame(frame, dir: Direction, force_dir: bool) -> FrameResult:
    global _prev_heading
    """
    Full pipeline:
      1) Extract ROI
      2) Binarize from predefined threshold and invert
      3) Find clusters of white pixels
      4) Label clusters
      5) Find lane
      6) Decide what to follow
      7) Compute heading based on lookahead point
    """
    if config.TIME_LOGGING:
        t0 = round(time.time() * 10000)

    # 1) ROI
    roi, offset = _extract_roi(frame)

    # 2) Binary
    binary = _preprocess(roi)

    if config.TIME_LOGGING:
        t1 = round(time.time() * 10000)
        print("Preproccess:", t1-t0)

    # 3) Clusters
    labeled_binary, clusters = cl.find_clusters(binary)

    if config.TIME_LOGGING:
        t2 = round(time.time() * 10000)
        print("Cluster detection:", t2-t1)

    ld.remove_false_clusters(clusters)

    # 4) Label clusters
    stop_point = ld.find_stop_line(labeled_binary, clusters)
    dist_to_stop = None
    if stop_point:
        dist_to_stop = _roi_to_fullframe(stop_point, offset)[1]

    ld.label_remaining_clusters(labeled_binary, clusters)

    if config.TIME_LOGGING:
        t3 = round(time.time() * 10000)
        print("Label clusters:", t3-t2)
    
    # 5) Boundries
    left_boundary, right_boundary = fb.compute_lane_boundaries(labeled_binary, clusters)

    if config.TIME_LOGGING:
        t4 = round(time.time() * 10000)
        print("Boundries:", t4-t3)

    # 6) Find possible paths
    path_l = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                         force_side="left")
    path_r = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                         force_side="right")
    
    if config.TIME_LOGGING:
        t5 = round(time.time() * 10000)
        print("Paths:", t5-t4)

    # 7) Scan for intersection
    diverging_paths = fp.detect_diverging_paths(path_l, path_r, binary.shape)

    target_path = None
    other_path = None
    median_lane_width = None
    if force_dir or diverging_paths:
        if dir == Direction.LEFT:
            target_path = path_l if path_l is not None else path_r
            if (diverging_paths):
                other_path = path_r
        elif dir == Direction.RIGHT:
            target_path = path_r if path_r is not None else path_l
            if (diverging_paths):
                other_path = path_l
    else:
        target_path = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                        force_side=None)
    
    both_edges_found = path_l is not None and path_r is not None
    if both_edges_found:
        median_lane_width = fb.compute_median_lane((left_boundary, right_boundary), binary.shape[1])

    if config.TIME_LOGGING:
        t6 = round(time.time() * 10000)
        print("Intersections:", t6-t5)

    # 8) Compute heading based on lookahead point
    target_point = None
    heading = _prev_heading
    target_point_roi = _choose_lookahead_point(target_path, roi.shape[0])
    if target_point_roi:
        target_point = _roi_to_fullframe(target_point_roi, offset)
        heading = _compute_heading(target_point[0])
        _prev_heading = heading

    if config.TIME_LOGGING:
        t7 = round(time.time() * 10000)
        print("Total:", t7-t0)

    return FrameResult(
        heading=heading,
        dist_to_stopline=dist_to_stop,
        stop_point=stop_point,
        target_point=target_point,
        target_path=target_path,
        other_path=other_path,
        both_edges_found = both_edges_found,
        roi=roi,
        roi_offset=offset,
        labeled_binary=labeled_binary,
        clusters=clusters,
        boundaries=(left_boundary, right_boundary),
        median_lane_width=median_lane_width
    )
