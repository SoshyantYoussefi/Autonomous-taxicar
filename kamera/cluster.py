from dataclasses import dataclass
from typing import Tuple, Literal
from enum import Enum
import numpy as np
import cv2
import config


class ClusterType(Enum):
    CONTAINS_STOPLINE = 0
    LEFT = 1
    RIGHT = 2
    IGNORE = 3
    OK = 4


@dataclass
class Cluster:
    id: int
    slice: Tuple[slice, slice]
    center_coords: Tuple[int, int]
    bbox: Tuple[int, int, int, int]
    pixel_count: int
    bbox_area: int
    ctype: ClusterType = ClusterType.OK

    # Pre-computed properties
    row_widths: np.ndarray[np.int32] | None = None
    row_left:   np.ndarray[np.int32] | None = None
    row_right:  np.ndarray[np.int32] | None = None
    row_center: np.ndarray[np.int32] | None = None

def find_clusters(binary):
    """
    High-performance implementation using OpenCV:
        1) Dilation via cv2.dilate (NEON-optimized on ARM)
        2) Connected components via cv2.connectedComponentsWithStats
        3) Extract bbox, centroid, area directly from stats
        4) Precompute per-row widths and left/right/center indices
    """

    binary = np.asarray(binary)
    if binary.ndim != 2:
        raise ValueError("binary must be a 2D array")

    # Create binary mask (0/1)
    mask = (binary > 0).astype(np.uint8)

    # ----------------------------------------------------------
    # 1) Dilation
    # ----------------------------------------------------------
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(mask, kernel, iterations=config.DILATION_ITER_COUNT)

    # ----------------------------------------------------------
    # 2) Connected components
    # ----------------------------------------------------------
    num_labels, labeled, stats, centroids = cv2.connectedComponentsWithStats(
        dilated, connectivity=8
    )

    if num_labels <= 1:
        return np.zeros_like(labeled, np.int32), []

    # ----------------------------------------------------------
    # 3) Build clusters
    # ----------------------------------------------------------
    final_labeled = np.zeros_like(labeled, dtype=np.int32)
    clusters = []
    next_id = 1

    for lbl in range(1, num_labels):
        x, y, w, h, area = stats[lbl]

        if area < config.MIN_CLUSTER_ACTIVE_PX:
            continue

        y_slice = slice(y, y + h)
        x_slice = slice(x, x + w)

        # Set cluster ID in final labeled image
        final_labeled[labeled == lbl] = next_id

        cx, cy = centroids[lbl]

        # ------------------------------------------------------
        # Precompute per-row geometry
        # ------------------------------------------------------
        local = (labeled[y_slice, x_slice] == lbl)

        row_widths = np.sum(local, axis=1).astype(np.int32)

        # Prepare arrays of same length as number of rows
        row_left   = np.full(h, -1, dtype=np.int32)
        row_right  = np.full(h, -1, dtype=np.int32)
        row_center = np.full(h, -1, dtype=np.int32)

        # Compute left/right/center for each row
        for r in range(h):
            xs = np.where(local[r])[0]
            if xs.size > 0:
                row_left[r]   = xs[0]
                row_right[r]  = xs[-1]
                row_center[r] = int(xs.mean())

        clusters.append(
            Cluster(
                id=next_id,
                slice=(y_slice, x_slice),
                center_coords=(int(cx), int(cy)),
                bbox=(y, y + h, x, x + w),
                pixel_count=int(area),
                bbox_area=w * h,
                row_widths=row_widths,
                row_left=row_left,
                row_right=row_right,
                row_center=row_center
            )
        )

        next_id += 1

    return final_labeled, clusters



Method = Literal["left", "right", "center"]

def get_cluster_points(binary_labeled: np.ndarray, 
                       cluster: Cluster,
                       method: Method) -> np.ndarray:

    if method not in ("left", "right", "center"):
        raise ValueError("method must be 'left', 'right', or 'center'")

    # Starting coordinates of this cluster's bounding box
    y0 = cluster.bbox[0]
    x0 = cluster.bbox[2]

    # Precomputed row information
    row_left   = cluster.row_left
    row_right  = cluster.row_right
    row_center = cluster.row_center
    row_widths = cluster.row_widths

    h = len(row_widths)

    # Rows that contain at least one pixel
    valid_rows = np.where(row_widths > 0)[0]
    if valid_rows.size == 0:
        return np.empty((0, 2), dtype=int)

    # Pick the correct per-row x positions
    if method == "left":
        xs_local = row_left[valid_rows]
    elif method == "right":
        xs_local = row_right[valid_rows]
    else:  # center
        xs_local = row_center[valid_rows]

    # Compute global coordinates
    xs_global = xs_local + x0
    ys_global = valid_rows + y0

    return np.column_stack((xs_global, ys_global)).astype(int)
