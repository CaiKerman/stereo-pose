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
from stereo_pose.calibration.package import activate_calibration, save_registered, read_bundle
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

    def execute(self, keys, calibration_solve=None, world_result=None, native=False):
        from stereo_pose.app.measurements import append_readout
        self.readout_registrations = []
        def draw_readout(canvas, rows, registration, *args, **kwargs):
            self.readout_registrations.append(registration)
            return append_readout(canvas, rows, registration, *args, **kwargs)
        estimator=Mock();results=[Mock(),Mock()]
        for result in results:result.plot.return_value=self.image.copy()
        estimator.infer_pair.return_value=results
        estimator.best_person.side_effect=lambda result:(self.L if result is results[0] else self.R,np.ones(17),0,1)
        camera=Mock();camera.get.side_effect=lambda k: {3:1280,4:720,5:30}.get(k,0)
        calibrator=Mock();calibrator.active=False
        calibrator.start.side_effect=lambda:setattr(calibrator,'active',True)
        calibrator.stop_without_delete.side_effect=lambda:setattr(calibrator,'active',False)
        calibrator.draw_overlay.side_effect=lambda canvas,*a:canvas
        calibrator.current={'valid':True,'good_area':True,'capture_reason':'settling'}
        calibrator.samples=[];calibrator.target_pairs=24;calibrator.min_pairs=12
        calibrator.auto_capture=True;calibrator.diversity_threshold=.12
        calibrator.readiness.return_value=50;calibrator.can_solve.return_value=False
        self.calibrator_for_test=calibrator
        if calibration_solve is not None:
            calibrator.start.side_effect=lambda:setattr(calibrator,'active',True)
            calibrator.readiness.return_value=100;calibrator.recommended_readiness=75
            calibrator.can_solve.return_value=True
            def solve():
                calibrator.active=False
                return {'path':calibration_solve,'T':[-300,0,0],'stereo_rms':0.,'sample_epipolar_mean_px':0.,'sample_epipolar_max_px':0.}
            calibrator.solve.side_effect=solve
        publisher=Mock()
        if native:
            display=Mock();display.native=True
            display.show.side_effect=keys
            self.display_for_test=display
        count={'i':0};clock={'t':0}
        def pair(*a,**kw):
            clock['t']+=250_000_000;count['i']+=1
            return True,self.image.copy(),self.image.copy(),{'host_midpoint_perf_ns':clock['t'],'wall_timestamp_ns':1_700_000_000_000_000_000+clock['t']}
        with ExitStack() as stack:
            if native:
                stack.enter_context(patch('stereo_pose.app.runner.create_display',return_value=display))
            else:
                from stereo_pose.app.desktop import HighGuiDisplay
                stack.enter_context(patch('stereo_pose.app.runner.create_display',return_value=HighGuiDisplay()))
                stack.enter_context(patch('stereo_pose.app.desktop.configure_highgui',return_value=False))
            for name,value in [('PoseEstimator',estimator),('open_camera',camera),('RuntimeCalibration',calibrator),('build_publisher',publisher),('resolve_device','cpu')]:
                stack.enter_context(patch('stereo_pose.app.runner.'+name,return_value=value))
            read=stack.enter_context(patch('stereo_pose.app.runner.read_stereo_pair',side_effect=pair))
            stack.enter_context(patch('stereo_pose.app.runner.time.perf_counter_ns',side_effect=lambda:clock['t']))
            # Default clock binding is patched via an injected recorder factory.
            from stereo_pose.outputs.csv_recorder import CsvRecorder
            stack.enter_context(patch('stereo_pose.app.runner.CsvRecorder',side_effect=lambda *a,**k:CsvRecorder(*a,**k,clock=lambda:clock['t'])))
            stack.enter_context(patch('cv2.imshow'));stack.enter_context(patch('cv2.waitKey',side_effect=keys));stack.enter_context(patch('cv2.destroyAllWindows'))
            wizard=stack.enter_context(patch('stereo_pose.app.runner.run_world_setup',return_value=world_result))
            stack.enter_context(patch('stereo_pose.app.runner.append_readout',side_effect=draw_readout))
            run(self.args,self.cfg)
        self.assertEqual(read.call_count,len(keys));self.assertEqual(estimator.infer_pair.call_count,len(keys)-calibrator.process.call_count)
        self.assertEqual(camera.release.call_count,2);publisher.close.assert_called_once()
        return publisher,wizard

    def test_native_buttons_run_original_calibration_manual_and_return_handlers(self):
        self.execute([ord('c'),ord(' '),ord('c'),ord('q')],native=True)
        self.calibrator_for_test.capture_current.assert_called_once()
        self.calibrator_for_test.stop_without_delete.assert_called_once()
        self.display_for_test.close.assert_called_once()
        views=[call.kwargs['view']['mode'] for call in self.display_for_test.show.call_args_list]
        self.assertEqual(views,['tracking','calibration','calibration','tracking'])
        for call in self.display_for_test.show.call_args_list:
            for image in call.kwargs['pair']:self.assertEqual(image.shape,self.image.shape)

    def test_native_csv_and_world_dialog_keep_lifecycle(self):
        _,wizard=self.execute([ord('t'),0,ord('w'),ord('q')],native=True)
        self.assertIs(wizard.call_args.kwargs['desktop'],self.display_for_test)
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['stop_reason'],'world_setup')

    def test_native_close_key_stops_recording_and_releases_resources(self):
        self.execute([ord('t'),0,ord('q')],native=True)
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['stop_reason'],'app_exit')
        self.display_for_test.close.assert_called_once()

    def test_default_off_and_original_protocol(self):
        pub,_=self.execute([ord('q')])
        self.assertFalse((self.root/'recordings').exists())
        msg=pub.publish.call_args.args[0]
        self.assertEqual(msg['coordinate_system'],'rectified_left_camera')
        self.assertEqual(len(msg['joints']),12);self.assertNotIn('left_eye',msg['joints'])

    def test_calibration_SPACE_reuses_current_pair_and_C_returns_to_tracking(self):
        self.execute([ord('c'),0,ord(' '),ord('c'),ord('q')])
        self.assertEqual(self.calibrator_for_test.process.call_count,3)
        self.calibrator_for_test.capture_current.assert_called_once()
        self.calibrator_for_test.stop_without_delete.assert_called_once()

    def test_manual_start_sample_stop_and_no_extra_inference(self):
        self.execute([ord('t'),0,0,ord('t'),ord('q')])
        sessions=list((self.root/'recordings').glob('session_*'));self.assertEqual(len(sessions),1)
        meta=json.loads((sessions[0]/'session.json').read_text())
        self.assertEqual(meta['stop_reason'],'manual');self.assertEqual(meta['samples_completed'],3)
        self.assertIn('left_eye',meta['selected_joints']);self.assertIn('eye_midpoint',meta['selected_joints'])
        self.assertEqual(len(meta['calibration_sha256']),64)
        self.assertIn('reset_after_s',meta['filtering']);self.assertEqual(meta['device'],'cpu')
        self.assertEqual(meta['actual_image_size_right'],[1280,720])

    def test_default_readout_and_csv_share_midpoint_frame(self):
        pub,_=self.execute([ord('t'),0,ord('q')])
        registration=self.readout_registrations[-1]
        self.assertEqual(registration['metadata']['mode'],'camera_midpoint')
        session=next((self.root/'recordings').glob('session_*'))
        meta=json.loads((session/'session.json').read_text())
        self.assertEqual(meta['coordinate_frame'],'camera_midpoint')
        self.assertFalse(meta['world']['definition']['up_confirmed'])
        np.testing.assert_allclose(meta['world']['R_wc'],registration['transform'].R)
        np.testing.assert_allclose(meta['world']['t_wc_mm'],registration['transform'].t)
        with (session/'joints.csv').open(encoding='utf-8-sig',newline='') as f:
            row=next(csv.DictReader(f))
        self.assertEqual(row['coordinate_frame'],'camera_midpoint')
        self.assertEqual(row['joint'],'left_eye')
        camera=[float(row['camera_filtered_mm_'+axis]) for axis in ('x','y','z')]
        world=[float(row['world_filtered_mm_'+axis]) for axis in ('x','y','z')]
        np.testing.assert_allclose(world,[camera[2],150-camera[0],-camera[1]],atol=1e-8)
        self.assertEqual(pub.publish.call_args.args[0]['coordinate_system'],'rectified_left_camera')

    def test_cancelled_W_keeps_default_and_restart_recomputes_it(self):
        before=self.cal.read_bytes()
        _,wizard=self.execute([ord('w'),ord('q')])
        self.assertEqual(wizard.call_args.kwargs['registration']['metadata']['mode'],'camera_midpoint')
        first=self.readout_registrations[0]['transform'].as_matrix()
        np.testing.assert_allclose(self.readout_registrations[-1]['transform'].as_matrix(),first)
        self.execute([ord('q')])
        np.testing.assert_allclose(self.readout_registrations[0]['transform'].as_matrix(),first)
        self.assertEqual(self.cal.read_bytes(),before)

    def test_new_stereo_recomputes_default_instead_of_carrying_world(self):
        self.world_source()
        new=synthetic_calibration(self.root/'new_stereo.npz')
        bundle=read_bundle(new);bundle['P2'][0,3]=-900*500;bundle['T'][0]=-500
        np.savez(new,**bundle)
        self.execute([ord('c'),ord('r'),ord('t'),0,ord('q')],calibration_solve=new)
        registration=self.readout_registrations[-1]
        self.assertEqual(registration['metadata']['mode'],'camera_midpoint')
        self.assertAlmostEqual(registration['metadata']['baseline_mm'],500)
        np.testing.assert_allclose(registration['transform'].apply([250,0,0]),[0,0,0])
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['coordinate_frame'],'camera_midpoint')
        self.assertEqual(meta['calibration_file'],str(new))

    def test_successful_W_replaces_default_for_live_readout_and_recording(self):
        saved=save_registered(self.cal,{'name':'ALIGNED WORLD',
            'transform':RigidTransform(np.eye(3),[10,20,30]),
            'metadata':{'mode':'world','up_confirmed':True}},self.root/'cal',self.root)
        self.execute([ord('w'),ord('t'),0,ord('q')],world_result=saved)
        self.assertEqual(self.readout_registrations[0]['metadata']['mode'],'camera_midpoint')
        self.assertEqual(self.readout_registrations[-1]['name'],'ALIGNED WORLD')
        meta=json.loads(next((self.root/'recordings').glob('session_*/session.json')).read_text())
        self.assertEqual(meta['coordinate_frame'],'ALIGNED WORLD')
        self.assertEqual(meta['calibration_file'],str(saved))

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
