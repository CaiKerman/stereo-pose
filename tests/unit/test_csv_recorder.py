"""Fake-clock cadence, real CSV/JSON IO, no cameras/models/user data."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from stereo_pose.models import PoseFrame, FrameTiming
from stereo_pose.outputs.csv_recorder import CsvRecorder, CSV_FIELDS
from stereo_pose.app.measurements import make_readout
from stereo_pose.persistence import cleanup_project


class TestCsvRecorder(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=0
        self.rec=CsvRecorder(self.root/'recordings',self.root,clock=lambda:self.now)
        self.meta={'calibration_file':'fixed.npz','calibration_sha256':'synthetic_hash',
                   'coordinate_frame':'CAMERA FRAME','config':{'quality':{'limit':3}}}

    def frame(self,i):
        return PoseFrame(i,1_700_000_000_000_000_000+self.now,'rectified_left_camera','mm','fixed.npz',
            FrameTiming(host_midpoint_perf_ns=self.now),{'enabled':True},{}, {})

    def rows(self):
        return make_readout(['left_eye','right_eye','eye_midpoint'],{}, {}, {},None)

    def read_rows(self):
        with (self.rec.path/'joints.csv').open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

    def test_off_until_start_no_files_written(self):
        self.assertFalse(self.rec.active);self.assertFalse(self.rec.sample(self.frame(0),self.rows()))
        self.assertFalse((self.root/'recordings').exists())

    def test_30_7_5_2_fps_and_fresh_cadence(self):
        for fps in [30,7,5,2]:
            with self.subTest(fps=fps):
                self.now=0;self.rec.start(self.meta)
                for i in range(fps*10):
                    self.now=int(round(i*1e9/fps));self.rec.sample(self.frame(i),self.rows())
                self.now=10_000_000_000;self.rec.stop()
                rows=self.read_rows();samples={int(r['sample_index']) for r in rows}
                self.assertEqual(len(samples),min(50,fps*10))
                self.assertEqual(len(rows),len(samples)*3)
                frames=[int(r['frame_index']) for r in rows[::3]]
                self.assertEqual(len(frames),len(set(frames)))
                self.assertTrue(all(int(r['timestamp_ns'])==1_700_000_000_000_000_000+int(r['sample_monotonic_ns']) for r in rows))

    def test_duplicate_stale_and_jitter_no_backfill(self):
        self.now=1_000_000_000;self.rec.start(self.meta)
        stale=self.frame(0);stale.timing.host_midpoint_perf_ns=0
        self.assertFalse(self.rec.sample(stale,self.rows()))
        for i,t in enumerate([1.01,1.019,1.27,1.31,1.91,4.]):
            self.now=int(t*1e9);frame=self.frame(i)
            self.rec.sample(frame,self.rows());self.assertFalse(self.rec.sample(frame,self.rows()))
        self.rec.stop();self.assertEqual(self.rec.samples,4)

    def test_missing_rows_blank_and_candidate_distinct(self):
        rows=self.rows();rows[0].update(status='candidate',reason='epipolar_threshold',candidate_camera_mm=[1,2,3])
        rows[1].update(status='accepted',reason='',camera_raw_mm=[4,5,6],camera_filtered_mm=[4.1,5.1,6.1],confidence_left=0.)
        self.rec.start(self.meta);self.rec.sample(self.frame(0),rows);self.rec.stop()
        saved=self.read_rows()
        self.assertEqual(list(saved[0]),CSV_FIELDS)
        self.assertEqual(saved[0]['camera_filtered_mm_x'],'');self.assertEqual(saved[0]['candidate_camera_mm_x'],'1.0')
        self.assertEqual(saved[1]['camera_raw_mm_x'],'4.0');self.assertEqual(saved[1]['confidence_left'],'0.0')
        self.assertEqual(saved[2]['camera_raw_mm_x'],'');self.assertEqual(saved[2]['valid'],'False')

    def test_exclude_candidate_and_sanitize_nonfinite(self):
        self.rec.include_candidates=False;rows=self.rows();rows[0].update(status='candidate',candidate_camera_mm=[1,2,3],confidence_left=float('nan'))
        self.rec.start(self.meta);self.rec.sample(self.frame(0),rows);self.rec.stop()
        self.assertEqual(self.read_rows()[0]['candidate_camera_mm_x'],'');self.assertEqual(self.read_rows()[0]['confidence_left'],'')

    def test_frozen_metadata_and_calibration_swap_stops_session(self):
        self.rec.start(self.meta);self.meta['config']['quality']['limit']=99
        self.rec.sample(self.frame(0),self.rows());self.now=500_000_000
        frame=self.frame(1);frame.calibration_file='other.npz'
        self.assertFalse(self.rec.sample(frame,self.rows()));self.assertFalse(self.rec.active)
        meta=json.loads((self.rec.path/'session.json').read_text())
        self.assertEqual(meta['config']['quality']['limit'],3);self.assertEqual(meta['stop_reason'],'calibration_changed')
        self.assertFalse(meta['video_recording'])

    def test_disk_full_error_preserves_written_rows_and_history(self):
        self.rec.start(self.meta);self.rec.sample(self.frame(0),self.rows());self.now=300_000_000
        with patch.object(self.rec._writer,'writerow',side_effect=OSError('disk full')):
            self.assertFalse(self.rec.sample(self.frame(1),self.rows()))
        self.assertFalse(self.rec.active);self.assertEqual(len(self.read_rows()),3)
        meta=json.loads((self.rec.path/'session.json').read_text());self.assertEqual(meta['status'],'error')
        self.assertIn('disk full',meta['error'])

    def test_start_failure_exit_and_rapid_sessions_no_overwrite(self):
        with patch('stereo_pose.outputs.csv_recorder.atomic_json',side_effect=OSError('denied')):
            with self.assertRaises(OSError):self.rec.start(self.meta)
        self.assertFalse(self.rec.active)
        dirs=[]
        for _ in range(3):
            self.now+=1_000_000_000;dirs.append(self.rec.start(self.meta));self.rec.sample(self.frame(0),self.rows());self.rec.stop('app_exit')
        self.assertEqual(len(set(dirs)),3)
        for p in dirs:
            self.assertEqual(json.loads((p/'session.json').read_text())['stop_reason'],'app_exit')

    def test_cleanup_does_not_touch_recordings_and_redirect_refused(self):
        self.rec.start(self.meta);self.rec.sample(self.frame(0),self.rows());self.rec.stop()
        before=(self.rec.path/'joints.csv').read_bytes()
        cleanup_project(self.root/'cal',self.root/'sessions',self.root,keep_latest=1,failed_days=0,verbose=False)
        self.assertEqual((self.rec.path/'joints.csv').read_bytes(),before)
        with self.assertRaises(Exception):
            cleanup_project(self.root/'cal',self.root/'recordings',self.root,failed_days=0,verbose=False)
        self.assertEqual((self.rec.path/'joints.csv').read_bytes(),before)
        for bad in [self.root/'sessions',self.root.parent/'outside']:
            with self.subTest(path=bad),self.assertRaises(Exception):CsvRecorder(bad,self.root).start(self.meta)

    def test_active_auto_calibration_survives_cleanup(self):
        import os
        auto=self.root/'cal'/'auto';auto.mkdir(parents=True)
        old=auto/'stereo_old.npz';old.write_bytes(b'synthetic');os.utime(old,(1,1))
        latest=auto/'stereo_new.npz';latest.write_bytes(b'synthetic')
        cleanup_project(self.root/'cal',self.root/'sessions',self.root,keep_latest=1,failed_days=0,verbose=False,protected_files=[old])
        self.assertTrue(old.exists());self.assertTrue(latest.exists())
