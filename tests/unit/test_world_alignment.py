"""Task003A geometry/package regressions use synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from stereo_pose.coordinates.rigid import RigidTransform, fit_rigid, relative_origin
from stereo_pose.calibration.package import (
    read_bundle, load_registration, save_registered, activate_calibration, file_sha256,
    atomic_npz, export_calibration_npz,
)
from stereo_pose.coordinates.markers import read_references, match_features, detect_markers
from stereo_pose.geometry import StereoTriangulator


def synthetic_calibration(path, distortion_shape=(1, 5)):
    K = np.array([[900., 0, 640], [0, 900, 360], [0, 0, 1]])
    P = np.c_[K, np.zeros(3)]
    P2 = P.copy(); P2[0, 3] = -900 * 300
    np.savez(path, K1=K, K2=K, D1=np.zeros(distortion_shape), D2=np.zeros(distortion_shape),
             R1=np.eye(3), R2=np.eye(3), R=np.eye(3), T=np.array([-300., 0, 0]),
             P1=P, P2=P2, image_size=np.array([1280, 720]), custom=np.array('preserve'))
    return path


class TestWorldFrozenPreview(unittest.TestCase):
    def test_raw_preview_keeps_full_frame_and_marker_location(self):
        from stereo_pose.app.world_setup import raw_frozen_markers
        left=np.zeros((720,1280,3),dtype=np.uint8)
        right=np.zeros_like(left)
        left[:]=[20,33,49]
        right[:]=[15,55,90]
        corners=np.array([[550,480],[640,480],[640,570],[550,570]],np.float32)
        frozen=raw_frozen_markers(left,right,{0:corners},{0:corners+np.array([30,0])})
        self.assertEqual([x.shape for x in frozen],[left.shape,right.shape])
        np.testing.assert_array_equal(frozen[0][100,100],left[100,100])
        np.testing.assert_array_equal(frozen[1][100,100],right[100,100])
        self.assertGreater(frozen[0][480,600,1],200)  # raw polygon stays at board location
        self.assertGreater(frozen[1][480,630,1],200)
        self.assertFalse(np.array_equal(frozen[0],left))
        np.testing.assert_array_equal(left[480,600],[20,33,49])

    def test_raw_world_axes_project_back_through_rectification_rotation(self):
        from stereo_pose.app.world_setup import world_axis_pixels_raw
        from types import SimpleNamespace
        rotation=cv2.Rodrigues(np.array([.04,-.09,.02]))[0]
        K=np.array([[1100.,0,630.],[0,1070.,350.],[0,0,1.]])
        D=np.array([-.05,.006,0.001,0.002,0.])
        tri=SimpleNamespace(K1=K,D1=D,R1=rotation)
        offset=np.array([0.,0.,1400.])
        actual=world_axis_pixels_raw(
            RigidTransform(np.eye(3),-offset),tri,length=100.,anchor_world=(0.,0.,0.)
        )
        points=np.array([[0,0,1400],[100,0,1400],[0,100,1400],[0,0,1500]],float)
        original=(rotation.T@points.T).T
        expected=cv2.projectPoints(original,np.zeros(3),np.zeros(3),K,D)[0].reshape(-1,2)
        np.testing.assert_allclose(actual,expected,atol=1e-8)

    def test_world_setup_never_rectifies_operator_preview_or_reloads_camera(self):
        from stereo_pose.app.world_setup import run_world_setup
        from stereo_pose.config import load_config
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            cal=synthetic_calibration(root/'calibration.npz')
            cfg=load_config(None)
            cfg['runtime']['root']=str(root)
            cfg['world']['reference_file']=str(root/'references.csv')
            left=np.zeros((720,1280,3),np.uint8)
            right=np.zeros_like(left)
            left[400:600,500:800]=[15,65,115]
            right[400:600,470:770]=[25,70,130]
            corners=np.array([[520.,420.],[600.,420.],[600.,500.],[520.,500.]])
            detector=lambda frame,dictionary: {0:corners}
            tri=StereoTriangulator(cal)
            with (
                patch('stereo_pose.app.world_setup.cv2.initUndistortRectifyMap',
                      side_effect=AssertionError('W preview should not rectify')),
                patch('stereo_pose.app.world_setup._setup_loop',return_value=None) as loop
            ):
                result=run_world_setup(
                    frame_left=left,frame_right=right,triangulator=tri,
                    calib_path=cal,config_path=root/'config.json',cfg=cfg,
                    detector=detector
                )
            self.assertIsNone(result)
            frozen_left,frozen_right=loop.call_args.args[0]
            self.assertEqual(frozen_left.shape,left.shape)
            self.assertEqual(frozen_right.shape,right.shape)
            np.testing.assert_array_equal(frozen_left[550,650],left[550,650])
            np.testing.assert_array_equal(frozen_right[550,650],right[550,650])


class TestWorldRigid(unittest.TestCase):
    def setUp(self):
        self.C = np.array([[0, 0, 1000], [100, 0, 1000], [0, 100, 1000], [90, 120, 1100.]])
        self.R = cv2.Rodrigues(np.array([.4, -.3, .7]))[0]
        self.t = np.array([11., 28., -910.])
        self.W = self.C @ self.R.T + self.t

    def test_arbitrary_proper_transform_inverse_distances(self):
        f = fit_rigid(self.C, self.W)
        np.testing.assert_allclose(f.transform.R, self.R, atol=1e-12)
        np.testing.assert_allclose(f.transform.t, self.t, atol=1e-10)
        np.testing.assert_allclose(f.transform.inverse().apply(self.W), self.C, atol=1e-10)
        self.assertAlmostEqual(np.linalg.det(f.transform.R), 1.)
        np.testing.assert_allclose(np.linalg.norm(np.diff(self.W, axis=0), axis=1),
                                   np.linalg.norm(np.diff(self.C, axis=0), axis=1))

    def test_three_coplanar_tilted_controls_allowed(self):
        f = fit_rigid(self.C[:3], self.W[:3])
        self.assertIn('redundancy', f.report()['warning'])
        self.assertLess(f.report()['max_mm'], 1e-8)

    def test_bad_controls_rejected(self):
        bad = [np.zeros((0, 3)), self.C[:2], np.array([[0,0,0],[1,0,0],[2,0,0]]),
               np.array([[0,0,0],[100,0,0],[200,.00001,0]]), self.C * np.nan]
        for p in bad:
            with self.subTest(p=p), self.assertRaises(ValueError): fit_rigid(p, p)

    def test_scale_and_outlier_not_silently_corrected(self):
        for w in [self.W * 2, self.W + [[0,0,0],[0,0,0],[0,0,0],[100,0,0]]]:
            with self.subTest(w=w), self.assertRaises(ValueError): fit_rigid(self.C, w, max_residual_mm=2)

    def test_improper_nonfinite_rotation_rejected(self):
        for r in [np.diag([1,1,-1]), np.eye(3)*2, np.eye(3)*np.nan]:
            with self.subTest(r=r), self.assertRaises(ValueError): RigidTransform(r, np.zeros(3))

    def test_zero_preserves_world_and_camera_axes(self):
        for base in [None, RigidTransform(self.R, self.t)]:
            z = relative_origin(base, self.C[0])
            np.testing.assert_allclose(z.apply(self.C[0]), np.zeros(3), atol=1e-10)
            np.testing.assert_allclose(z.R, np.eye(3) if base is None else self.R)


class TestWorldPackage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = synthetic_calibration(self.root/'old.npz')
        self.reg = {'name':'TEST WORLD', 'transform':RigidTransform(np.eye(3), [1,2,3]),
                    'metadata':{'method':'rigid_controls', 'up_confirmed':True, 'reference_points':[]}}

    def save(self):
        return save_registered(self.source, self.reg, self.root/'cal', self.root)

    def test_legacy_and_shape_roundtrip_and_no_overwrite(self):
        original = self.source.read_bytes()
        self.assertIsNone(load_registration(self.source)[0])
        for shape in [(1,5),(5,1),(5,)]:
            with self.subTest(shape=shape):
                synthetic_calibration(self.source, shape)
                a = read_bundle(self.source); target=self.save(); b=read_bundle(target)
                for k in a: np.testing.assert_array_equal(a[k], b[k])
                self.assertEqual(b['D1'].shape, shape)
                reg, warnings=load_registration(target)
                self.assertEqual(reg['name'], 'TEST WORLD'); self.assertFalse(warnings)
                StereoTriangulator(target)
        self.assertNotEqual(self.save(), self.save())
        synthetic_calibration(self.source)
        self.assertEqual(original, self.source.read_bytes())

    def test_manual_export_copies_exact_full_world_npz_without_mutating_source(self):
        source=self.save()
        before=source.read_bytes()
        exported=export_calibration_npz(source,self.root/'world_backup.npz',
            expected_sha256=file_sha256(source))
        self.assertEqual(exported.read_bytes(),before)
        self.assertEqual(source.read_bytes(),before)
        active,_=load_registration(exported)
        self.assertEqual(active['name'],'TEST WORLD')
        self.assertEqual(file_sha256(exported),file_sha256(source))

    def test_manual_export_rejects_invalid_destination_and_hash_mismatch(self):
        target=self.root/'safe.npz'
        target.write_bytes(b'prior user backup')
        prior=target.read_bytes()
        for destination,expected in [
            (self.source,'none'),
            (self.root/'wrong.txt',None),
            (target,'f'*64),
        ]:
            with self.subTest(destination=destination,expected=expected):
                with self.assertRaises(ValueError):
                    export_calibration_npz(self.source,destination,
                        expected_sha256=expected)
                self.assertEqual(target.read_bytes(),prior)
                self.assertFalse(list(self.root.glob('*.tmp')))

    def test_manual_export_refuses_existing_destination_without_permission(self):
        target=self.root/'my_old_backup.npz'
        target.write_bytes(b'important previous file')
        with self.assertRaises(FileExistsError):
            export_calibration_npz(self.source,target)
        self.assertEqual(target.read_bytes(),b'important previous file')
        exported=export_calibration_npz(self.source,target,overwrite=True)
        self.assertEqual(exported.read_bytes(),self.source.read_bytes())

    def test_manual_export_atomic_failure_preserves_old_destination(self):
        target=self.root/'safe.npz'
        target.write_bytes(b'untouched')
        with patch('stereo_pose.calibration.package.os.replace',
                   side_effect=OSError('failed to publish')), self.assertRaises(OSError):
            export_calibration_npz(self.source,target,overwrite=True)
        self.assertEqual(target.read_bytes(),b'untouched')
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_geometry_tamper_invalidates_world(self):
        p=self.save(); b=read_bundle(p); b['K1'][0,0]+=1; np.savez(p, **b)
        reg, warnings=load_registration(p)
        self.assertIsNone(reg); self.assertIn('fingerprint', warnings[0])

    def test_resolution_invalidates_world_index_does_not(self):
        p=self.save()
        self.assertIsNone(load_registration(p, (640,480))[0])
        b=read_bundle(p); b['camera_left']=np.array(8); np.savez(p, **b)
        self.assertIsNotNone(load_registration(p)[0])

    def test_active_file_survives_new_auto_and_restart(self):
        from stereo_pose.calibration import newest_calibration
        from stereo_pose.config import load_config
        p=self.save(); cfg=self.root/'config.json'; cfg.write_text('{"unknown":42}')
        activate_calibration(cfg, p)
        c=load_config(cfg); self.assertEqual(c['unknown'],42)
        auto=self.root/'cal'/'auto'; auto.mkdir(); synthetic_calibration(auto/'stereo_new.npz')
        self.assertEqual(newest_calibration(self.root/'cal', c['stereo']['explicit_file']),p)
        self.assertEqual(c['stereo']['active_sha256'],file_sha256(p))

    def test_save_and_activation_failures_preserve_history(self):
        p=self.save(); old=p.read_bytes()
        with patch('stereo_pose.calibration.package.np.savez',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.save()
        self.assertEqual(p.read_bytes(),old)
        self.assertEqual(len(list((self.root/'cal'/'saved').glob('*.npz'))),1)
        cfg=self.root/'config.json'; cfg.write_text('{"keep":1}')
        with patch('stereo_pose.calibration.package.os.replace',side_effect=OSError('denied')):
            with self.assertRaises(OSError): activate_calibration(cfg,p)
        self.assertEqual(json.loads(cfg.read_text()),{'keep':1})

    def test_no_generated_path_escape_or_objects(self):
        with self.assertRaises(Exception): save_registered(self.source,self.reg,self.root.parent/'bad',self.root)
        with patch('stereo_pose.calibration.package.read_bundle',return_value={'x':np.array({},dtype=object)}):
            with self.assertRaises(ValueError): self.save()

    def test_partial_unknown_schema_and_invalid_shapes(self):
        for field,value in [('world_schema_version',np.array('2')),('world_R',np.eye(3)*2),('D1',np.zeros((2,5)))]:
            with self.subTest(field=field):
                p=self.save();b=read_bundle(p);b[field]=value;np.savez(p,**b)
                self.assertIsNone(load_registration(p)[0])
        p=self.save();b=read_bundle(p);del b['world_t_mm'];np.savez(p,**b)
        self.assertIsNone(load_registration(p)[0])

    def test_world_metadata_object_is_refused_without_pickle(self):
        p=self.save();b=read_bundle(p);b['world_metadata_json']=np.array({'bad':1},dtype=object);np.savez(p,**b)
        reg,warnings=load_registration(p);self.assertIsNone(reg);self.assertTrue(warnings)

    def test_atomic_archive_refuses_existing_path_and_failed_write(self):
        old=self.source.read_bytes()
        with self.assertRaises(FileExistsError):atomic_npz(self.source,{'new':np.arange(3)})
        self.assertEqual(self.source.read_bytes(),old)
        with patch('stereo_pose.calibration.package.np.savez',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):atomic_npz(self.root/'new.npz',{'new':np.arange(3)})
        self.assertFalse((self.root/'new.npz').exists());self.assertFalse(list(self.root.glob('*.partial')))


class TestMarkerCorrespondence(unittest.TestCase):
    def test_stereo_corner_rejection_shows_actual_quality_metrics(self):
        refs=[{'dictionary':'DICT_4X4_50','id':0,'feature_type':'center','xyz_mm':[0,0,0]}]
        observed={0:np.zeros((4,2))}
        cases=[
            (None,'三角化失败'),
            ({'xyz_mm':np.array([10.,20.,1000.]),'epipolar_error_px':7.25,
              'reprojection_error_max_px':4.5},'极线误差超限'),
            ({'xyz_mm':np.array([10.,20.,-100.]),'epipolar_error_px':0.5,
              'reprojection_error_max_px':1.0},'相机深度必须大于0'),
            ({'xyz_mm':np.array([10.,20.,1000.]),'epipolar_error_px':0.5,
              'reprojection_error_max_px':4.5},'重投影误差超限'),
        ]
        for result,reason in cases:
            with self.subTest(reason=reason):
                tri=Mock();tri.triangulate_with_quality.return_value=result
                with self.assertRaises(ValueError) as cm:
                    match_features(refs,observed,observed,tri,'DICT_4X4_50',3,2.5)
                message=str(cm.exception)
                self.assertIn('ID 0 corner0',message)
                self.assertIn(reason,message)
                self.assertIn('上限 3px',message)
                self.assertIn('上限 2.5px',message)
                self.assertIn('冻结',message)
                if result is not None:
                    self.assertIn('1000.00mm' if result['xyz_mm'][2]==1000. else '-100.00mm',message)

    def test_reference_csv_explicit_types_duplicates_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.csv'
            header='dictionary,id,feature_type,X_mm,Y_mm,Z_mm\n'
            good='DICT_4X4_50,7,center,0,0,0\nDICT_4X4_50,3,center,100,0,0\nDICT_4X4_50,2,corner0,0,100,0\n'
            p.write_text(header+good); self.assertEqual(len(read_references(p)),3)
            for bad in [good+good, good.replace(',100,0,0',',nan,0,0'), good.replace('corner0','wrong')]:
                p.write_text(header+bad)
                with self.assertRaises(ValueError): read_references(p)

    def test_real_aruco_detector_and_duplicate_ids(self):
        dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker=cv2.aruco.generateImageMarker(dictionary,7,140)
        image=np.full((240,400),255,np.uint8); image[50:190,30:170]=marker
        found=detect_markers(image,'DICT_4X4_50'); self.assertIn(7,found)
        image[50:190,230:370]=marker
        with self.assertRaises(ValueError): detect_markers(image,'DICT_4X4_50')

    def test_tilted_marker_center_uses_triangulated_corners(self):
        with tempfile.TemporaryDirectory() as d:
            tri=StereoTriangulator(synthetic_calibration(Path(d)/'s.npz'))
            R=cv2.Rodrigues(np.array([.9,.7,.1]))[0]
            points=np.array([[-30,-30,0],[30,-30,0],[30,30,0],[-30,30,0]])@R.T+[0,0,1100]
            def project(P):
                v=np.c_[points,np.ones(4)]@P.T;return v[:,:2]/v[:,2:]
            l={7:project(tri.P1)};r={7:project(tri.P2)}
            refs=[{'dictionary':'DICT_4X4_50','id':7,'feature_type':'center','xyz_mm':[0,0,0]}]
            c,w=match_features(refs,l,r,tri,'DICT_4X4_50',3,2.5)
            np.testing.assert_allclose(c[0],points.mean(axis=0),atol=1e-9)
            with self.assertRaises(ValueError): match_features(refs,l,{},tri,'DICT_4X4_50',3,2.5)
            with self.assertRaises(ValueError): match_features(refs,l,r,tri,'DICT_5X5_50',3,2.5)
