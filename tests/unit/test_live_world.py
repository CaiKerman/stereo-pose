"""Deterministic live projection and W interaction; real geometry, fake window IO."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from stereo_pose.config import load_config
from stereo_pose.coordinates.rigid import RigidTransform
from stereo_pose.app.measurements import measure_frame, make_readout, append_readout
from stereo_pose.app.world_setup import run_world_setup, world_axis_pixels
from stereo_pose.filtering import JointSmoother
from stereo_pose.quality import TemporalSpeedGate
from stereo_pose.models import JointRejection
from stereo_pose.outputs.v1_message import serialize_v1_json
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.calibration.package import load_registration, file_sha256
from tests.unit.test_world_alignment import synthetic_calibration


class TestLiveProjection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.cal=synthetic_calibration(Path(self.tmp.name)/'s.npz');self.tri=StereoTriangulator(self.cal)
        self.cfg=load_config(None)
        C=np.tile([0.,0.,1200.],(17,1));C[:,0]=np.arange(17)*15
        def project(P):
            p=np.c_[C,np.ones(17)]@P.T;return p[:,:2]/p[:,2:]
        self.l=project(self.tri.P1);self.r=project(self.tri.P2)

    def measure(self, names, right=None):
        return measure_frame(selected_joints=['left_shoulder'],readout_joints=names,triangulator=self.tri,
            points_left=self.l,points_right=self.r if right is None else right,conf_left=np.ones(17),conf_right=np.ones(17),
            kp_conf=.45,qcfg=self.cfg['quality'],speed_gate=TemporalSpeedGate(),smoother=JointSmoother(),t_s=1,
            frame_index=0,wall_timestamp_ns=123,pair_timing={},calib_path=self.cal)

    def test_eyes_do_not_change_legacy_bytes_or_statistics(self):
        r=self.r.copy();r[1,1]+=25
        old,*_=self.measure(['left_shoulder'],r)
        new,accepted,v,g=self.measure(['left_eye','right_eye','eye_midpoint','left_shoulder'],r)
        self.assertEqual(serialize_v1_json(old),serialize_v1_json(new))
        self.assertIn('right_eye',accepted);self.assertNotIn('left_eye',accepted)
        self.assertEqual(new.frame_quality['accepted_joints'],1)

    def test_accepted_raw_filtered_world_and_midpoint(self):
        names=['left_eye','right_eye','eye_midpoint']
        frame,a,v,g=self.measure(names)
        registration={'transform':RigidTransform(np.eye(3),[100,200,300]),'name':'W'}
        before=serialize_v1_json(frame)
        rows=make_readout(names,a,v,g,registration)
        self.assertEqual(before,serialize_v1_json(frame))
        for row in rows:
            self.assertEqual(row['status'],'accepted')
            np.testing.assert_allclose(row['world_filtered_mm'],np.asarray(row['camera_filtered_mm'])+[100,200,300])
        np.testing.assert_allclose(rows[2]['camera_raw_mm'],(np.asarray(rows[0]['camera_raw_mm'])+rows[1]['camera_raw_mm'])/2)
        self.assertTrue(rows[2]['derived'])

    def test_candidate_is_separate_and_midpoint_missing(self):
        r=self.r.copy();r[1,1]+=20
        _,a,v,g=self.measure(['left_eye','right_eye'],r)
        rows=make_readout(['left_eye','right_eye','eye_midpoint'],a,v,g,None)
        self.assertEqual(rows[0]['status'],'candidate')
        self.assertIsNone(rows[0]['camera_filtered_mm']);self.assertIsNotNone(rows[0]['candidate_camera_mm'])
        self.assertIsNone(rows[2]['camera_filtered_mm']);self.assertEqual(rows[2]['reason'],'both_eyes_required')

    def test_missing_frame_never_uses_previous_values(self):
        _,a,v,g=self.measure(['left_eye','right_eye'])
        make_readout(['left_eye','right_eye','eye_midpoint'],a,v,g,None)
        rows=make_readout(['left_eye','right_eye','eye_midpoint'],{}, {}, {},None)
        self.assertTrue(all(x['camera_filtered_mm'] is None for x in rows))

    def test_overlay_contains_live_rows_without_mutating_image(self):
        _,a,v,g=self.measure(['left_eye','right_eye'])
        rows=make_readout(['left_eye','right_eye','eye_midpoint'],a,v,g,None)
        image=np.zeros((360,1280,3),np.uint8);copy=image.copy()
        drawn=append_readout(image,rows,None,'REC OFF')
        self.assertGreater(drawn.shape[0],360);np.testing.assert_array_equal(image,copy)


class TestWInteraction(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=synthetic_calibration(self.root/'old.npz')
        self.tri=StereoTriangulator(self.source);self.cfg=load_config(None)
        self.cfg['runtime']['root']=str(self.root);self.cfg['stereo']['calibration_dir']=str(self.root/'cal')
        self.cfg['world']['reference_file']=str(self.root/'ref.csv');self.config=self.root/'config.json'
        self.config.write_text('{"keep":12}')
        self.left={};self.right={}
        centers=[[0,0,1000],[100,0,1000],[0,100,1000]]
        for i,(cx,cy,cz) in enumerate(centers):
            pts=np.array([[-30,-30,0],[30,-30,0],[30,30,0],[-30,30,0]])+[cx,cy,cz]
            for P,out in [(self.tri.P1,self.left),(self.tri.P2,self.right)]:
                q=np.c_[pts,np.ones(4)]@P.T;out[i]=q[:,:2]/q[:,2:]
        Path(self.cfg['world']['reference_file']).write_text('dictionary,id,feature_type,X_mm,Y_mm,Z_mm\n'+
            'DICT_4X4_50,0,center,0,0,0\nDICT_4X4_50,1,center,100,0,0\nDICT_4X4_50,2,center,0,100,0\n')

    def wizard(self, keys, registration=None):
        with patch('cv2.getWindowProperty',return_value=1),patch('cv2.imshow'),patch('cv2.waitKey',side_effect=keys),patch('cv2.destroyWindow'):
            return run_world_setup(frame_left=np.zeros((720,1280,3),np.uint8),frame_right=np.zeros((720,1280,3),np.uint8),
                triangulator=self.tri,calib_path=self.source,config_path=self.config,cfg=self.cfg,registration=registration,
                detector=lambda frame,dictionary: self.left if not hasattr(self,'called') else self.right)

    def test_confirm_without_world_up_is_blocked_then_cancel_preserves_active(self):
        # Intrinsics/extrinsics differ only in P2, injected corner maps are per-view.
        with patch('stereo_pose.app.world_setup.detect_markers'):
            # Use a finite detector call sequence rather than any camera acquisition.
            from unittest.mock import Mock
            detector=Mock(side_effect=[self.left,self.right])
            old=self.config.read_bytes();source=file_sha256(self.source)
            with patch('cv2.getWindowProperty',return_value=1),patch('cv2.imshow'),patch('cv2.waitKey',side_effect=[ord('r'),13,27]),patch('cv2.destroyWindow'):
                out=run_world_setup(frame_left=np.zeros((720,1280,3),np.uint8),frame_right=np.zeros((720,1280,3),np.uint8),
                    triangulator=self.tri,calib_path=self.source,config_path=self.config,cfg=self.cfg,detector=detector)
            self.assertIsNone(out);self.assertEqual(self.config.read_bytes(),old);self.assertEqual(file_sha256(self.source),source)

    def test_fit_confirm_save_activate(self):
        from unittest.mock import Mock
        with patch('cv2.getWindowProperty',return_value=1),patch('cv2.imshow'),patch('cv2.waitKey',side_effect=[ord('r'),ord('u'),13]),patch('cv2.destroyWindow'):
            out=run_world_setup(frame_left=np.zeros((720,1280,3),np.uint8),frame_right=np.zeros((720,1280,3),np.uint8),
                triangulator=self.tri,calib_path=self.source,config_path=self.config,cfg=self.cfg,
                detector=Mock(side_effect=[self.left,self.right]))
        reg,warnings=load_registration(out,(1280,720));self.assertFalse(warnings)
        np.testing.assert_allclose(reg['transform'].t,[0,0,-1000],atol=1e-8)
        self.assertEqual(json.loads(self.config.read_text())['stereo']['explicit_file'],str(out.resolve()))

    def test_zero_mode_keeps_existing_rotation(self):
        from unittest.mock import Mock
        R=cv2.Rodrigues(np.array([.2,.1,.3]))[0];base={'transform':RigidTransform(R,[1,2,3]),'name':'old'}
        with patch('cv2.getWindowProperty',return_value=1),patch('cv2.imshow'),patch('cv2.waitKey',side_effect=[ord('z'),ord('r'),13]),patch('cv2.destroyWindow'):
            out=run_world_setup(frame_left=np.zeros((720,1280,3),np.uint8),frame_right=np.zeros((720,1280,3),np.uint8),
                triangulator=self.tri,calib_path=self.source,config_path=self.config,cfg=self.cfg,registration=base,
                detector=Mock(side_effect=[self.left,self.right]))
        reg,_=load_registration(out);np.testing.assert_allclose(reg['transform'].R,R)
        np.testing.assert_allclose(reg['transform'].apply([0,0,1000]),np.zeros(3),atol=1e-8)

    def test_axis_projection_matches_rectified_frame(self):
        t=RigidTransform(np.eye(3),[0,0,-1000]);uv=world_axis_pixels(t,self.tri.P1)
        np.testing.assert_allclose(uv[0],[640,360]);self.assertGreater(uv[1,0],uv[0,0]);self.assertGreater(uv[2,1],uv[0,1])
