from scipy import ndimage
import numpy as np

def skeletonize(binary):
    # Ensure uint8 0/255
    bin_u8 = (binary > 0).astype(np.uint8) * 255

    # Zhang-Suen thinning
    try:
        from cv2.ximgproc import thinning
    except ImportError:
        raise RuntimeError(
            "cv2.ximgproc.thinning not available. "
            "Install opencv-contrib-python==4.12.0.88"
        )

    skel = thinning(bin_u8)
    skel_bin = (skel > 0).astype(np.uint8)
    return skel_bin


def split_cluster_into_branches(
    cluster_mask,
    min_branch_pixels=10,
    thicken_iterations=0,
):
    """
    Given a binary mask for ONE cluster, skeletonize it and break it into
    separate branch segments at junctions (T / X intersections).
    """
    cluster_mask = np.asarray(cluster_mask).astype(bool)
    if cluster_mask.ndim != 2:
        raise ValueError("cluster_mask must be a 2D array")

    # 1) Skeletonize: make the cluster 1-pixel-wide
    skel_bin = skeletonize(cluster_mask)

    if not skel_bin.any():
        return np.zeros_like(cluster_mask, dtype=np.int32), []

    # 2) Count 8-connected neighbors for each skeleton pixel
    #    (center excluded)
    neighbor_kernel = np.array(
        [[1, 1, 1],
         [1, 0, 1],
         [1, 1, 1]],
        dtype=np.uint8,
    )

    neighbor_count = ndimage.convolve(
        skel_bin.astype(np.uint8),
        neighbor_kernel,
        mode="constant",
        cval=0,
    )

    # Endpoints: degree 1 (not used for splitting, but handy to keep around)
    endpoints = (skel_bin == 1) & (neighbor_count == 1)

    # Branch points: degree >= 3 (T / X junctions)
    branch_points = (skel_bin == 1) & (neighbor_count >= 5)

    # 3) Remove branch points → skeleton falls apart into separate paths
    skel_split = skel_bin & ~branch_points

    # 4) Label the separated skeleton segments
    structure = np.ones((3, 3), dtype=bool)  # 8-connected on skeleton
    raw_labels, num_raw = ndimage.label(skel_split, structure=structure)

    if num_raw == 0:
        return np.zeros_like(cluster_mask, dtype=np.int32), []

    # 5) Filter small branches and optionally thicken back to lines
    branch_labels = np.zeros_like(raw_labels, dtype=np.int32)
    branches = []
    next_id = 1

    for raw_id in range(1, num_raw + 1):
        skel_branch = (raw_labels == raw_id)
        count = int(skel_branch.sum())
        if count < min_branch_pixels:
            continue

        # Bounding box of this skeleton branch
        ys, xs = np.where(skel_branch)
        y0, y1 = ys.min(), ys.max() + 1
        x0, x1 = xs.min(), xs.max() + 1

        if thicken_iterations > 0:
            # Thicken skeleton back into a wider line, but only inside cluster_mask
            dilated = ndimage.binary_dilation(
                skel_branch,
                structure=np.ones((3, 3), bool),
                iterations=thicken_iterations,
            )
            branch_full = dilated & cluster_mask
        else:
            # Just use the skeleton pixels
            branch_full = skel_branch

        branch_labels[branch_full] = next_id

        branches.append(
            {
                "id": next_id,
                "pixel_count": count,
                "bbox": (y0, y1, x0, x1),
            }
        )
        next_id += 1

    return branch_labels.astype(np.int32), branches
