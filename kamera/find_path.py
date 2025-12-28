from typing import Tuple, Optional
import numpy as np
import config
import path_spacing

def compute_lane_center(
    left_boundary: np.ndarray,
    right_boundary: np.ndarray,
    roi_shape: Tuple[int, int],
    force_side: Optional[str] = None,
) -> np.ndarray | None:
    """
    Compute lane center points using left/right boundaries.

    force_side:
        None      -> normal (use both if available)
        "left"    -> ignore right boundary, derive center from left
        "right"   -> ignore left boundary, derive center from right
    """
    h, w = roi_shape
    num_scanlines = config.SCANLINES

    centers = []

    # ---- enforce forced side ----
    if force_side == "left":
        right_boundary = np.empty((0, 2), dtype=np.int32)
    elif force_side == "right":
        left_boundary = np.empty((0, 2), dtype=np.int32)

    # Pre-extract y columns
    left_y = left_boundary[:, 1] if left_boundary.size > 0 else None
    right_y = right_boundary[:, 1] if right_boundary.size > 0 else None

    # No boundaries at all
    if (left_boundary.size == 0) and (right_boundary.size == 0):
        return None

    band_height = h / num_scanlines

    for i in range(num_scanlines):
        i_from_bottom = i

        y_min = int(h - (i_from_bottom + 1) * band_height)
        y_max = int(h - i_from_bottom * band_height)
        y_min = max(0, y_min)
        y_max = min(h - 1, y_max)
        if y_min > y_max:
            continue

        y_center = int(0.5 * (y_min + y_max))

        # --- mean LEFT in band ---
        x_left_avg = None
        if left_boundary.size > 0:
            mask_l = (left_y >= y_min) & (left_y <= y_max)
            if mask_l.any():
                x_left_avg = float(left_boundary[mask_l, 0].mean())

        # --- mean RIGHT in band ---
        x_right_avg = None
        if right_boundary.size > 0:
            mask_r = (right_y >= y_min) & (right_y <= y_max)
            if mask_r.any():
                x_right_avg = float(right_boundary[mask_r, 0].mean())

        if x_left_avg is not None and x_right_avg is not None:
            # Both visible -> true midpoint
            center_x = 0.5 * (x_left_avg + x_right_avg)

        elif x_left_avg is not None or x_right_avg is not None:
            # Only one boundary -> estimated lane width
            lane_width_norm = (
                config.DEFAULT_LANE_WIDTH_OF_ROI
                - (config.LANE_WIDTH_DECREASE_RATE * i_from_bottom)
            )
            lane_width_px = lane_width_norm * w

            if x_left_avg is not None:
                center_x = x_left_avg + lane_width_px / 2.0
            else:
                center_x = x_right_avg - lane_width_px / 2.0
        else:
            continue

        centers.append((int(round(center_x)), y_center))

    if not centers:
        return None

    return np.array(centers, dtype=np.int32)


def detect_diverging_paths(path_l: np.ndarray, path_r: np.ndarray, roi_shape: Tuple[int, int]) -> bool:
    h, w = roi_shape

    h_middle = h//2
    y_coords, widths = path_spacing.widths_on_common_y(path_l, path_r)
    if y_coords.size == 0: return False

    # Get average spacing in bottom 50%
    middle_indexes = [i for i, y in enumerate(y_coords) if (y>h_middle and y < 0.8*h)]
    if len(middle_indexes) == 0: return False
    avg_width_middle = widths[middle_indexes].mean()

    # Get average spacing at top 10% of detected boundries
    y_min = np.min(y_coords)
    top_indexes = [i for i, y in enumerate(y_coords) if abs(y-y_min)/h < 0.1]
    if len(top_indexes) == 0: return False
    avg_width_top = widths[top_indexes].mean()

    if config.DEBUG_INTERSECTION:
        print("Top:", avg_width_top)
        print("Middle:", avg_width_middle)

    if avg_width_top < avg_width_middle: return False
    
    # Test 1
    test_1_passed = (avg_width_top/avg_width_middle) >= config.DIVERGENCE_THRESHOLD and avg_width_top > config.MIN_ABS_DIVERGENCE

    # Test 2
    test_2_passed = (avg_width_top/avg_width_middle) >= config.DIVERGENCE_THRESHOLD_2 and avg_width_top > config.MIN_ABS_DIVERGENCE_2

    # Test 3
    test_3_passed = avg_width_top > config.ABS_DIVERGENCE_THRESHOLD_TOP

    return test_1_passed or test_2_passed or test_3_passed
