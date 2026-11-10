"""Local reproducible calibration diagnostics and independent XYZ controls."""
from __future__ import annotations

import cv2
import numpy as np

from stereo_pose.calibration.package import validate_stereo_bundle
from stereo_pose.geometry.projection import (RawCamera, camera_model, project_points,
                                              rectification_maps, rectify_stereo)
from stereo_pose.geometry.triangulation import StereoTriangulator

REGIONS = ('center', 'middle', 'edge', 'corner_tl', 'corner_tr', 'corner_bl', 'corner_br')


def region_labels(uv, size):
    normalized = (2 * np.asarray(uv).reshape(-1, 2) / (np.asarray(size) - 1)) - 1
    radius = np.max(np.abs(normalized), axis=1)
    labels = np.full(len(radius), 'edge', dtype='U10')
    labels[radius < .70] = 'middle'
    labels[radius < .35] = 'center'
    for x, y, name in ((-1, -1, 'tl'), (1, -1, 'tr'), (-1, 1, 'bl'), (1, 1, 'br')):
        labels[(x * normalized[:, 0] >= .70) & (y * normalized[:, 1] >= .70)] = 'corner_' + name
    return labels


def stats(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not len(a):
        return {'n': 0, 'mean': None, 'p50': None, 'p95': None}
    p50, p95 = np.percentile(a, (50, 95))
    return {'n': len(a), 'mean': float(a.mean()), 'p50': float(p50), 'p95': float(p95),
            'low_sample': len(a) < 20}


def _grid(size, cols, rows):
    x, y = np.meshgrid(np.linspace(0, size[0]-1, cols), np.linspace(0, size[1]-1, rows))
    return np.c_[x.ravel(), y.ravel()]


def _mono_errors(obj, uv, cam):
    rays, _ = cam.inverse(uv)
    good = np.isfinite(rays).all(axis=1)
    out = np.full(len(rays), np.nan)
    if good.sum() >= 6:
        ok, r, t = cv2.solvePnP(obj[good], rays[good], np.eye(3), None)
        if ok:
            out[good] = np.linalg.norm(project_points(
                cam.model, obj[good], cam.K, cam.D, r, t) - uv[good], axis=1)
    return out


def regional_errors(bundle, objpoints, left, right, size, quality):
    """Per-view raw pixel residuals and runtime quality verdicts by raw region."""
    tri = StereoTriangulator(bundle)
    views = ([], [])
    for obj, pl, pr in zip(objpoints, left, right):
        pl, pr = (np.asarray(p, dtype=float).reshape(-1, 2) for p in (pl, pr))
        ul, ur = tri.rectify_pair(pl, pr)
        epi = np.abs(ul[:, tri.epipolar_axis] - ur[:, tri.epipolar_axis])
        valid = np.isfinite(epi) & (epi <= quality['max_epipolar_error_px'])
        ids = np.flatnonzero(valid)
        if len(ids):
            h = cv2.triangulatePoints(tri.P1, tri.P2, ul[ids].T, ur[ids].T).T
            with np.errstate(divide='ignore', invalid='ignore'):
                xyz = h[:, :3] / h[:, 3:]
                depth = xyz[:, 2]
                proj_l, proj_r = h @ tri.P1.T, h @ tri.P2.T
                error = np.maximum(np.linalg.norm(proj_l[:, :2]/proj_l[:, 2:] - ul[ids], axis=1),
                                   np.linalg.norm(proj_r[:, :2]/proj_r[:, 2:] - ur[ids], axis=1))
            valid[ids] &= (np.isfinite(xyz).all(axis=1) &
                           (depth >= quality['min_depth_mm']) & (depth <= quality['max_depth_mm']) &
                           (error <= quality['max_reprojection_error_px']))
            score = np.exp(-epi[ids] / quality['max_epipolar_error_px']
                           - error / quality['max_reprojection_error_px'])
            valid[ids] &= score >= quality.get('min_quality_score', 0.)
        for values, uv, cam in zip(views, (pl, pr), (tri.raw_left, tri.raw_right)):
            values.append((uv, _mono_errors(obj, uv, cam), epi, valid))
    report = {}
    cells = (12, 8)
    centers = (_grid(cells, *cells) + .5) / cells * (np.asarray(size) - 1)
    cell_regions = region_labels(centers, size)
    for side, values in zip(('left', 'right'), views):
        if not values:
            continue
        uv, mono, epi, valid = (np.concatenate(a) for a in zip(*values))
        labels = region_labels(uv, size)
        occupied = np.clip((uv / np.asarray(size) * cells).astype(int), 0, np.array(cells)-1)
        occupied_ids = occupied[:, 1] * cells[0] + occupied[:, 0]
        report[side] = {}
        for name in REGIONS:
            mask = labels == name
            possible = np.flatnonzero(cell_regions == name)
            coverage = len(np.intersect1d(occupied_ids, possible)) / len(possible) if len(possible) else None
            report[side][name] = dict(count=int(mask.sum()), grid_coverage=coverage,
                monocular_reprojection_px=stats(mono[mask]), stereo_epipolar_px=stats(epi[mask]),
                rejected_fraction=float(1-valid[mask].mean()) if mask.any() else None)
    return report


def mapping_report(bundle, size):
    """Audit sensor grid, central radial branch and output framing separately."""
    validate_stereo_bundle(bundle)
    model = camera_model(bundle)
    uv = _grid(size, 33, 25)
    framings = [('artifact', bundle, (None, None))]
    if 'R' in bundle and 'T' in bundle:
        for framing in (0, 1):
            try:
                matrices, rois = rectify_stereo(bundle, size, framing)
                framings.append((str(framing), {**bundle, **matrices}, rois))
            except (cv2.error, ValueError) as error:
                framings.append((str(framing), {'error': str(error)}, (None, None)))
    out = {'sampling_grid': [33, 25], 'framing_parameter': 'balance' if model == 'fisheye' else 'alpha'}
    for i, side in enumerate(('left', 'right'), 1):
        K, D = bundle[f'K{i}'], bundle[f'D{i}']
        cam = RawCamera(model, K, D, size)
        rays, errors = cam.inverse(uv)
        finite = np.isfinite(rays).all(axis=1)
        ideal_radius = np.linalg.norm(rays, axis=1)
        ray_angle = np.degrees(np.arctan(ideal_radius))
        raw_radius = np.linalg.norm(uv - K[:2, 2], axis=1)
        if model == 'fisheye':
            finite_limit = cam.limit < np.pi/2
            limit_ray = np.tan(cam.limit * (1-1e-7))
        else:
            finite_limit = np.isfinite(cam.limit)
            limit_ray = cam.limit * (1-1e-7)
        # Profile in ideal normalized radius; sample all four radial directions
        # since non-radial terms and unequal fx/fy make pixel radii asymmetric.
        corner_scale = np.max(np.linalg.norm((uv-K[:2, 2])/np.diag(K)[:2], axis=1))
        visible_scale = np.max(ideal_radius[finite], initial=0.)
        profile_limit = max(float(corner_scale), float(visible_scale))
        if finite_limit:
            profile_limit = min(profile_limit, float(limit_ray))
        radial = np.linspace(0., profile_limit, 101)
        profile = []
        for x, y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            projected = project_points(model, np.c_[x*radial, y*radial, np.ones(len(radial))], K, D)
            radii = np.linalg.norm(projected - K[:2, 2], axis=1)
            profile.append({'direction': [x, y],
                            'raw_radius_px': [float(r) if np.isfinite(r) else None for r in radii]})
        bad = np.flatnonzero(~finite)
        out[side] = {
            'invalid_grid_count': len(bad),
            'invalid_raw_pixels': uv[bad].tolist(), 'roundtrip_px': stats(errors),
            'invalid_samples': [{'uv': uv[i].tolist(),
                'roundtrip_px': float(errors[i]) if np.isfinite(errors[i]) else None}
                for i in bad],
            'central_branch_limit': float(cam.limit) if finite_limit else None,
            'central_branch_limit_unit': 'radians' if model == 'fisheye' else 'normalized_ray_radius',
            'radial_profile': {'ideal_radius': radial.tolist(), 'directions': profile},
            'raw_radius_to_angle': np.c_[raw_radius[finite], ray_angle[finite]].tolist(),
            'rectifications': {},
        }
        for name, geometry, rois in framings:
            if 'error' in geometry:
                out[side]['rectifications'][name] = geometry
                continue
            R, P = geometry[f'R{i}'], geometry[f'P{i}']
            rect = cam.rectify(uv, R, P)
            inside = np.all((rect >= 0) & (rect <= np.asarray(size)-1), axis=1)
            # Sample output pixels directly, without allocating a full 4K map.
            output_uv = uv
            homogeneous = np.c_[output_uv, np.ones(len(output_uv))]
            direction = homogeneous @ np.linalg.inv(P[:, :3]).T @ R
            mapped = project_points(model, direction, K, D)
            inverse_mapped, _ = cam.inverse(mapped)
            with np.errstate(invalid='ignore', divide='ignore'):
                expected = direction[:, :2] / direction[:, 2:]
            forward = (direction[:, 2] > 0) & (np.linalg.norm(inverse_mapped-expected, axis=1) < 1e-2)
            out[side]['rectifications'][name] = {
                'virtual_focal_px': [float(P[0, 0]), float(P[1, 1])], 'P': P.tolist(),
                'roi': rois[i-1], 'raw_grid_visible_fraction': float(inside.mean()),
                'output_grid_in_sensor_fraction': float(forward.mean()),
                'invalid_output_pixels': output_uv[~forward].tolist(),
                'max_valid_raw_ray_angle_deg': float(np.max(ray_angle[inside])) if inside.any() else None,
            }
    return out


def framing_errors(bundle, left, right, size):
    report = {}
    for framing in (0, 1):
        try:
            matrices, _ = rectify_stereo(bundle, size, framing)
            tri = StereoTriangulator({**bundle, **matrices})
            l, r = np.concatenate(left), np.concatenate(right)
            ul, ur = tri.rectify_pair(l, r)
            axis = tri.epipolar_axis
            epi = np.abs(ul[:, axis] - ur[:, axis])
            angles = [np.arctan((uv[:, axis] - P[axis, 2]) / P[axis, axis])
                      for uv, P in ((ul, tri.P1), (ur, tri.P2))]
            good = np.isfinite(epi)
            ul, ur = ul[good], ur[good]
            with np.errstate(invalid='ignore', divide='ignore'):
                h = cv2.triangulatePoints(tri.P1, tri.P2, ul.T, ur.T).T if len(ul) else np.empty((0, 4))
                pl, pr = h @ tri.P1.T, h @ tri.P2.T
                reproj = .5 * (np.linalg.norm(pl[:, :2]/pl[:, 2:] - ul, axis=1)
                               + np.linalg.norm(pr[:, :2]/pr[:, 2:] - ur, axis=1))
            report[str(framing)] = {'epipolar_px': stats(epi),
                                    'epipolar_plane_angle_mrad': stats(1000 * np.abs(angles[0] - angles[1])),
                                    'rectified_reprojection_px': stats(reproj),
                                    'invalid_count': int((~good).sum())}
        except (cv2.error, ValueError, np.linalg.LinAlgError) as error:
            report[str(framing)] = {'error': str(error)}
    return report


def preview_pair(frames, tri, maps=None):
    if maps is None:
        maps = [rectification_maps(tri.camera_model, getattr(tri, f'K{i}'), getattr(tri, f'D{i}'),
                                   getattr(tri, f'R{i}'), getattr(tri, f'P{i}'), tri.image_size)
                for i in (1, 2)]
    return tuple(cv2.remap(frame, *m, cv2.INTER_LINEAR) for frame, m in zip(frames, maps)), maps


def reference_errors(bundle, references, quality, registration=None):
    """Compare external ground truth, independent of both the fit and W inputs."""
    from stereo_pose.quality.scoring import classify_joint

    if references.get('unit') != 'mm' or references.get('frame') not in ('camera_left', 'world'):
        raise ValueError('reference coordinates need unit=mm and frame=camera_left or world')
    if references['frame'] == 'world':
        if registration is None or references.get('world_name') != registration['name']:
            raise ValueError('reference frame needs a valid W registration with the same world_name')
    else:
        registration = None
    tri = StereoTriangulator(bundle)
    results = []
    groups = {}
    for row in references['points']:
        identity = str(row['id'])
        truth = np.asarray(row['xyz_mm'], dtype=float)
        left, right = (np.asarray(row[f'uv_{side}'], dtype=float) for side in ('left', 'right'))
        if truth.shape != (3,) or left.shape != (2,) or right.shape != (2,) or not np.isfinite(truth).all():
            raise ValueError(f'invalid reference point: {identity}')
        point = tri.triangulate_with_quality(left, right)
        verdict = classify_joint(identity, conf_l=1., conf_r=1., keypoint_confidence=0.,
                                 geometry=point, qcfg=quality)
        item = dict(id=identity, xyz_truth_mm=truth.tolist(), accepted=verdict.accepted,
                    reason=verdict.state, detail=verdict.detail, measurement_mm=None, error_mm=None)
        if verdict.accepted:
            xyz = point['xyz_mm']
            xyz = registration['transform'].apply(xyz) if registration else tri.R1.T @ xyz
            delta = xyz - truth
            groups.setdefault(identity, []).append((xyz, delta))
            item.update(measurement_mm=xyz.tolist(), error_mm=delta.tolist(),
                        norm_error_mm=float(np.linalg.norm(delta)),
                        region_left=region_labels(left, tri.image_size)[0],
                        region_right=region_labels(right, tri.image_size)[0])
        results.append(item)
    by_id = {}
    for name, repeats in groups.items():
        xyz, delta = (np.asarray(a) for a in zip(*repeats))
        by_id[name] = {'repeats_accepted': len(xyz), 'signed_bias_xyz_mm': delta.mean(0).tolist(),
                       'repeatability_std_xyz_mm': xyz.std(0, ddof=1).tolist() if len(xyz) > 1 else None,
                       'norm_error_mm': stats(np.linalg.norm(delta, axis=1))}
    return {'validation_type': 'independent_xyz_reference', 'frame': references['frame'],
            'world_name': references.get('world_name'), 'points': results, 'by_target': by_id,
            'norm_error_mm': stats([row['norm_error_mm'] for row in results if row['accepted']]),
            'rejected_count': sum(not row['accepted'] for row in results)}


def write_mapping_plot(path, report, size):
    """Save the raw-radius/ray-angle scatter and invalid sensor grid for each view."""
    canvas = np.full((540, 1120, 3), 250, dtype=np.uint8)
    color, muted, invalid = (124, 91, 24), (100, 100, 100), (46, 58, 210)
    def label(value, xy, scale=.55):
        cv2.putText(canvas, value, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (40, 40, 40), 1, cv2.LINE_AA)

    for row, side in enumerate(('left', 'right')):
        y = row*270
        label(f'{side.upper()} | raw radius vs. ray angle', (40, y+30), .65)
        label('Raw sensor grid | failed inverse in red', (605, y+30), .65)
        chart_x, chart_y, width, height = 72, y+45, 460, 168
        cv2.rectangle(canvas, (chart_x, chart_y), (chart_x+width, chart_y+height), muted, 1)
        label('90 deg', (6, chart_y+5))
        label('0 deg', (12, chart_y+height+4))
        label('0 px', (chart_x, chart_y+height+22))
        max_radius = float(np.hypot(*size))
        label(f'{max_radius:.0f} raw px', (chart_x+width-95, chart_y+height+22))
        for radius, angle in report[side]['raw_radius_to_angle']:
            x = chart_x + min(width, round(width * radius/max_radius))
            pt_y = chart_y + height - round(height * angle/90)
            cv2.circle(canvas, (x, pt_y), 1, color, -1)
        left, top = 620, y+45
        sensor_width = min(450, round(height * size[0]/size[1]))
        cv2.rectangle(canvas, (left, top), (left+sensor_width, top+height), muted, 1)
        for u, v in report[side]['invalid_raw_pixels']:
            x = left + round(sensor_width*u/(size[0]-1))
            pt_y = top + round(height*v/(size[1]-1))
            cv2.circle(canvas, (x, pt_y), 2, invalid, -1)
        label(f'{report[side]["invalid_grid_count"]} / 825 samples rejected', (left, top+height+22))
    ok, encoded = cv2.imencode('.png', canvas)
    if not ok:
        raise OSError('could not encode calibration mapping plot')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded.tobytes())
