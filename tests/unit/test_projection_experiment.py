"""Independent optical rigs and a local single-capture comparison."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import cv2
import numpy as np

from stereo_pose.calibration.camera_settings import compare_camera_modes
from stereo_pose.calibration.collection import RuntimeCalibration
from stereo_pose.calibration.correspondence import prepare_stereo_pairs
from stereo_pose.calibration.experiment import mapping_report, reference_errors
from stereo_pose.calibration.model_fit import fit_model
from stereo_pose.calibration.package import read_bundle, stereo_fingerprint, validate_stereo_bundle
from stereo_pose.config import load_config
from stereo_pose.diagnostics.snapshot import calibrate_bundle, compute_epipolar
from stereo_pose.geometry.projection import RawCamera, project_points, rectify_stereo
from stereo_pose.geometry.triangulation import StereoTriangulator
from stereo_pose.persistence.cleanup import cleanup_project
from tests.unit.test_calibration_capture_policy import _grid_det


SIZE = (1280, 800)
K1 = np.array([[590., 0., 645.], [0., 568., 388.], [0., 0., 1.]])
K2 = np.array([[631., 0., 626.], [0., 607., 405.], [0., 0., 1.]])
R = cv2.Rodrigues(np.array([.027, -.09, .013]))[0]
T = np.array([-205., 9., 5.])
D = {'pinhole': np.array([-.09, .02, .0006, -.0007, -.003]),
     'rational': np.array([.11, -.008, .001, -.0004, .001, .09, .004, .001]),
     'fisheye': np.array([.055, -.018, .006, -.0009])}
POINTS = np.array([[-300., -240., 680.], [480., 260., 740.], [0., 0., 950.]])


def observations(model, count=16):
    board = np.zeros((54, 3), np.float32)
    board[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2) * 30
    board[:, :2] -= np.mean(board[:, :2], axis=0)
    rng = np.random.default_rng(121)
    obj, left, right = [], [], []
    for index in range(count):
        # Spread whole poses across the field, with different tilt/roll/depth.
        x = (-320, 20, 320, 120)[index % 4]
        y = (-170, 0, 170)[(index // 4) % 3]
        r = rng.uniform(-.50, .50, 3)
        t = np.array([x, y, rng.uniform(570, 1020)])
        rr = cv2.Rodrigues(R @ cv2.Rodrigues(r)[0])[0]
        pl = project_points(model, board, K1, D[model], r, t)
        pr = project_points(model, board, K2, D[model], rr, R @ t + T)
        obj.append(board.copy())
        left.append(pl.reshape(-1, 1, 2).astype(np.float32))
        right.append(pr.reshape(-1, 1, 2).astype(np.float32))
    return obj, left, right


def raw_pair(model, xyz):
    return (project_points(model, xyz, K1, D[model]),
            project_points(model, xyz @ R.T + T, K2, D[model]))


class TestProjectionExperiment(TestCase):
    def test_fit_and_reconstruct_each_model_with_different_intrinsics_and_toe_in(self):
        for model in D:
            with self.subTest(model=model):
                result = fit_model(model, *observations(model), SIZE)
                bundle = {**result, 'image_size': np.array(SIZE)}
                validate_stereo_bundle(bundle)
                tri = StereoTriangulator(bundle)
                left, right = raw_pair(model, POINTS)
                for point, l, r in zip(POINTS, left, right):
                    out = tri.triangulate_with_quality(l, r)
                    self.assertIsNotNone(out)
                    np.testing.assert_allclose(out['xyz_mm'], tri.R1 @ point, atol=1.0)
                    self.assertLess(out['epipolar_error_px'], .2)
                    replay = compute_epipolar(calibrate_bundle(tri), l, r)
                    self.assertAlmostEqual(out['epipolar_error_px'], replay['epipolar_error_px'])

    def test_extreme_fisheye_correspondence_and_quality_scale(self):
        k1 = np.array([[325., 0., 639.], [0., 321., 398.], [0., 0., 1.]])
        k2 = np.array([[352., 0., 625.], [0., 336., 408.], [0., 0., 1.]])
        d = np.array([.015, -.002, .0002, -.00001])
        r = cv2.Rodrigues(np.array([.045, -.13, .02]))[0]
        t = np.array([-130., 4., 5.])
        board = np.zeros((54, 3), np.float32)
        board[:, :2] = (np.mgrid[0:9, 0:6].T.reshape(-1, 2) - [4, 2.5]) * 35
        rng = np.random.default_rng(99)
        obj, left, right = [], [], []
        for i in range(24):
            x = (-1250, -650, 0, 700, 1250, 400)[i % 6]
            y = (-620, -200, 210, 650)[i // 6]
            translation = np.array([x, y, rng.uniform(515, 760)])
            rotation = rng.uniform(-.42, .42, 3)
            rr = cv2.Rodrigues(r @ cv2.Rodrigues(rotation)[0])[0]
            obj.append(board)
            left.append(project_points('fisheye', board, k1, d, rotation, translation)
                        .reshape(-1, 1, 2).astype('f'))
            cr = project_points('fisheye', board, k2, d, rr, r @ translation + t)
            right.append((cr[::-1] if i % 5 == 0 else cr).reshape(-1, 1, 2).astype('f'))
        corrected, match = prepare_stereo_pairs(obj, left, right, SIZE, 12)
        self.assertEqual(match['coordinate_basis'], 'provisional_fisheye_undistorted_pixels')
        self.assertEqual(match['accepted_indices'], list(range(24)))
        self.assertEqual(match['reversed_count'], 5)
        bundle = fit_model('fisheye', obj, left, corrected, SIZE)
        tri = StereoTriangulator({**bundle, 'image_size': SIZE})
        raw_preview, _ = rectify_stereo(bundle, SIZE, 0)
        self.assertLess(raw_preview['P1'][0, 0], 100.)
        self.assertGreater(tri.P1[0, 0], 340.)
        xyz = np.array([[1150., 500., 550.], [-1050., -550., 600.]])
        l = project_points('fisheye', xyz, k1, d)
        rr = project_points('fisheye', xyz @ r.T + t, k2, d)
        for p, pl, pr in zip(xyz, l, rr):
            q = tri.triangulate_with_quality(pl, pr)
            np.testing.assert_allclose(q['xyz_mm'], tri.R1 @ p, atol=.1)
            ul, ur = q['rectified_uv_left'], q['rectified_uv_right']
            h = bundle['Q'] @ [*ul, ul[0] - ur[0], 1.]
            np.testing.assert_allclose(h[:3]/h[3], q['xyz_mm'], atol=.01)
        mapping = mapping_report(bundle, SIZE)
        self.assertGreater(mapping['left']['invalid_grid_count'], 0)
        self.assertIsNone(tri.triangulate([0, 0], rr[0]))

    def test_explicit_model_cannot_be_inferred_from_four_distortion_coefficients(self):
        fitted = fit_model('fisheye', *observations('fisheye'), SIZE)
        self.assertEqual(StereoTriangulator(fitted).camera_model, 'fisheye')
        legacy = {key: val for key, val in fitted.items() if key != 'camera_model'}
        self.assertEqual(StereoTriangulator(legacy).camera_model, 'pinhole')
        self.assertNotEqual(stereo_fingerprint(fitted), stereo_fingerprint(legacy))
        with self.assertRaisesRegex(ValueError, 'camera_model'):
            validate_stereo_bundle({**fitted, 'camera_model': np.array('unknown')})
        with self.assertRaisesRegex(ValueError, 'distortion'):
            validate_stereo_bundle({**fitted, 'D2': np.zeros(5)})

    def test_bad_edges_do_not_become_trusted_coordinates(self):
        k = np.array([[550., 0., 640.], [0., 550., 400.], [0., 0., 1.]])
        bad_d = np.array([-1., 0., 0., 0., 0.])
        cam = RawCamera('pinhole', k, bad_d, SIZE)
        rays, _ = cam.inverse([[640, 400], [1200, 700], [700, 401]])
        self.assertTrue(np.isfinite(rays[[0, 2]]).all())
        self.assertTrue(np.isnan(rays[1]).all())
        self.assertAlmostEqual(cam.limit, np.sqrt(1/3))
        fish = RawCamera('fisheye', k, [-1., 0., 0., 0.], SIZE)
        self.assertTrue(np.isnan(fish.inverse([[1200, 700]])[0]).all())
        self.assertTrue(np.isnan(fish.inverse([[np.nan, 0], [-1, 0]])[0]).all())

    def test_preview_framing_changes_pixels_without_changing_ideal_xyz(self):
        for model in ('pinhole', 'fisheye'):
            with self.subTest(model=model):
                bundle = fit_model(model, *observations(model), SIZE)
                wide, _ = rectify_stereo(bundle, SIZE, 1)
                base_tri = StereoTriangulator(bundle)
                wide_tri = StereoTriangulator({**bundle, **wide})
                self.assertNotAlmostEqual(base_tri.P1[0, 0], wide_tri.P1[0, 0], places=3)
                left, right = raw_pair(model, POINTS)
                for l, r in zip(left, right):
                    np.testing.assert_allclose(base_tri.R1.T @ base_tri.triangulate(l, r),
                                               wide_tri.R1.T @ wide_tri.triangulate(l, r), atol=1e-7)
                report = mapping_report(bundle, SIZE)
                self.assertIn('1', report['right']['rectifications'])
                self.assertEqual(report['framing_parameter'], 'balance' if model == 'fisheye' else 'alpha')

    def test_same_frozen_poses_reused_by_all_models_and_failure_does_not_replace_candidate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = load_config(None)
            stereo = {**cfg['stereo'], 'square_mm': 30., 'calibration_dir': str(root/'cal')}
            runtime = {**cfg['calibration_runtime'], 'session_dir': str(root/'sessions')}
            cal = RuntimeCalibration(stereo, runtime)
            cal.start()
            obj, left, right = observations('fisheye')
            right[4] = right[4][::-1].copy()
            raw_frame = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
            for l, r in zip(left, right):
                dl, dr = _grid_det(), _grid_det()
                dl['corners'], dr['corners'] = l.reshape(-1, 2), r.reshape(-1, 2)
                cal._save(raw_frame, raw_frame, dl, dr, 0.)
            with mock.patch.object(cal, '_load_points', wraps=cal._load_points) as load:
                reports = [cal.solve(model, stage=True, quality=cfg['quality']) for model in D]
                load.assert_called_once()
            self.assertEqual(len({r['dataset_sha256'] for r in reports}), 1)
            self.assertEqual(len({r['path'] for r in reports}), 3)
            indices = [(r['quality']['train']['sample_indices'], r['quality']['holdout']['sample_indices'])
                       for r in reports]
            self.assertTrue(all(indices[0] == split for split in indices))
            self.assertTrue(set(indices[0][0]).isdisjoint(indices[0][1]))
            self.assertTrue(all(r['quality']['holdout']['regional']['left'] for r in reports))
            self.assertTrue(all(Path(r['path']).is_file() for r in reports))
            self.assertFalse(list((root/'cal'/'auto').glob('*.npz')))
            reopened = RuntimeCalibration(stereo, runtime)
            reopened.open_dataset(cal.dataset.path)
            self.assertEqual(set(reopened.results), {(m, 0) for m in D})
            with mock.patch('stereo_pose.calibration.collection.fit_model', side_effect=cv2.error('synthetic solver failure')):
                with self.assertRaisesRegex(ValueError, 'synthetic solver failure'):
                    reopened.solve('fisheye', stage=True)
            self.assertEqual(reopened.results['fisheye', 0]['npz_sha256'], reports[2]['npz_sha256'])
            self.assertTrue((cal.session_dir/'left'/'000.png').is_file())
            self.assertEqual(cleanup_project(root/'cal', root/'sessions', root, failed_days=-1), [])

    def test_external_xyz_validation_scores_raw_left_and_keeps_rejected_points(self):
        bundle = fit_model('fisheye', *observations('fisheye'), SIZE)
        bundle['image_size'] = np.array(SIZE)
        left, right = raw_pair('fisheye', POINTS)
        row = dict(id='pointA', xyz_mm=POINTS[0].tolist(), uv_left=left[0].tolist(),
                   uv_right=right[0].tolist())
        quality = load_config(None)['quality']
        report = reference_errors(bundle, {'unit': 'mm', 'frame': 'camera_left',
            'points': [row, row, {**row, 'id': 'missing', 'uv_left': [-10, 0]}]}, quality)
        self.assertEqual(report['rejected_count'], 1)
        self.assertEqual(report['by_target']['pointA']['repeats_accepted'], 2)
        self.assertLess(report['norm_error_mm']['p95'], .5)
        self.assertIsNone(report['points'][-1]['measurement_mm'])

    def test_confirmed_camera_setting_mismatch_and_unknown_are_distinct(self):
        saved = {'modes': {'left': {'operator_confirmed': {'eis': 'off', 'fov': 'wide'}}}}
        unknown, mismatches = compare_camera_modes(saved, {'left': {'operator_confirmed': {'eis': 'on'}}})
        self.assertEqual(len(unknown), 1)
        self.assertEqual(len(mismatches), 1)
        self.assertIn('EIS', mismatches[0])
