import numpy as np
from collections import defaultdict

def _y_to_mean_x(points: np.ndarray) -> dict[int, float]:
    """
    Given an array of [x, y] points, return mean of x for y
    """
    pts = np.asarray(points).reshape(-1, 2)
    buckets = defaultdict(list)
    for x, y in pts:
        buckets[int(y)].append(float(x))

    return {y: float(np.mean(xs)) for y, xs in buckets.items()}


def widths_on_common_y(left_boundary: np.ndarray,
                        right_boundary: np.ndarray):
    """
    Returns (ys, widths) where ys are the y-coordinates that exist
    in BOTH boundaries, and widths = |x_right - x_left| at each such y.
    """
    if left_boundary is None or right_boundary is None:
        return np.array([]), np.array([])

    if left_boundary.size == 0 or right_boundary.size == 0:
        return np.array([]), np.array([])

    left_map = _y_to_mean_x(left_boundary)
    right_map = _y_to_mean_x(right_boundary)

    # Only y's that exist in both maps
    common_ys = sorted(set(left_map.keys()) & set(right_map.keys()))
    if len(common_ys) == 0:
        return np.array([]), np.array([])

    ys = np.array(common_ys, dtype=int)
    l_xs = np.array([left_map[y] for y in common_ys], dtype=float)
    r_xs = np.array([right_map[y] for y in common_ys], dtype=float)

    widths = np.abs(r_xs - l_xs)
    return ys, widths

