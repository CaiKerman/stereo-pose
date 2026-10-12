"""Whole tracking loop with injected cameras/model/windows; real geometry and files."""
import json
import csv
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
from stereo_pose.config import ConfigError, load_config, validate_config
from stereo_pose.app.runner import run
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.calibration.package import activate_calibration, save_registered
from stereo_pose.coordinates.rigid import RigidTransform
from tests.unit.test_world_alignment import synthetic_calibration


class TestTrackingLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.cal=synthetic_calibration(self.root/'old.npz')
        self.tri=StereoTriangulator(self.cal);self.cfg=load_config(None)
        self.cfg['cleanup']['enabled']=False;self.cfg['runtime']['root']=str(self.root)
        self.cfg['stereo'].update(load='explicit',explicit_file=str(self.cal),calibration_dir=str(self.root/'cal'))
        self.cfg['recording']['output_dir']=str(self.root/'recordings')
        self.cfg['world']['reference_file']=str(self.root/'ref.csv')
        self.args=SimpleNamespace(left_cam=None,right_cam=None,device=None,model=None,config=str(self.root/'config.json'))
        Path(self.args.config).write_text(json.dumps(self.cfg))
        xyz=np.tile([0.,0.,1200.],(17,1));xyz[:,0]=np.arange(17)*12
        def proj(P):
            q=np.c_[xyz,np.ones(17)]@P.T;return q[:,:2]/q[:,2:]
        self.L=proj(self.tri.P1);self.R=proj(self.tri.P2);self.image=np.zeros((720,1280,3),np.uint8)

    def execute(self, keys, calibration_solve=None):
        estimator=Mock();results=[Mock(),Mock()]
        for result in results:result.plot.return_value=self.image.copy()
        estimator.infer_pair.return_value=results
        estimator.best_person.side_effect=lambda result:(self.L if result is results[0] else self.R,np.ones(17),0,1)
        camera=Mock();camera.get.side_effect=lambda k: {3:1280,4:720,5:30}.get(k,0)
        calibrator=Mock();calibrator.active=False
        if calibration_solve is not None:
            calibrator.start.side_effect=lambda:setattr(calibrator,'active',True)
            calibrator.readiness.return_value=100;calibrator.recommended_readiness=75
            calibrator.can_solve.return_value=True
            def solve():
                calibrator.active=False
                return {'path':calibration_solve,'T':[-300,0,0],'stereo_rms':0.,'sample_epipolar_mean_px':0.,'sample_epipolar_max_px':0.}
            calibrator.solve.side_effect=solve
        publisher=Mock()
        count={'i':0};clock={'t':0}
        def pair(*a,**kw):
            clock['t']+=250_000_000;count['i']+=1
            return True,self.image.copy(),self.image.copy(),{'host_midpoint_perf_ns':clock['t'],'wall_timestamp_ns':1_700_000_000_000_000_000+clock['t']}
        with ExitStack() as stack:
            for name,value in [('PoseEstimator',estimator),('open_camera',camera),('RuntimeCalibration',calibrator),('build_publisher',publisher),('resolve_device','cpu')]:
                stack.enter_context(patch('stereo_pose.app.runner.'+name,return_value=value))
            read=stack.enter_context(patch('stereo_pose.app.runner.read_stereo_pair',side_effect=pair))
            stack.enter_context(patch('stereo_pose.app.runner.time.perf_counter_ns',side_effect=lambda:clock['t']))
            # Default clock binding is patched via an injected recorder factory.
            from stereo_pose.outputs.csv_recorder import CsvRecorder
            stack.enter_context(patch('stereo_pose.app.runner.CsvRecorder',side_effect=lambda *a,**k:CsvRecorder(*a,**k,clock=lambda:clock['t'])))
            stack.enter_context(patch('cv2.imshow'));stack.enter_context(patch('cv2.waitKey',side_effect=keys));stack.enter_context(patch('cv2.destroyAllWindows'))
            wizard=stack.enter_context(patch('stereo_pose.app.runner.run_world_setup',return_value=None))
            run(self.args,self.cfg)
        self.assertEqual(read.call_count,len(keys));self.assertEqual(estimator.infer_pair.call_count,len(keys)-(1 if calibration_solve is not None else 0))
        self.assertEqual(camera.release.call_count,2);publisher.close.assert_called_once()
        return publisher,wizard

    def test_default_off_and_original_protocol(self):
        pub,_=self.execute([ord('q')])
        self.assertFalse((self.root/'recordings').exists())
        msg=pub.publish.call_args.args[0]
        self.assertEqual(msg['coordinate_system'],'rectified_left_camera')
        self.assertEqual(len(msg['joints']),12);self.assertNotIn('left_eye',msg['joints'])

    def test_manual_start_sample_stop_and_no_extra_inference(self):
        self.execute([ord('t'),0,0,ord('t'),ord('q')])
        sessions=list((self.root/'recordings').glob('session_*'));self.assertEqual(len(sessions),1)
        meta=json.loads((sessions[0]/'session.json').read_text())
        self.assertEqual(meta['stop_reason'],'manual');self.assertEqual(meta['samples_completed'],3)
        self.assertIn('left_eye',meta['selected_joints']);self.assertIn('eye_midpoint',meta['selected_joints'])
        self.assertEqual(len(meta['calibration_sha256']),64)
        self.assertIn('reset_after_s',meta['filtering']);self.assertEqual(meta['device'],'cpu')
        self.assertEqual(meta['actual_image_size_right'],[1280,720])

    def test_world_setup_segments_recording_even_when_cancelled(self):
        _,wizard=self.execute([ord('t'),0,ord('w'),ord('q')])
        wizard.assert_called_once();meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['stop_reason'],'world_setup')

    def test_filter_change_stops_and_app_exit_flushes(self):
        self.execute([ord('t'),0,ord('f'),ord('q')])
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text());self.assertEqual(meta['stop_reason'],'filter_changed')
        self.execute([ord('t'),0,ord('q')])
        self.assertIn('app_exit',[json.loads(p.read_text())['stop_reason'] for p in (self.root/'recordings').glob('session_*/session.json')])

    def test_invalid_record_path_fails_without_crashing_tracking(self):
        self.cfg['recording']['output_dir']=str(self.root/'sessions')
        self.execute([ord('t'),ord('q')]);self.assertFalse((self.root/'sessions').exists())

    def world_source(self):
        p=save_registered(self.cal,{'name':'TEST WORLD','transform':RigidTransform(np.eye(3),[100,200,300]),
            'metadata':{'method':'synthetic','up_confirmed':True}},self.root/'cal',self.root)
        activate_calibration(self.args.config,p)
        self.cfg=load_config(self.args.config)
        return p

    def test_restart_restores_world_without_markers_and_csv_keeps_C_and_W(self):
        p=self.world_source();pub,wizard=self.execute([ord('t'),0,ord('q')])
        wizard.assert_not_called()
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['coordinate_frame'],'TEST WORLD');self.assertEqual(meta['calibration_file'],str(p))
        with next((self.root/'recordings').glob('session_*/joints.csv')).open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
        self.assertAlmostEqual(float(row['world_filtered_mm_x'])-float(row['camera_filtered_mm_x']),100)
        self.assertEqual(pub.publish.call_args.args[0]['coordinate_system'],'rectified_left_camera')

    def test_stereo_resolve_clears_world_and_persists_new_selection(self):
        self.world_source();new=synthetic_calibration(self.root/'new_stereo.npz')
        pub,_=self.execute([ord('t'),ord('c'),ord('r'),ord('q')],calibration_solve=new)
        self.assertEqual(load_config(self.args.config)['stereo']['explicit_file'],str(new.resolve()))
        self.assertEqual(pub.publish.call_args.args[0]['calibration_file'],str(new))
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['stop_reason'],'enter_calibration');self.assertEqual(meta['coordinate_frame'],'TEST WORLD')


class TestTask003Config(unittest.TestCase):
    def test_defaults_match_shipped_json(self):
        defaults=load_config(None)
        shipped=json.loads((Path(__file__).parents[2]/'configs/default.json').read_text())
        for key in ['readout','world','recording']:self.assertEqual(defaults[key],shipped[key])

    def test_autostart_nonfinite_rate_and_unknown_joint_rejected(self):
        for key,value in [('auto_start',True),('sample_rate_hz',float('nan')),('sample_rate_hz',0),('enabled','true')]:
            with self.subTest(key=key,value=value):
                cfg=load_config(None);cfg['recording'][key]=value
                with self.assertRaises(ConfigError):validate_config(cfg)
        cfg=load_config(None);cfg['readout']['joints']=['unknown']
        with self.assertRaises(ConfigError):validate_config(cfg)
