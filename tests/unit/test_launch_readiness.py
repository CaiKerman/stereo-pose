"""Download/update startup regressions with synthetic assets and no hardware."""
import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from stereo_pose.calibration.package import activate_calibration, file_sha256, read_bundle, restore_moved_calibration
from stereo_pose.capture.selection import CameraChoice, save_camera_choice
from stereo_pose.config import load_config
from tests.unit.test_world_alignment import synthetic_calibration


class TestLauncherReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / '新分支 with spaces'
        self.root.mkdir()
        self.config = self.root / 'config.json'
        self.model = self.root / 'weights' / 'my_pose.pt'
        self.model.parent.mkdir()
        self.model.write_bytes(b'synthetic local weights - never loaded')
        self.config.write_text(json.dumps({'pose': {'model': 'weights/my_pose.pt'},
            'camera': {'selection': {'startup_pick': False}}, 'owner_note': '保留'}))
        cwd = Path.cwd()
        spec = importlib.util.spec_from_file_location('readiness_run_me',
            Path(__file__).parents[2] / 'RUN_ME.py')
        self.launcher = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(self.launcher)
        finally:
            os.chdir(cwd)

    def launch(self):
        cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.launcher, 'ROOT', self.root))
            stack.enter_context(patch.object(self.launcher, 'check_dependencies'))
            stack.enter_context(patch.object(self.launcher, 'ensure_config', return_value=self.config))
            stack.enter_context(patch.object(self.launcher, 'stop', side_effect=RuntimeError('STOP')))
            stack.enter_context(patch('stereo_pose.diagnostics.doctor.run_doctor', return_value={}))
            stack.enter_context(patch('stereo_pose.diagnostics.doctor.render_doctor', return_value='offline test'))
            picker = stack.enter_context(patch('stereo_pose.capture.selection.run_camera_selection',
                return_value=CameraChoice(0, 1)))
            run_main = stack.enter_context(patch('stereo_pose.app.runner.main'))
            self.launcher.main()
        return picker, run_main

    def test_configured_model_in_chinese_path_starts_without_default_weights(self):
        picker, run_main = self.launch()
        picker.assert_not_called()
        run_main.assert_called_once()
        self.assertFalse((self.root / 'yolo11n-pose.pt').exists())

    def test_missing_configured_model_stops_before_any_picker_or_tracking(self):
        self.model.unlink()
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            self.launch()

    def test_moved_exact_selected_archive_is_recovered_before_tracking(self):
        old = self.root / 'removed parent' / 'selected.npz'
        old.parent.mkdir()
        synthetic_calibration(old)
        copied = self.root / 'runtime' / 'calibrations' / 'saved' / old.name
        copied.parent.mkdir(parents=True)
        copied.write_bytes(old.read_bytes())
        activate_calibration(self.config, old)
        digest = file_sha256(old)
        old.unlink()
        _, run_main = self.launch()
        run_main.assert_called_once()
        cfg = load_config(self.config)
        self.assertEqual(Path(cfg['stereo']['explicit_file']).resolve(), copied.resolve())
        self.assertEqual(cfg['stereo']['active_sha256'], digest)
        self.assertEqual(cfg['owner_note'], '保留')

    def test_moved_selection_never_substitutes_same_name_different_geometry(self):
        old = self.root / 'removed parent' / 'selected.npz'
        old.parent.mkdir()
        synthetic_calibration(old)
        activate_calibration(self.config, old)
        copied = self.root / 'runtime' / 'calibrations' / 'saved' / old.name
        copied.parent.mkdir(parents=True)
        b = read_bundle(old); b['P2'][0, 3] *= 2
        import numpy as np
        np.savez(copied, **b)
        old.unlink()
        before = self.config.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            self.launch()
        self.assertEqual(self.config.read_bytes(), before)

    def test_BOM_config_survives_load_camera_choice_and_world_activation(self):
        self.config.write_text(self.config.read_text(), encoding='utf-8-sig')
        self.assertEqual(load_config(self.config)['owner_note'], '保留')
        save_camera_choice(self.config, 2, 1)
        synthetic_calibration(self.root / 'stereo.npz')
        # Activation also needs to accept a BOM, before converting to plain UTF8.
        self.config.write_text(self.config.read_text(), encoding='utf-8-sig')
        activate_calibration(self.config, self.root / 'stereo.npz')
        cfg = load_config(self.config)
        self.assertEqual(cfg['owner_note'], '保留')
        self.assertEqual(cfg['camera']['left'], 2)

    def test_headless_OpenCV_is_reported_before_camera_selection(self):
        from types import SimpleNamespace
        cv = SimpleNamespace(getBuildInformation=lambda: 'OpenCV\n  GUI: NONE\n')
        with patch.object(self.launcher.importlib, 'import_module', return_value=cv), \
             patch.object(self.launcher, 'stop', side_effect=RuntimeError('dependency stop')) as stop:
            with self.assertRaisesRegex(RuntimeError, 'dependency stop'):
                self.launcher.check_dependencies()
        self.assertIn('headless', stop.call_args.args[1])

    def test_matching_relocated_old_auto_archive_is_protected_from_cleanup(self):
        from stereo_pose.persistence import cleanup_project
        auto=self.root/'runtime'/'calibrations'/'auto';auto.mkdir(parents=True)
        selected=synthetic_calibration(auto/'stereo_selected.npz')
        newer=synthetic_calibration(auto/'stereo_newer.npz')
        os.utime(selected,(1,1));os.utime(newer,(2,2))
        cfg=load_config(self.config)
        data=json.loads(self.config.read_text())
        data['stereo']={'load':'explicit','explicit_file':str(self.root/'removed'/'stereo_selected.npz'),
                        'active_sha256':file_sha256(selected)}
        self.config.write_text(json.dumps(data))
        cfg=load_config(self.config)
        restore_moved_calibration(self.config,cfg)
        cleanup_project(auto.parent,self.root/'runtime'/'sessions',runtime_root=self.root/'runtime',
                        keep_latest=1,protected_files=[cfg['stereo']['explicit_file']])
        self.assertTrue(selected.exists());self.assertTrue(newer.exists())

    def test_existing_changed_selected_archive_is_not_replaced_by_matching_copy(self):
        selected=synthetic_calibration(self.root/'selected.npz')
        copied=self.root/'runtime'/'calibrations'/'saved'/'copy.npz'
        copied.parent.mkdir(parents=True);copied.write_bytes(selected.read_bytes())
        activate_calibration(self.config,selected)
        selected.write_bytes(b'changed file')
        before=self.config.read_bytes()
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            restore_moved_calibration(self.config,load_config(self.config))
        self.assertEqual(self.config.read_bytes(),before)

    def test_missing_selection_without_hash_is_not_guessed_from_filename(self):
        copied=synthetic_calibration(self.root/'selected.npz')
        data=json.loads(self.config.read_text())
        data['stereo']={'load':'explicit','explicit_file':str(self.root/'removed'/copied.name)}
        self.config.write_text(json.dumps(data))
        before=self.config.read_bytes()
        with self.assertRaisesRegex(FileNotFoundError,'no recorded SHA'):
            restore_moved_calibration(self.config,load_config(self.config))
        self.assertEqual(self.config.read_bytes(),before)


class TestStartupResourceRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = load_config(None)
        self.cfg['cleanup']['enabled'] = False
        self.cfg['stereo']['calibration_dir'] = str(self.root / 'cal')
        from types import SimpleNamespace
        self.args = SimpleNamespace(left_cam=None, right_cam=None, device=None,
            model=None, config=str(self.root / 'config.json'))

    def test_second_camera_failure_releases_first_camera(self):
        from stereo_pose.app.runner import run
        first = Mock()
        with patch('stereo_pose.app.runner.resolve_device', return_value='cpu'), \
             patch('stereo_pose.app.runner.open_camera', side_effect=[first, RuntimeError('right failed')]), \
             patch('cv2.destroyAllWindows'):
            with self.assertRaisesRegex(RuntimeError, 'right failed'):
                run(self.args, self.cfg)
        first.release.assert_called_once()

    def test_model_or_publisher_init_failure_releases_both_cameras(self):
        from stereo_pose.app.runner import run
        for stage in ('PoseEstimator', 'build_publisher', 'RuntimeCalibration'):
            with self.subTest(stage=stage):
                left, right = Mock(), Mock()
                with ExitStack() as stack:
                    stack.enter_context(patch('stereo_pose.app.runner.resolve_device', return_value='cpu'))
                    stack.enter_context(patch('stereo_pose.app.runner.open_camera', side_effect=[left, right]))
                    stack.enter_context(patch('stereo_pose.app.runner.PoseEstimator'))
                    publisher=stack.enter_context(patch('stereo_pose.app.runner.build_publisher'))
                    stack.enter_context(patch('stereo_pose.app.runner.' + stage, side_effect=RuntimeError('init failed')))
                    stack.enter_context(patch('cv2.destroyAllWindows'))
                    with self.assertRaisesRegex(RuntimeError, 'init failed'):
                        run(self.args, self.cfg)
                left.release.assert_called_once(); right.release.assert_called_once()
                if stage == 'RuntimeCalibration':
                    publisher.return_value.close.assert_called_once()
