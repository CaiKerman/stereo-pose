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
