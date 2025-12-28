from typing import List, Tuple
import numpy as np
import config

from cluster import Cluster, ClusterType, get_cluster_points

def cluster_resembeles_line(cluster: Cluster) -> bool:    
    row_widths = cluster.row_widths

    valid = (row_widths > 0) & (row_widths < config.MAX_LINE_WIDTH_PX)
    widths = row_widths[valid]

    if len(widths) < config.MIN_Y_PX_PER_LINE:
        return False

    mean = widths.mean()
    if mean == 0:
        return False

    # FAST and robust
    rel_std = widths.std() / mean
    return rel_std <= config.MAX_LINE_THICKNESS_DEVATION


def remove_false_clusters(clusters: List[Cluster]):
    for cluster in clusters:
        h = cluster.bbox[1] - cluster.bbox[0]
        w = cluster.bbox[3] - cluster.bbox[2]

        # Proportion check
        if h / max(w, 1) < 0.25:
            cluster.ctype = ClusterType.IGNORE
            continue
        
        # Line thickness check
        if not cluster_resembeles_line(cluster):
            cluster.ctype = ClusterType.IGNORE
            continue


def label_remaining_clusters(binary_labeled, clusters: List[Cluster]):
    for cluster in clusters:
        if cluster.ctype == ClusterType.CONTAINS_STOPLINE: 
            continue
        
        if cluster.ctype == ClusterType.IGNORE:
            continue
        
        # Check if left or right
        roi_width = binary_labeled.shape[1]
        roi_center_x = roi_width // 2

        # Use bottom points to determine L/R
        bottom_points = get_cluster_points(binary_labeled, cluster, method="center")
        if len(bottom_points) == 0:
            return

        n_bottom = max(5, len(bottom_points) // 5)  # 20% or min 5
        idx = np.argpartition(bottom_points[:,1], -n_bottom)[-n_bottom:]
        lowest_part = bottom_points[idx]

        avg_x_bottom = int(lowest_part[:, 0].mean())

        # Classify based on L/R of center
        if avg_x_bottom < roi_center_x:
            cluster.ctype = ClusterType.LEFT
        else:
            cluster.ctype = ClusterType.RIGHT

def _all_quadrants_activated(binary_labeled: np.ndarray, cluster: Cluster) -> bool:
    """ Return True if all quadrants inside the cluster ROI contain
        at least one pixel with this cluster's id.
    """
    y_slice, x_slice = cluster.slice
    lim = config.ACTIVATION_SQUARES_OF_ROI
    cl = (binary_labeled[y_slice, x_slice] == cluster.id)

    h, w = cl.shape
    if h == 0 or w == 0:
        return False

    y_cut = int(lim * (h / 2))
    x_cut = int(lim * (w / 2))

    q1 = cl[0:y_cut, 0:x_cut].any()            # top-left
    q2 = cl[h - y_cut:h, 0:x_cut].any()        # bottom-left
    q3 = cl[0:y_cut, w - x_cut:w].any()        # top-right
    q4 = cl[h - y_cut:h, w - x_cut:w].any()    # bottom-right

    return q1 and q2 and q3 and q4


def find_stop_line(binary, clusters: List[Cluster]) -> Tuple[int, int] | None:
    for cluster in clusters:
        width = cluster.bbox[3] - cluster.bbox[2]
        height = cluster.bbox[1] - cluster.bbox[0]
        if width > config.STOP_LINE_MIN_WIDTH and height > config.STOP_LINE_MIN_HEIGHT:
            if not _all_quadrants_activated(binary, cluster): continue

            cluster.ctype = ClusterType.CONTAINS_STOPLINE

            # Extract pixels belonging to current cluster
            y_slice, x_slice = cluster.slice
            cluster_mask = binary[y_slice, x_slice] > 0

            if not np.any(cluster_mask):
                continue

            ys_all, xs_all = np.where(cluster_mask)
            ys_all = ys_all + y_slice.start      # ROI coordinates
            xs_all = xs_all + x_slice.start

            if len(xs_all) == 0:
                continue

            # Mask middle 10%
            w_local = x_slice.stop - x_slice.start
            mid_start = int(w_local * 0.40)
            mid_end   = int(w_local * 0.60)
            central_strip_mask = (xs_all >= x_slice.start + mid_start) & \
                                (xs_all <  x_slice.start + mid_end)

            if not np.any(central_strip_mask):
                ys_central = ys_all # Fallback
            else:
                ys_central = ys_all[central_strip_mask]
            
            cent_x = int(np.average(xs_all))

            # Get y as mean from bottom 20% of central pixels
            k = max(1, int(len(ys_central) * 0.30))
            idx = np.argpartition(ys_central, -k)[-k:]
            cent_y = int(ys_central[idx].mean())

            return (cent_x, cent_y)

    return None