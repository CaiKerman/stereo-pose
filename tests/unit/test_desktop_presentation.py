"""Offline UI semantics and display dimensions; no Tk/camera/GPU required."""
import base64
import copy
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import cv2

from stereo_pose.app.presentation import (Action, PendingAction, fit_size, initial_size,
    readout_cells, tracking_view, calibration_view, coordinate_label)
from stereo_pose.app.desktop import create_display, HighGuiDisplay, encode_tk_png
from stereo_pose.app.world_form import save_form_rows, load_form_rows


class TestDisplayContract(unittest.TestCase):
    def test_tk_png_preview_roundtrip_preserves_bgr_pixels(self):
        frame = np.zeros((36,64,3),dtype=np.uint8)
        frame[:] = [15,75,230]
        encoded = encode_tk_png(frame)
        decoded = cv2.imdecode(np.frombuffer(base64.b64decode(encoded),dtype=np.uint8),
                               cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(decoded, frame)

    def test_tk_png_encoding_failure_reports_error(self):
        with patch('stereo_pose.app.desktop.cv2.imencode',return_value=(False,None)):
            with self.assertRaisesRegex(RuntimeError,'encode camera preview'):
                encode_tk_png(np.zeros((4,4,3),np.uint8))

    def test_fit_preserves_whole_image_for_common_and_portrait_screens(self):
        for screen in [(800,600),(1024,768),(1366,768),(1920,1080),(3840,2160),(600,900)]:
            with self.subTest(screen=screen):
                initial=initial_size(*screen)
                self.assertLessEqual(initial[0],screen[0]);self.assertLessEqual(initial[1],screen[1])
                for image in [(1280,720),(640,480),(1920,1080),(720,1280)]:
                    width,height=fit_size(image,initial)
                    self.assertLessEqual(width,initial[0]);self.assertLessEqual(height,initial[1])
                    self.assertLessEqual(abs(width-height*image[0]/image[1]),2)

    def test_invalid_display_size_rejected(self):
        for size in [(0,720),(-1,720),(1280,0)]:
            with self.subTest(size=size),self.assertRaises(ValueError):fit_size(size,(100,100))

    def test_high_dpi_initial_size_grows_but_stays_inside_work_area(self):
        for scale in (1.25,1.5,2.):
            with self.subTest(scale=scale):
                width,height=initial_size(3840,2160,scale)
                self.assertGreater(width,1320);self.assertGreater(height,900)
                self.assertLessEqual(width,3840);self.assertLessEqual(height,2160)

    def test_click_dispatch_disabled_and_one_pending_command(self):
        queue=PendingAction();queue.configure('tracking',[Action(ord('w'),'world',False),Action(ord('c'),'cal')])
        queue.offer(ord('w'));self.assertEqual(queue.take(),255)
        queue.offer(ord('c'));queue.offer(ord('c'));self.assertEqual(queue.take(),ord('c'))
        self.assertEqual(queue.take(),255)

    def test_stale_click_cannot_cross_modes_but_keyboard_semantics_retained(self):
        queue=PendingAction();queue.configure('tracking',[Action(ord('c'),'cal')]);queue.offer(ord('c'))
        queue.configure('calibration',[Action(ord('r'),'solve',False)])
        self.assertEqual(queue.take(),255)
        queue.offer(ord('r'),keyboard=True);self.assertEqual(queue.take(),ord('r'))

    def test_candidate_and_missing_never_render_as_accepted_coordinates(self):
        rows=[{'joint':'left_eye','status':s,'reason':'test','world_filtered_mm':[1,2,3],
            'camera_filtered_mm':[4,5,6],'candidate_world_mm':[7,8,9]} for s in ['accepted','candidate','missing','rejected']]
        before=copy.deepcopy(rows);cells=readout_cells(rows,{'name':'world'})
        self.assertEqual(cells[0][1:4],('1.0','2.0','3.0'))
        for row in cells[1:]:self.assertEqual(row[1:4],('—','—','—'))
        self.assertEqual(rows,before)

    def test_frame_label_keeps_default_and_zero_provenance(self):
        self.assertIn('假定向上',coordinate_label({'name':'default','metadata':{'mode':'camera_midpoint'}}))
        self.assertIn('轴向保持不变',coordinate_label({'name':'ZERO','metadata':{'mode':'zero'}}))

    def test_no_calibration_disables_world_and_record_buttons(self):
        view=tracking_view([],None,calibrated=False,recording=False,record_status='OFF',smoothing=True,cameras=(1,2),fps='30fps')
        actions={a.key:a for a in view['actions']}
        self.assertFalse(actions[ord('w')].enabled);self.assertFalse(actions[ord('t')].enabled)
        self.assertTrue(actions[ord('c')].enabled)

    def test_calibration_data_shortage_is_not_called_movement(self):
        cal=SimpleNamespace(current={'capture_reason':'insufficient_observations','valid':True,'good_area':True},
            samples=[],can_solve=lambda:False,target_pairs=20,min_pairs=12,auto_capture=True,
            diversity_threshold=.12,readiness=lambda:0)
        view=calibration_view(cal)
        self.assertIn('积累有效检测',view['hint']);self.assertNotIn('移动',view['hint'])
        actions={a.key:a for a in view['actions']}
        self.assertTrue(actions[ord(' ')].enabled);self.assertFalse(actions[ord('r')].enabled)

    def test_missing_tk_falls_back_without_crashing_pipeline(self):
        with patch('stereo_pose.app.desktop.desktop_available',return_value=True),patch('stereo_pose.app.desktop.DesktopDisplay.__init__',side_effect=ImportError('no Tk')):
            self.assertIsInstance(create_display(),HighGuiDisplay)

    def test_manual_duplicate_notice_survives_next_detection_until_backend_expiry(self):
        cal=SimpleNamespace(current={'capture_reason':'duplicate_pose'},samples=[1],
            can_solve=lambda:False,target_pairs=20,min_pairs=12,auto_capture=True,
            diversity_threshold=.12,readiness=lambda:0,last_capture_notice='MANUAL captured pair 1 | DUPLICATE WARNING (force retained)',
            _current_timestamp=1.,_notice_until=2.)
        self.assertIn('高度重复',calibration_view(cal)['notice'])
        cal._current_timestamp=3.
        self.assertEqual(calibration_view(cal)['notice'],'')

    def test_highgui_has_resizable_window_and_close_returns_quit(self):
        display=HighGuiDisplay()
        with patch('stereo_pose.app.desktop.configure_highgui',return_value=True) as configure,patch('cv2.imshow'),patch('cv2.waitKey',return_value=-1),patch('cv2.getWindowProperty',return_value=0):
            self.assertEqual(display.show(np.zeros((240,320,3),np.uint8)),ord('q'))
            configure.assert_called_once()


class TestWorldFormPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'references.csv'
        self.path.write_text('prior contents')

    def row(self,identifier,xyz):
        return dict(zip(('dictionary','id','feature_type','X_mm','Y_mm','Z_mm'),['DICT_4X4_50',str(identifier),'center',*xyz]))

    def test_full_form_omits_unused_blank_templates_but_preserves_explicit_features(self):
        row=self.row(3,['1','2','3']);row['feature_type']='corner2'
        save_form_rows(self.path,[row,self.row(4,['','',''])])
        self.assertEqual(load_form_rows(self.path),[row])

    def test_zero_uses_only_first_row_without_requiring_other_points(self):
        first=self.row(7,['0','0','0'])
        save_form_rows(self.path,[first,self.row(4,['','',''])],zero=True)
        self.assertEqual(load_form_rows(self.path),[first])

    def test_partial_coordinates_do_not_overwrite_existing_file(self):
        old=self.path.read_bytes()
        with self.assertRaises(ValueError):save_form_rows(self.path,[self.row(3,['1','','3'])])
        self.assertEqual(self.path.read_bytes(),old)

    def test_failed_atomic_publish_retains_existing_file_and_removes_temp(self):
        old=self.path.read_bytes()
        with patch('stereo_pose.app.world_form.os.replace',side_effect=OSError('disk error')),self.assertRaises(OSError):
            save_form_rows(self.path,[self.row(3,['1','2','3'])])
        self.assertEqual(self.path.read_bytes(),old);self.assertEqual(list(self.path.parent.glob('*.tmp')),[])
