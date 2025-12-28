import cv2
import numpy as np
import matplotlib.pyplot as plt
from process_frame import FrameResult
import config
import cluster as cl  # assuming this defines ClusterType etc.

COLORS = [
    (128, 0,   255),  # Purple
    (255, 128, 0),    # Orange
    (255, 0,   255),  # Magenta
    (0,   255, 128),  # Spring green
]


def get_color(cluster_id: int):
    return COLORS[cluster_id % len(COLORS)]


def build(frame: np.ndarray, result: FrameResult, intersection_is_active:bool = True) -> np.ndarray:
    """
    Draw visualization overlays directly onto the captured frame and return
    an RGB image suitable for plt.imshow().
    """
    vis = frame.copy()
    off_x, off_y = result.roi_offset

    # Helper to convert ROI-based points to full-frame
    offset_vec = np.array([off_x, off_y], dtype=np.int32)

    # --- Draw boundaries (lane lines) ---
    left_boundary, right_boundary = result.boundaries

    if left_boundary is not None and left_boundary.size > 1:
        left_pts_full = (left_boundary + offset_vec).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [left_pts_full], isClosed=False,
            color=(0, 0, 255), thickness=4
        )

    if right_boundary is not None and right_boundary.size > 1:
        right_pts_full = (right_boundary + offset_vec).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [right_pts_full], isClosed=False,
            color=(0, 0, 255), thickness=4
        )

    # --- Draw paths (centerlines) ---
    target_path = result.target_path
    other_path = result.other_path

    if target_path is not None and target_path.size > 1:
        target_pts_full = (target_path + offset_vec).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [target_pts_full],
            isClosed=False,
            color=(0, 200, 255),
            thickness=3
        )

    if other_path is not None and other_path.size > 1:
        other_pts_full = (other_path + offset_vec).reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [other_pts_full],
            isClosed=False,
            color=(0, 70, 100),
            thickness=3
        )

    # --- Draw clusters (bounding boxes + labels) ---
    for cluster in result.clusters:
        color = get_color(cluster.id)
        y_sl, x_sl = cluster.slice  # slices in ROI coords
    
        # Bounding box corners in ROI coords
        x1, x2 = x_sl.start, x_sl.stop
        y1, y2 = y_sl.start, y_sl.stop

        # Convert to full-frame coords by adding ROI offset
        pt1 = (x1 + off_x, y1 + off_y)
        pt2 = (x2 + off_x, y2 + off_y)

        # Draw bounding box
        if cluster.ctype.value in config.SHOW_CLUSTERS_BB:
            cv2.rectangle(vis, pt1, pt2, color, 2)

        # Draw ClusterType text
        if cluster.ctype.value in config.SHOW_CLUSTERS_TEXT:
            text = cluster.ctype.name.replace("_", " ")
            text_color = color
            (text_w, text_h), baseline = cv2.getTextSize(
                text, config.FONT, config.FONT_SCALE, config.FONT_THICKNESS)
            text_x = pt1[0] + 5
            text_y = pt1[1] + 15

            cv2.putText(
                vis, text, (text_x, text_y),
                config.FONT, config.FONT_SCALE,
                text_color, config.FONT_THICKNESS,
                cv2.LINE_AA
            )

        # --- Draw stop line (cluster that contains stopline) ---
        if cluster.ctype == cl.ClusterType.CONTAINS_STOPLINE and result.stop_point is not None:
            sx, sy = map(int, result.stop_point)  # ROI coords
            sy_full = sy + off_y

            _,_, x_min, x_max = cluster.bbox
            x_min_full = x_min + off_x
            x_max_full = x_max + off_x

            cv2.line(
                vis,
                (x_min_full, sy_full),
                (x_max_full, sy_full),
                (0, 0, 220),
                2
            )
            cv2.putText(
                vis, "STOP",
                (x_min_full + 8, sy_full - 8),
                config.FONT, config.FONT_SCALE,
                (0, 10, 240),
                config.FONT_THICKNESS,
                cv2.LINE_AA
            )

    # Target
    if result.target_point is not None:
        tx, ty = map(int, result.target_point)

        origin_x = config.FRAME_W // 2 + config.CAMERA_X_OFFSET
        origin_y = config.FRAME_H - 1

        cv2.line(
            vis,
            (origin_x, origin_y),
            (tx, ty),
            (0, 70, 180),
            2,
            cv2.LINE_AA
        )
        cv2.circle(vis, (tx, ty), 6, (0, 70, 240), -1)
    
    # Heading text
    text = f"{result.heading:.1f}"
    text_size, _ = cv2.getTextSize(text, cv2.FONT_ITALIC, 1.0, 2)
    text_w, _ = text_size
    color_heading = (0, 200, 255) if intersection_is_active else (245, 245, 245)
    cv2.rectangle(vis, (0,0), (round(6 + text_w*1.2), 44), (0,0,0), -1)
    cv2.putText(
        vis,
        text,
        (8, 33),
        cv2.FONT_ITALIC,
        1.0,
        color_heading,
        2,
        cv2.LINE_AA,
    )

    return vis
