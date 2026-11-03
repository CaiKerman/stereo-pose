"""Geometry-driven correspondence of independently detected stereo checkerboards.

Each rectangular board permits a direct ordering and a whole-board 180-degree
reversal. Do NOT reverse individual rows/columns or match by image x/y position.
No camera equality, parallel-axis assumption, known baseline or square size is
used here. A fundamental matrix is estimated from several frozen stereo pairs,
then each pair is resolved against the common geometry *before* calibration.
"""
from __future__ import annotations

import cv2
import numpy as np


class CornerCorrespondenceError(ValueError):
    """2D checkerboard correspondences are ambiguous or geometrically invalid."""


def _sampson_px(fundamental, left, right):
    """Symmetric first-order epipolar distance in input-image pixels."""
    l = np.asarray(left, dtype=np.float64).reshape(-1, 2)
    r = np.asarray(right, dtype=np.float64).reshape(-1, 2)
    lh = np.column_stack((l, np.ones(len(l))))
    rh = np.column_stack((r, np.ones(len(r))))
    fl = lh @ fundamental.T
    ftr = rh @ fundamental
    numerator = np.abs(np.sum(rh * fl, axis=1))
    denominator = np.sqrt(np.maximum(
        np.sum(fl[:, :2] ** 2, axis=1) + np.sum(ftr[:, :2] ** 2, axis=1),
        1e-16,
    ))
    return numerator / denominator


def normalize_stereo_pairs(left_pairs, right_pairs, *, threshold_px=3.0,
                           min_good_pairs=None):
    """Return (right_corners_in_left_order, evidence), or fail before NPZ output.

    The RANSAC pool includes BOTH legal orderings for EVERY pair. Consequently
    even if most or all right frames are reversed, the correct physical matches
    remain available to find a consensus fundamental matrix. Candidate
    comparisons use only pixels and epipolar geometry, not the nominal board
    square_mm, and do not assume the cameras share focal length or orientation.

    A score must both pass the geometry threshold and clearly beat the other
    ordering. By default reject an ambiguous pair immediately; when the caller
    supplies min_good_pairs, omit individually invalid pairs only if enough
    trustworthy pairs remain, recording the indices for audit. Do not guess.
    No fixed 24-pair requirement is introduced.
    """
    if len(left_pairs) != len(right_pairs) or len(left_pairs) < 3:
        raise CornerCorrespondenceError(
            "左右棋盘格样本数量不一致，或不足以建立双目几何对应关系"
        )
    left, right = [], []
    for index, (l, r) in enumerate(zip(left_pairs, right_pairs)):
        l = np.asarray(l, dtype=np.float64).reshape(-1, 2)
        r = np.asarray(r, dtype=np.float64).reshape(-1, 2)
        if (l.shape != r.shape or l.shape[0] < 8 or
                not np.isfinite(l).all() or not np.isfinite(r).all()):
            raise CornerCorrespondenceError(
                f"第 {index + 1} 组棋盘格角点形状或数值无效"
            )
        left.append(l)
        right.append(r)

    # Equal representation of both candidates avoids a majority-direction bias.
    pool_left = np.concatenate([np.concatenate([l, l]) for l in left])
    pool_right = np.concatenate(
        [np.concatenate([r, r[::-1]]) for r in right]
    )
    try:
        F, _mask = cv2.findFundamentalMat(
            pool_left, pool_right, cv2.FM_RANSAC, 1.5, 0.999, 15000
        )
    except cv2.error as error:
        raise CornerCorrespondenceError(
            "左右棋盘格的极线模型求解失败；检查角点质量与姿态覆盖，"
            "原标定文件保持不变"
        ) from error
    if F is None or F.shape != (3, 3) or not np.isfinite(F).all():
        raise CornerCorrespondenceError(
            "多组棋盘格无法形成稳定的左右极线关系；请检查角点编号/样本姿态，"
            "原标定文件保持不变"
        )

    corrected, modes, scores, accepted, rejected = [], [], [], [], []
    for index, (l, r) in enumerate(zip(left, right)):
        direct = _sampson_px(F, l, r)
        reversed_180 = _sampson_px(F, l, r[::-1])
        d = float(np.median(direct))
        rev = float(np.median(reversed_180))
        reverse = rev < d
        winner, loser = (rev, d) if reverse else (d, rev)
        winning_errors = reversed_180 if reverse else direct
        valid_fraction = float(np.mean(winning_errors <= threshold_px * 2))
        scores.append((d, rev))

        # Absolute geometric plausibility + decisive superiority. Repeated
        # near-identical poses can be ambiguous even when RANSAC returns an F.
        if (winner > threshold_px or valid_fraction < 0.65 or
                loser - winner < max(2.0, 2.0 * winner)):
            message = (f"第 {index + 1} 组左右角点对应不可靠："
                       f"direct={d:.2f}px，reversed_180={rev:.2f}px")
            if min_good_pairs is None:
                raise CornerCorrespondenceError(
                    message + "；为避免错误三维坐标，本次未生成 NPZ"
                )
            rejected.append((index, message))
            continue

        accepted.append(index)
        corrected.append(
            (r[::-1] if reverse else r).copy().reshape(-1, 1, 2).astype(np.float32)
        )
        modes.append("reversed_180" if reverse else "direct")

    if min_good_pairs is not None and len(accepted) < min_good_pairs:
        messages = "；".join(reason for _, reason in rejected)
        raise CornerCorrespondenceError(
            f"角点对应仅有 {len(accepted)}/{min_good_pairs} 组可信；"
            f"失败样本：{messages}；原 NPZ 保持不变"
        )
    return corrected, {
        "accepted_indices": accepted,
        "rejected_indices": [index for index, _ in rejected],
        "modes": modes,
        "reversed_count": modes.count("reversed_180"),
        "median_sampson_px": float(np.median(
            np.concatenate([
                _sampson_px(F, l, r.reshape(-1, 2))
                for index, r in zip(accepted, corrected)
                for l in (left[index],)
            ])
        )),
        "pair_scores_px": scores,
    }
