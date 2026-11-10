"""Synthetic native Tk smoke (no cameras/models); run with a desktop or Xvfb.

PYTHONPATH=src:. python tools/smoke_desktop_ui.py
Normal headless regression is tests/unit/test_desktop_presentation.py instead.
"""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from stereo_pose.app.desktop import DesktopDisplay
from stereo_pose.app.presentation import tracking_view, calibration_view
from stereo_pose.app.world_form import WorldForm
from stereo_pose.app.world_setup import run_world_setup
from stereo_pose.calibration.package import read_bundle
from stereo_pose.geometry import StereoTriangulator
from stereo_pose.config import load_config
from tests.unit.test_world_alignment import synthetic_calibration


class NativeSmoke(unittest.TestCase):
    def setUp(self):
        self.ui=DesktopDisplay();self.addCleanup(self.ui.close)
        self.callbacks=[]
        self.ui.root.report_callback_exception=lambda *args:self.callbacks.append(args)
        self.image=np.zeros((360,640,3),np.uint8);self.image[:]=[45,30,20]
        self.rows=[{'joint':'left_eye','status':'accepted','reason':'',
                    'camera_filtered_mm':[1,2,3],'world_filtered_mm':[4,5,6]}]
        self.view=tracking_view(self.rows,None,calibrated=True,recording=False,record_status='未录制',
                               smoothing=True,cameras=(1,2),fps='30fps')
        self.ui.show(pair=(self.image,self.image.copy()),view=self.view)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'references.csv'
        self.path.write_text('dictionary,id,feature_type,X_mm,Y_mm,Z_mm\nDICT_4X4_50,0,center,0,0,0\nDICT_4X4_50,1,center,100,0,0\nDICT_4X4_50,2,center,0,100,0\n')

    def tearDown(self):
        self.assertEqual(self.callbacks,[],str(self.callbacks))

    def test_common_and_narrow_windows_keep_controls_and_image_ratio(self):
        for size in [(800,600),(1024,768),(1366,768),(1920,1080),(600,900),(520,420)]:
            with self.subTest(size=size):
                self.ui.root.geometry(f'{size[0]}x{size[1]}')
                for _ in range(2):self.ui.show(pair=(self.image,self.image),view=self.view)
                self.assertTrue(self.ui.tree.winfo_ismapped())
                for button in self.ui.buttons:
                    self.assertLessEqual(button.winfo_x()+button.winfo_width(),self.ui.toolbar.winfo_width()+2)
                    self.assertLess(button.winfo_rooty()+button.winfo_height(),self.ui.root.winfo_rooty()+self.ui.root.winfo_height())
                for photo in self.ui.pair.photos:
                    self.assertIsNotNone(photo)
                    self.assertLessEqual(abs(photo.width()-photo.height()*640/360),2)

    def test_first_paint_recovers_collapsed_camera_sash(self):
        # Reproduce the actual reported state (a 1-pixel camera pane).
        self.ui.panes.sashpos(0,1)
        self.ui.root.update_idletasks()
        self.assertLess(self.ui.pair.frame.winfo_height(), 80)
        self.ui._preview_split_initialized=False  # emulate first native paint
        self.ui.show(pair=(self.image,self.image),view=self.view)
        self.assertGreater(self.ui.pair.frame.winfo_height(), 80)
        self.assertGreater(self.ui.pair.labels[0].winfo_height(), 20)

    def test_camera_viewport_starts_visible_and_survives_mode_changes(self):
        # Regression for owner Windows screenshot: live video pane was only a
        # thin strip above the coordinate table, despite valid camera frames.
        for width,height in ((1320,900),(1024,768),(800,600)):
            with self.subTest(size=(width,height)):
                self.ui.root.geometry(f'{width}x{height}')
                self.ui.show(pair=(self.image,self.image),view=self.view)
                self.ui.show(pair=(self.image,self.image),view=self.view)
                self.assertGreater(self.ui.pair.frame.winfo_height(), 80)
                self.assertGreater(self.ui.pair.labels[0].winfo_height(), 20)
                self.assertGreater(self.ui.pair.labels[1].winfo_height(), 20)
                self.assertGreater(self.ui.panes.sashpos(0), 80)
        cal=SimpleNamespace(current={'capture_reason':'insufficient_observations'},samples=[],
            can_solve=lambda:False,target_pairs=24,min_pairs=12,auto_capture=True,
            diversity_threshold=.12,readiness=lambda:0)
        self.ui.show(pair=(self.image,self.image),view=calibration_view(cal))
        self.assertGreater(self.ui.pair.frame.winfo_height(), 80)
        self.ui.show(pair=(self.image,self.image),view=self.view)
        self.assertGreater(self.ui.pair.frame.winfo_height(), 80)

    def test_camera_preview_is_visible_and_follows_each_new_frame(self):
        # Previous checks only saw that an image object existed, not its pixels.
        self.ui.show(pair=(self.image,self.image),view=self.view)
        for photo in self.ui.pair.photos:
            self.assertIsNotNone(photo)
            self.assertEqual(tuple(photo.get(photo.width()//2,photo.height()//2)),(20,30,45))
        newer=self.image.copy();newer[:]=[12,140,238]
        self.ui.show(pair=(newer,self.image),view=self.view)
        left,right=self.ui.pair.photos
        self.assertEqual(tuple(left.get(left.width()//2,left.height()//2)),(238,140,12))
        self.assertEqual(tuple(right.get(right.width()//2,right.height()//2)),(20,30,45))
        self.ui.root.geometry('800x600')
        self.ui.show(pair=(newer,self.image),view=self.view)
        self.ui.show(pair=(newer,self.image),view=self.view)
        self.assertEqual(tuple(self.ui.pair.photos[0].get(3,3)),(238,140,12))

    def test_manual_npz_load_and_save_actions_dispatch_from_real_buttons(self):
        actions={a.key:a for a in self.view['actions']}
        self.assertTrue(actions[ord('l')].enabled)
        self.assertTrue(actions[ord('k')].enabled)
        for key in (ord('l'),ord('k')):
            self.ui.show(pair=(self.image,self.image),view=self.view)
            button=next(b for a,b in zip(self.view['actions'],self.ui.buttons) if a.key==key)
            button.invoke()
            self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),key)

    def test_projection_dropdowns_and_separate_activation_button(self):
        cal = SimpleNamespace(current={}, samples=[], dataset=None, results={}, failures={},
            can_solve=lambda:False, target_pairs=24, min_pairs=12, auto_capture=True,
            diversity_threshold=.12, readiness=lambda:0)
        self.assertEqual(self.ui.projection_options(), ('pinhole', 0, False))
        view = calibration_view(cal, options=self.ui.projection_options())
        self.ui.show(pair=(self.image,self.image),view=view)
        self.assertTrue(self.ui.projection_bar.winfo_ismapped())
        self.assertFalse(next(a for a in view['actions'] if a.key==ord('a')).enabled)
        self.ui.model_box.current(2)
        self.ui.framing_box.current(1)
        self.ui.preview_box.current(1)
        self.assertEqual(self.ui.projection_options(), ('fisheye', 1, True))
        self.ui.show(pair=(self.image,self.image),view=self.view)
        self.assertFalse(self.ui.projection_bar.winfo_ismapped())

    def test_button_and_keyboard_dispatch_once(self):
        self.ui.buttons[0].invoke()
        self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),ord('c'))
        self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),255)
        self.ui._keyboard(SimpleNamespace(widget=self.ui.root,keysym='t',char='t'))
        self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),ord('t'))

    def test_context_buttons_and_candidate_rows(self):
        cal=SimpleNamespace(current={'capture_reason':'insufficient_observations'},samples=[],
            can_solve=lambda:False,target_pairs=24,min_pairs=12,auto_capture=True,diversity_threshold=.12,readiness=lambda:0)
        self.ui.show(pair=(self.image,self.image),view=calibration_view(cal))
        self.assertEqual(str(self.ui.buttons[0]['state']),'disabled')
        self.assertEqual(str(self.ui.buttons[1]['state']),'disabled')
        rows=[{**self.rows[0],'status':'candidate','reason':'epipolar'}]
        view=tracking_view(rows,None,calibrated=True,recording=False,record_status='未录制',smoothing=True,cameras=(1,2),fps='30fps')
        self.ui.show(pair=(self.image,self.image),view=view)
        self.assertEqual(tuple(self.ui.tree.item(self.ui.tree.get_children()[0],'values')[1:4]),('—','—','—'))

    def test_readonly_help_focus_keeps_quit_and_record_shortcuts(self):
        self.ui.tabs.select(2)
        for key in ('t','q'):
            self.ui._keyboard(SimpleNamespace(widget=self.ui.help_text,keysym=key,char=key))
            self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),ord(key))

    def form(self):
        form=WorldForm(self.ui,self.path,{0:None,1:None,2:None},{0:None,1:None,2:None},'DICT_4X4_50','WORLD')
        self.addCleanup(form.close)
        return form

    def test_world_setup_frozen_camera_pane_starts_visible_and_recovers_from_collapse(self):
        form=self.form()
        form.root.update()
        form.panes.sashpos(0,1)  # reproduce owner screenshot: only a thin divider
        form.root.update_idletasks()
        self.assertLess(form.pair.frame.winfo_height(),80)
        form.show((self.image,self.image),zero=False,up=False,candidate=None,
                  report={},error='Enter real XYZ in CSV, save it, then R=fit')
        self.assertGreater(form.pair.frame.winfo_height(),80)
        self.assertGreater(form.pair.labels[0].winfo_height(),20)
        self.assertGreater(form.pair.labels[1].winfo_height(),20)
        self.assertTrue(all(photo is not None for photo in form.pair.photos))
        # The recovered size remains under operator control after first layout.
        form.panes.sashpos(0,180);form.root.update_idletasks()
        form.show((self.image,self.image),zero=False,up=False,candidate=None,
                  report={},error='Enter real XYZ in CSV, save it, then R=fit')
        self.assertAlmostEqual(form.panes.sashpos(0),180,delta=10)

    def test_typing_in_reference_entry_never_dispatches_shortcuts(self):
        form=self.form()
        entry=next(child for child in form.input.winfo_children() if child.winfo_class()=='TEntry')
        before=form.pending
        form.keyboard(SimpleNamespace(widget=entry,keysym='r',char='r'))
        self.assertEqual(form.pending,before)

    def test_changed_reference_cannot_save_stale_preview(self):
        form=self.form()
        candidate={'metadata':{'reference_points':[{'xyz_mm':[0,0,0]}]}}
        form.show((self.image,self.image),zero=False,up=True,candidate=candidate,report={'rms_mm':0,'max_mm':0},error='')
        self.assertEqual(str(form.save_button['state']),'normal')
        form.entries['X_mm'].set('15');form.update_row()
        form.show((self.image,self.image),zero=False,up=True,candidate=candidate,report={},error='')
        self.assertEqual(str(form.save_button['state']),'disabled')
        self.assertTrue(form.dirty)

    def test_uncommitted_entry_edit_invalidates_preview_immediately(self):
        form=self.form()
        candidate={'metadata':{'reference_points':[{'xyz_mm':[0,0,0]}]}}
        form.show((self.image,self.image),zero=False,up=True,candidate=candidate,report={},error='')
        form.entries['X_mm'].set('15')
        self.assertTrue(form.dirty)
        self.assertEqual(str(form.save_button['state']),'disabled')

    def test_same_event_batch_zero_then_fit_delivers_mode_first(self):
        form=self.form();form.zero.set(True);form.change_mode();form.fit()
        key=form.show((self.image,self.image),zero=False,up=False,candidate=None,report={},error='')
        self.assertEqual(key,ord('z'))
        key=form.show((self.image,self.image),zero=True,up=False,candidate=None,report={},error='')
        self.assertEqual(key,ord('r'))
        self.assertEqual(len(self.path.read_text().splitlines()),2)

    def test_native_world_fit_confirmation_save_and_exact_reload(self):
        root=Path(self.tmp.name);cal=synthetic_calibration(root/'old.npz');tri=StereoTriangulator(cal)
        cfg=load_config(None);cfg['runtime']['root']=str(root);cfg['world']['reference_file']=str(self.path)
        cfg['stereo']['calibration_dir']=str(root/'cal');config=root/'config.json';config.write_text(json.dumps(cfg))
        left={};right={}
        for i,center in enumerate([[0,0,1000],[100,0,1000],[0,100,1000]]):
            points=np.array([[-20,-20,0],[20,-20,0],[20,20,0],[-20,20,0]])+center
            for P,out in [(tri.P1,left),(tri.P2,right)]:
                p=np.c_[points,np.ones(4)]@P.T;out[i]=p[:,:2]/p[:,2:]
        original=WorldForm.show;step={'n':0}
        def drive(form,images,**state):
            original(form,images,**state)
            step['n']+=1
            if step['n']==1:form.fit();key=form.pending;form.pending=255;return key
            if step['n']==2:return ord('u')
            return 13
        before=cal.read_bytes()
        with patch.object(WorldForm,'show',drive):
            saved=run_world_setup(frame_left=np.zeros((720,1280,3),np.uint8),frame_right=np.zeros((720,1280,3),np.uint8),
                triangulator=tri,calib_path=cal,config_path=config,cfg=cfg,desktop=self.ui,
                detector=Mock(side_effect=[left,right]))
        self.assertTrue(saved.is_file());self.assertEqual(cal.read_bytes(),before)
        self.assertIn('world_R',read_bundle(saved))
        self.assertEqual(load_config(config)['stereo']['explicit_file'],str(saved.resolve()))

    def test_close_requests_quit_and_modal_cancel(self):
        form=self.form();self.ui._request_close()
        self.assertEqual(form.show((self.image,self.image),zero=False,up=False,candidate=None,report={},error=''),27)
        self.assertEqual(self.ui.show(pair=(self.image,self.image),view=self.view),ord('q'))


if __name__=='__main__':
    unittest.main(verbosity=2)
