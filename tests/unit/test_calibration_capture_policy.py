"""Runtime calibration capture policy tests.

RC2 behavior:
- auto capture still requires the stability gate;
- SPACE/manual force capture bypasses only the stability gate;
- both cameras must still detect the full board and satisfy minimum area.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import cv2

from stereo_pose.calibration.collection import RuntimeCalibration
from stereo_pose.calibration.correspondence import normalize_stereo_pairs, CornerCorrespondenceError


def _calibrator(root: Path) -> RuntimeCalibration:
    stereo = {
        "board_cols": 9,
        "board_rows": 6,
        "square_mm": 25.0,
        "calibration_dir": str(root / "calibrations"),
    }
    runtime = {
        "session_dir": str(root / "sessions"),
        "auto_capture": True,
        "auto_capture_interval_s": 0.7,
        "min_pairs_to_solve": 12,
        "target_pairs": 24,
        "recommended_readiness": 75,
        "min_board_area_ratio": 0.012,
        "diversity_threshold": 0.12,
        "stable_dwell_s": 0.30,
        "stable_min_frames": 3,
        "stable_corner_motion_px": 5.0,
        "robust_prune": True,
        "prune_min_epipolar_px": 0.8,
        "prune_max_epipolar_px": 2.5,
        "max_prune_fraction": 0.25,
        "keep_images_after_success": False,
    }
    return RuntimeCalibration(stereo, runtime)


def _det(area=0.02):
    corners = np.zeros((54, 2), dtype=np.float32)
    return {
        "corners": corners,
        "center": (0.5, 0.5),
        "area_ratio": float(area),
        "angle_deg": 0.0,
        "sharpness": 100.0,
    }


class TestCalibrationCapturePolicy(unittest.TestCase):
    def test_manual_force_capture_bypasses_stability_gate(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(), _det()]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 9.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=True)

            save.assert_called_once()
            self.assertTrue(result["captured"])
            self.assertFalse(result["stable"])
            self.assertTrue(result["good_area"])

    def test_auto_capture_still_requires_stability(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(), _det()]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 9.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=False)

            save.assert_not_called()
            self.assertFalse(result["captured"])

    def test_manual_force_capture_still_rejects_too_small_board(self):
        with tempfile.TemporaryDirectory() as d:
            cal = _calibrator(Path(d))
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            detections = [_det(area=0.005), _det(area=0.005)]
            with (
                mock.patch.object(cal, "_detect", side_effect=detections),
                mock.patch.object(cal, "_update_stability", return_value=(False, 2.0, 0.1)),
                mock.patch.object(cal, "_save") as save,
            ):
                result = cal.process(frame, frame, force_capture=True)

            save.assert_not_called()
            self.assertFalse(result["captured"])
            self.assertFalse(result["good_area"])


def _grid_det(dx=0., dy=0., angle=0., area=0.04, reverse=False):
    xy=np.mgrid[0:9,0:6].T.reshape(-1,2).astype(np.float32)*16+[64.,40.]
    center=xy.mean(axis=0)
    rad=np.deg2rad(angle);R=np.array([[np.cos(rad),-np.sin(rad)],[np.sin(rad),np.cos(rad)]])
    xy=(xy-center)@R.T+center+[dx,dy]
    if reverse:xy=xy[::-1].copy()
    return {'corners':xy.astype(np.float32),'center':tuple(xy.mean(axis=0)/[320,240]),
            'area_ratio':area,'angle_deg':angle+(180 if reverse else 0),'sharpness':100.}


class TestAdaptiveAutoCapture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.cal=_calibrator(self.root);self.cal.start()
        self.frame=np.zeros((240,320,3),np.uint8)

    def observe(self,t,left=None,right=None,*,missing=None,force=False):
        left=_grid_det() if left is None else left
        right=_grid_det(dx=-12) if right is None else right
        if missing in ('left','both'):left=None
        if missing in ('right','both'):right=None
        with mock.patch.object(self.cal,'_detect',side_effect=[left,right]):
            return self.cal.process(self.frame,self.frame,force_capture=force,timestamp_s=t)

    def static_rate(self,hz):
        captured=[]
        for i in range(3*hz+1):
            result=self.observe(i/hz)
            if result['captured']:captured.append(i/hz)
        self.assertEqual(len(captured),1)
        self.assertGreaterEqual(captured[0]+1e-9,max(.30,2/hz))
        self.assertLessEqual(captured[0],max(.30,2/hz)+1/hz+1e-9)
        self.assertAlmostEqual(result['effective_detection_hz'],hz)
        self.assertEqual(result['capture_reason'],'duplicate_pose')

    def test_30_Hz_static_board_auto_captures(self):self.static_rate(30)
    def test_5_Hz_static_board_auto_captures(self):self.static_rate(5)
    def test_2_Hz_static_board_auto_captures(self):self.static_rate(2)

    def test_real_OpenCV_SB_detects_and_auto_captures_synthetic_checkerboard(self):
        frame=np.full((240,320,3),255,np.uint8)
        for row in range(7):
            for col in range(10):
                if (row+col)%2 == 0:
                    frame[40+row*18:40+(row+1)*18,64+col*18:64+(col+1)*18]=0
        for t in (0.,.2,.4):
            result=self.cal.process(frame,frame,timestamp_s=t)
        self.assertTrue(result['detected_left']);self.assertTrue(result['detected_right'])
        self.assertTrue(result['captured']);self.assertEqual(len(self.cal.samples),1)

    def test_continuous_motion_in_either_view_never_captures(self):
        for hz in (2,5,30):
            for side in ('left','right','both'):
                with self.subTest(hz=hz,side=side):
                    self.cal.start()
                    for i in range(3*hz+1):
                        t=i/hz;dx=10*t
                        left=_grid_det(dx=dx if side in ('left','both') else 0.)
                        right=_grid_det(dx=-12+(dx if side in ('right','both') else 0.))
                        self.assertFalse(self.observe(t,left,right)['captured'])
                    self.assertEqual(len(self.cal.samples),0)

    def test_consistent_rotation_never_captures(self):
        for i in range(31):
            self.observe(i/5,_grid_det(angle=i*3),_grid_det(dx=-12,angle=i*3))
        self.assertEqual(len(self.cal.samples),0)

    def test_slow_coherent_drift_has_a_visible_reason_below_5px_excursion(self):
        for i in range(3):
            result=self.observe(i/5,_grid_det(dx=i*2),_grid_det(dx=-12+i*2))
        self.assertFalse(result['captured'])
        self.assertLess(result['stability_motion_px'],5.)
        self.assertEqual(result['motion_cause'],'coherent_drift')

    def test_static_pixel_jitter_at_slow_and_fast_rates_is_allowed(self):
        rng=np.random.default_rng(4)
        for hz in (2,30):
            with self.subTest(hz=hz):
                self.cal.start()
                for i in range(3*hz+1):
                    left,right=_grid_det(),_grid_det(dx=-12)
                    left['corners']+=rng.normal(0,.25,(54,2)).astype(np.float32)
                    right['corners']+=rng.normal(0,.25,(54,2)).astype(np.float32)
                    self.observe(i/hz,left,right)
                self.assertEqual(len(self.cal.samples),1)

    def test_short_detection_loss_does_not_count_blind_time_as_stability(self):
        self.observe(0.)
        self.observe(.1)
        missed=self.observe(.2,missing='right')
        self.assertFalse(missed['captured']);self.assertEqual(missed['capture_reason'],'detection_failed')
        self.assertTrue(missed['detected_left']);self.assertFalse(missed['detected_right'])
        reacquired=self.observe(.3)
        self.assertFalse(reacquired['captured'])
        self.assertAlmostEqual(reacquired['stable_dwell_s'],.1)
        self.assertFalse(self.observe(.4)['captured'])
        self.assertTrue(self.observe(.5)['captured'])

    def test_long_detection_loss_requires_fresh_observations(self):
        self.observe(0.);self.observe(.2)
        self.observe(2.,missing='both')
        fresh=self.observe(2.5)
        self.assertFalse(fresh['captured']);self.assertEqual(fresh['stability_observations'],1)
        self.assertFalse(self.observe(3.)['captured'])
        self.assertTrue(self.observe(3.5)['captured'])

    def test_large_valid_detection_gap_also_resets_without_explicit_failure(self):
        self.observe(0.);self.observe(.2)
        result=self.observe(2.)
        self.assertFalse(result['captured']);self.assertEqual(result['stability_observations'],1)

    def test_same_pose_is_not_repeated_even_with_zero_diversity_threshold(self):
        self.cal.diversity_threshold=0.
        for i in range(101):self.observe(i/5)
        self.assertEqual(len(self.cal.samples),1)

    def test_new_pose_captures_again_after_motion_stops(self):
        for i in range(7):self.observe(i/5)
        self.assertEqual(len(self.cal.samples),1)
        for i in range(10,20):self.observe(i/5,_grid_det(dx=65),_grid_det(dx=53))
        self.assertEqual(len(self.cal.samples),2)
        self.assertEqual(self.cal.current['capture_reason'],'duplicate_pose')

    def test_180_degree_detector_order_flips_do_not_fake_motion_or_diversity(self):
        for i in range(16):
            self.observe(i/5,_grid_det(reverse=bool(i%2)),_grid_det(dx=-12,reverse=bool((i+1)%2)))
        self.assertEqual(len(self.cal.samples),1)
        self.assertTrue(self.cal.current['stable'])
        self.assertLess(self.cal.current['stability_motion_px'],1e-5)

    def test_unrecognized_corner_permutation_is_not_stable(self):
        self.observe(0.);self.observe(.1)
        left=_grid_det();left['corners']=np.roll(left['corners'],1,axis=0)
        result=self.observe(.4,left,_grid_det(dx=-12))
        self.assertFalse(result['captured']);self.assertFalse(result['stable'])
        self.assertEqual(result['stability_reason'],'corner_order_jump')

    def test_persistently_scrambled_grid_never_becomes_new_stability_evidence(self):
        for i in range(31):
            left=_grid_det();left['corners']=np.roll(left['corners'],1,axis=0)
            result=self.observe(i/5,left,_grid_det(dx=-12))
            self.assertFalse(result['captured'])
            self.assertEqual(result['stability_reason'],'corner_order_jump')
        self.assertEqual(len(self.cal.samples),0)

    def test_even_slower_consistent_cadence_does_not_deadlock_forever(self):
        for i in range(6):self.observe(i*2.)
        self.assertEqual(len(self.cal.samples),1)
        self.assertAlmostEqual(self.cal.current['effective_detection_hz'],.5)

    def test_same_timestamp_never_accumulates_three_observations(self):
        for i in range(30):self.observe(0.)
        self.assertEqual(len(self.cal.samples),0)
        self.assertEqual(self.cal.current['stability_observations'],1)

    def test_new_default_is_merged_into_existing_config_without_rewriting_it(self):
        import json
        from stereo_pose.config import load_config, validate_config, ConfigError
        path=self.root/'config.json'
        path.write_text(json.dumps({'calibration_runtime':{'stable_corner_motion_px':5.},'user':'keep'}))
        before=path.read_bytes();cfg=load_config(path)
        self.assertEqual(cfg['calibration_runtime']['stable_loss_grace_s'],1.25)
        self.assertEqual(cfg['calibration_runtime']['stable_corner_motion_px'],5.)
        self.assertEqual(path.read_bytes(),before)
        defaults=json.loads((Path(__file__).parents[2]/'configs/default.json').read_text())
        self.assertEqual(defaults['calibration_runtime'],load_config(None)['calibration_runtime'])
        cfg['calibration_runtime']['stable_loss_grace_s']=0
        with self.assertRaises(ConfigError):validate_config(cfg)

    def test_sampling_interval_and_diversity_have_explicit_reasons(self):
        self.cal.interval=5.
        for i in range(7):self.observe(i/5)
        for i in range(10,16):self.observe(i/5,_grid_det(dx=65),_grid_det(dx=53))
        result=self.cal.current
        self.assertTrue(result['stable']);self.assertEqual(result['capture_reason'],'waiting_interval')
        self.assertGreater(result['interval_remaining_s'],0)
        self.observe(6.,_grid_det(dx=65),_grid_det(dx=53))
        self.observe(6.2,_grid_det(dx=65),_grid_det(dx=53))
        self.assertTrue(self.observe(6.4,_grid_det(dx=65),_grid_det(dx=53))['captured'])

    def test_manual_uses_current_pair_without_redetection_and_warns_on_duplicate(self):
        self.cal.auto_capture=False
        result=self.observe(0.)
        self.assertFalse(result['stable']);self.assertEqual(result['capture_reason'],'auto_disabled')
        with mock.patch.object(self.cal,'_detect',side_effect=AssertionError('duplicate detection')):
            result=self.cal.capture_current()
        self.assertTrue(result['captured']);self.assertEqual(len(self.cal.samples),1)
        result=self.observe(.1,force=True)
        self.assertTrue(result['captured']);self.assertTrue(result['manual_duplicate'])
        self.assertEqual(len(self.cal.samples),2)

    def test_SPACE_after_auto_capture_warns_and_still_preserves_force_semantics(self):
        for t in (0.,.2,.4):self.observe(t)
        self.assertEqual(len(self.cal.samples),1)
        with mock.patch.object(self.cal,'_detect',side_effect=AssertionError('redetection')):
            result=self.cal.capture_current()
            self.assertTrue(result['captured']);self.assertTrue(result['manual_duplicate'])
            self.assertEqual(len(self.cal.samples),2)
            result=self.cal.capture_current()
            self.assertTrue(result['manual_duplicate']);self.assertEqual(len(self.cal.samples),3)

    def test_manual_rejects_missing_or_small_board_and_no_stale_capture(self):
        for kwargs in ({'missing':'right'},{'left':_grid_det(area=.001)}):
            with self.subTest(kwargs=kwargs):
                self.observe(0.,**kwargs)
                result=self.cal.capture_current()
                self.assertFalse(result['captured'])
        self.cal.stop_without_delete()
        self.assertFalse(self.cal.capture_current()['captured'])
        self.assertEqual(len(self.cal.samples),0)

    def test_insufficient_evidence_is_not_reported_as_board_motion(self):
        result=self.observe(0.)
        self.assertEqual(result['capture_reason'],'insufficient_observations')
        with mock.patch('cv2.putText',wraps=cv2.putText) as draw:
            canvas=self.cal.draw_overlay(np.zeros((240,640,3),np.uint8))
        labels=[call.args[1] for call in draw.call_args_list]
        self.assertTrue(any('WAIT OBSERVATIONS' in text for text in labels))
        self.assertTrue(any('effective' in text.lower() and 'Hz' in text for text in labels))
        self.assertFalse(any('WAITING FOR STILLNESS' in text for text in labels))
        self.assertGreater(canvas.shape[0],240)

    def test_failed_image_write_is_not_counted_as_capture(self):
        with mock.patch('cv2.imwrite',side_effect=[True,False]):
            result=self.observe(0.,force=True)
        self.assertFalse(result['captured']);self.assertEqual(len(self.cal.samples),0)
        self.assertEqual(result['capture_reason'],'capture_failed')


class TestCalibrationSolveRegression(unittest.TestCase):
    def test_existing_solver_complete_NPZ_and_reload_on_synthetic_rig(self):
        from stereo_pose.calibration.package import read_bundle, load_readout_registration
        from stereo_pose.geometry import StereoTriangulator
        with tempfile.TemporaryDirectory() as tmp:
            cal=_calibrator(Path(tmp));cal.start()
            K=np.array([[900.,0,640],[0,900,360],[0,0,1]])
            obj=np.zeros((54,3),np.float32);obj[:,:2]=np.mgrid[0:9,0:6].T.reshape(-1,2)*25
            rng=np.random.default_rng(8);objs=[];left=[];right=[];paths=[]
            Rst=cv2.Rodrigues(np.array([.01,-.02,.005]))[0];Tst=np.array([-300.,1.5,2.])
            for i in range(16):
                rvec=rng.uniform(-.35,.35,3);tvec=np.array([rng.uniform(-120,100),rng.uniform(-90,40),rng.uniform(850,1400)])
                Rpose=cv2.Rodrigues(rvec)[0]
                cl=cv2.projectPoints(obj,rvec,tvec,K,np.zeros(5))[0].astype(np.float32)
                rr=cv2.Rodrigues(Rst@Rpose)[0];tr=Rst@tvec+Tst
                cr=cv2.projectPoints(obj,rr,tr,K,np.zeros(5))[0].astype(np.float32)
                objs.append(obj.copy());left.append(cl);right.append(cr);paths.append((Path(tmp)/'l.png',Path(tmp)/'r.png'))
                cal.samples.append({'left':_grid_det(),'right':_grid_det(dx=-12),'descriptor':np.zeros(10)})
            with mock.patch.object(cal,'_load_points',return_value=(objs,left,right,paths,(1280,720))):
                result=cal.solve()
            self.assertFalse(cal.active);self.assertEqual(result['sample_count'],16)
            self.assertLess(result['stereo_rms'],.01)
            bundle=read_bundle(result['path'])
            self.assertTrue(all(k in bundle for k in ('K1','D1','K2','D2','R','T','R1','R2','P1','P2','Q')))
            np.testing.assert_allclose(bundle['T'].reshape(-1),Tst,atol=.05)
            tri=StereoTriangulator(result['path'])
            point=np.array([[100.,40.,1100.]])
            pl=cv2.projectPoints(point,np.zeros(3),np.zeros(3),K,np.zeros(5))[0].reshape(2)
            pr=cv2.projectPoints(point,cv2.Rodrigues(Rst)[0],Tst,K,np.zeros(5))[0].reshape(2)
            actual=tri.triangulate(pl,pr)
            np.testing.assert_allclose(actual,bundle['R1']@point[0],atol=.1)
            registration,warnings=load_readout_registration(result['path'],(1280,720))
            self.assertFalse(warnings);self.assertEqual(registration['metadata']['mode'],'camera_midpoint')


class TestStereoCheckerboardCorrespondence(unittest.TestCase):
    """Synthetic 9x6 board, different intrinsics and deliberately converged rigs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.obj = np.zeros((54,3),np.float32)
        self.obj[:,:2] = np.mgrid[0:9,0:6].T.reshape(-1,2) * 25
        # Intentionally different focal lengths and an angled 2-camera setup.
        self.K1 = np.array([[850.,0,625],[0,820,350],[0,0,1]])
        self.K2 = np.array([[1190.,0,615],[0,1080,340],[0,0,1]])
        self.D1 = np.array([-.12,.03,0.,0.,0.])
        self.D2 = np.array([-.18,.06,0.,0.,0.])
        self.R = cv2.Rodrigues(np.array([.05,.30,.07]))[0]
        self.T = np.array([-190.,20.,13.])

    def observations(self, reverse=(), n=12, *, repeat=False, seed=5):
        rng=np.random.default_rng(seed)
        original_right=[]; left=[]; right=[]
        for i in range(n):
            rvec=rng.uniform(-.29,.29,3)
            trans=np.array([rng.uniform(-150,170),rng.uniform(-110,30),rng.uniform(950,1600)])
            if repeat:
                rvec=np.array([.11,-.17,.05])
                trans=np.array([-25.,-20.,1200.])
            pose=cv2.Rodrigues(rvec)[0]
            l=cv2.projectPoints(self.obj,rvec,trans,self.K1,self.D1)[0]
            rv2=cv2.Rodrigues(self.R@pose)[0]
            r=cv2.projectPoints(self.obj,rv2,self.R@trans+self.T,self.K2,self.D2)[0]
            if not repeat:
                l+=rng.normal(0,.18,l.shape).astype(np.float32)
                r+=rng.normal(0,.18,r.shape).astype(np.float32)
            original_right.append(r.copy())
            left.append(l)
            right.append(r[::-1].copy() if i in reverse else r.copy())
        return left,right,original_right

    def test_direct_correspondence_with_different_camera_intrinsics(self):
        left,right,expected=self.observations()
        aligned,diag=normalize_stereo_pairs(left,right)
        self.assertEqual(diag['reversed_count'],0)
        self.assertEqual(diag['modes'],['direct']*12)
        self.assertLess(diag['median_sampson_px'],1)
        for a,b in zip(aligned,expected):
            np.testing.assert_allclose(a,b,atol=.0001)

    def test_mixed_180_flips_recover_exact_physical_corner_pairs(self):
        reversals={1,4,8}
        left,right,expected=self.observations(reverse=reversals)
        aligned,diag=normalize_stereo_pairs(left,right)
        self.assertEqual(diag['reversed_count'],len(reversals))
        self.assertEqual({i for i,mode in enumerate(diag['modes']) if mode=='reversed_180'},reversals)
        for a,b in zip(aligned,expected):
            np.testing.assert_allclose(a,b,atol=.0001)

    def test_all_right_cameras_reversed_still_recovers_common_geometry(self):
        left,right,expected=self.observations(reverse=set(range(12)))
        aligned,diag=normalize_stereo_pairs(left,right)
        self.assertEqual(diag['reversed_count'],12)
        for a,b in zip(aligned,expected):
            np.testing.assert_allclose(a,b,atol=.0001)

    def test_unrecognized_permutation_or_ambiguous_single_pose_rejected(self):
        left,right,_=self.observations()
        invalid=list(right)
        invalid[5]=np.roll(right[5],8,axis=0)
        with self.assertRaisesRegex(CornerCorrespondenceError,'第 6 组'):
            normalize_stereo_pairs(left,invalid)
        same_left,same_right,_=self.observations(repeat=True)
        with self.assertRaisesRegex(CornerCorrespondenceError,'对应不可靠'):
            normalize_stereo_pairs(same_left,same_right)

    def test_twelve_paired_images_solve_with_correction_without_24_requirement(self):
        from stereo_pose.calibration.package import read_bundle
        cal=_calibrator(self.root);cal.start()
        reverse={0,3,7}
        left,right,_=self.observations(reverse=reverse)
        for _ in range(12):
            cal.samples.append({'left':_grid_det(), 'right':_grid_det(dx=-12),
                                'descriptor':np.zeros(10)})
        obj=[self.obj.copy() for _ in left]
        paths=[(self.root/'l.png',self.root/'r.png') for _ in left]
        with mock.patch.object(cal,'_load_points',return_value=(obj,left,right,paths,(1280,720))):
            report=cal.solve()
        self.assertEqual(report['sample_count'],12)
        self.assertEqual(report['corner_order_reversed_count'],3)
        self.assertLess(report['sample_epipolar_mean_px'],3)
        bundle=read_bundle(report['path'])
        self.assertEqual(int(bundle['corner_order_reversed_count']),3)
        self.assertEqual(str(bundle['corner_order_modes'][0]),'reversed_180')
        np.testing.assert_allclose(bundle['T'].reshape(3),self.T,atol=15.0)

    def test_unresolvable_corners_do_not_publish_new_npz(self):
        cal=_calibrator(self.root);cal.start()
        left,right,_=self.observations()
        right[2]=np.roll(right[2],5,axis=0)
        for _ in left:
            cal.samples.append({'left':_grid_det(), 'right':_grid_det(dx=-12),
                                'descriptor':np.zeros(10)})
        existing=cal.calibration_dir/'auto'/'stereo_existing.npz'
        existing.parent.mkdir(parents=True,exist_ok=True)
        existing.write_bytes(b'existing physical calibration')
        paths=[(self.root/'l.png',self.root/'r.png') for _ in left]
        with mock.patch.object(cal,'_load_points',return_value=(
                [self.obj.copy() for _ in left],left,right,paths,(1280,720))):
            with self.assertRaisesRegex(CornerCorrespondenceError,'第 3 组'):
                cal.solve()
        self.assertTrue(cal.active)
        self.assertEqual(list(existing.parent.glob('*.npz')),[existing])
        self.assertEqual(existing.read_bytes(),b'existing physical calibration')




if __name__ == "__main__":
    unittest.main()
