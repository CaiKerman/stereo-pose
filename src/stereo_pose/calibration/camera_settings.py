"""Operator-confirmed webcam settings and observable capture-format metadata."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from stereo_pose.calibration.package import atomic_json

MANUAL_FIELDS = ('identity', 'fov', 'eis', 'firmware', 'imaging_mode')


def load_camera_notes(runtime_root):
    path = Path(runtime_root) / 'webcam_settings.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def save_camera_notes(runtime_root, notes):
    atomic_json(Path(runtime_root) / 'webcam_settings.json', notes)


def camera_modes(left, right, indices, notes):
    def property_value(cap, prop):
        try:
            value = float(cap.get(prop))
        except (cv2.error, TypeError, ValueError):
            return None
        return value if np.isfinite(value) and value > 0 else None

    modes = {}
    for side, cap, index in zip(('left', 'right'), (left, right), indices):
        w, h = (property_value(cap, prop) for prop in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = property_value(cap, cv2.CAP_PROP_FOURCC)
        code = None
        if fourcc:
            chars = [(int(fourcc) >> (8*i)) & 0xff for i in range(4)]
            if all(32 <= x < 127 for x in chars):
                code = bytes(chars).decode('ascii')
        try:
            backend = cap.getBackendName()
        except (AttributeError, cv2.error):
            backend = None
        modes[side] = {
            'index': int(index), 'reported_size': [int(w), int(h)] if w and h else None,
            'reported_fps': property_value(cap, cv2.CAP_PROP_FPS), 'reported_fourcc': code,
            'reported_backend': backend if isinstance(backend, str) else None,
            'operator_confirmed': {k: str(notes.get(str(index), {}).get(k) or '').strip() or None
                                   for k in MANUAL_FIELDS},
        }
    return modes


def compare_camera_modes(saved_context, current):
    warnings, mismatches = [], []
    for side, label in (('left', '左'), ('right', '右')):
        before = saved_context.get('modes', {}).get(side)
        after = current.get(side)
        if not before or not after:
            continue
        for key, name in (('reported_fourcc', '视频编码'), ('reported_backend', '采集后端')):
            a, b = before.get(key), after.get(key)
            if a and b and a != b:
                mismatches.append(f'{label}相机{name}已改变（{a} → {b}）')
        old, new = before.get('operator_confirmed', {}), after.get('operator_confirmed', {})
        if before.get('index') != after.get('index') and not (
                old.get('identity') and new.get('identity') and
                old['identity'].casefold() == new['identity'].casefold()):
            warnings.append(f'{label}相机编号变化，需确认物理相机与安装位置一致')
        for key, name in zip(MANUAL_FIELDS, ('设备标识', 'Webcam FOV', 'EIS', '固件', '成像模式')):
            a, b = old.get(key), new.get(key)
            if a and b and a.casefold() != b.casefold():
                mismatches.append(f'{label}相机{name}已改变（{a} → {b}）')
            elif a and not b:
                warnings.append(f'请确认{label}相机{name}仍为 {a}')
    return warnings, mismatches
