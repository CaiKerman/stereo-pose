"""Task003A geometry/package regressions use synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from stereo_pose.coordinates.rigid import RigidTransform, fit_rigid, relative_origin
from stereo_pose.calibration.package import (
    read_bundle, load_registration, save_registered, activate_calibration, file_sha256,
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


class TestMarkerCorrespondence(unittest.TestCase):
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
