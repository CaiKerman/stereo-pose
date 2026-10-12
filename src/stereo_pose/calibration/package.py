"""Immutable stereo+world NPZ and explicit active preference; no image IO."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from stereo_pose.coordinates.rigid import RigidTransform
from stereo_pose.persistence import ensure_managed_location

GEOMETRY_KEYS = ('K1','D1','K2','D2','R','T','E','F','R1','R2','P1','P2','Q','image_size','square_mm')
WORLD_KEYS = ('world_R','world_t_mm','world_coordinate_name','world_schema_version','world_metadata_json')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read_bundle(path):
    with np.load(path, allow_pickle=False) as f:
        return {k: f[k].copy() for k in f.files}


def stereo_fingerprint(bundle):
    h = hashlib.sha256()
    for k in GEOMETRY_KEYS:
        if k in bundle:
            a = np.asarray(bundle[k])
            h.update(json.dumps([k,a.dtype.str,list(a.shape)],separators=(',',':')).encode())
            h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def validate_stereo_bundle(bundle):
    for key, shape in [('K1',(3,3)),('K2',(3,3)),('R1',(3,3)),('R2',(3,3)),('P1',(3,4)),('P2',(3,4))]:
        a=np.asarray(bundle.get(key),dtype=float)
        if a.shape != shape or not np.all(np.isfinite(a)):raise ValueError(f'invalid {key} shape/finite calibration values')
    for key in ('D1','D2'):
        a=np.asarray(bundle.get(key),dtype=float)
        if a.size not in (4,5,8,12,14) or a.ndim not in (1,2) or (a.ndim==2 and 1 not in a.shape) or not np.all(np.isfinite(a)):
            raise ValueError(f'invalid {key} distortion vector')


def load_registration(path, actual_size=None):
    """Return (valid registration, warnings); bad W never becomes accepted W."""
    try:
        b = read_bundle(path)
        validate_stereo_bundle(b)
    except (ValueError, KeyError, TypeError, OSError) as e:
        return None, [f'WORLD INVALID: unreadable/invalid calibration package: {e}']
    if not any(k in b for k in WORLD_KEYS): return None, []
    try:
        if not all(k in b for k in WORLD_KEYS): raise ValueError('incomplete world fields')
        if str(b['world_schema_version'].item()) != '1': raise ValueError('unsupported world schema')
        m = json.loads(str(b['world_metadata_json'].item()))
        if m['stereo_fingerprint'] != stereo_fingerprint(b): raise ValueError('stereo fingerprint mismatch')
        if m['source_system'] != 'rectified_left_camera' or m['unit'] != 'mm': raise ValueError('invalid source frame/units')
        if actual_size is not None:
            if 'image_size' not in b or tuple(np.asarray(b['image_size']).reshape(-1)) != tuple(actual_size):
                raise ValueError('world registration image_size mismatch or unverified')
        t = RigidTransform(b['world_R'], b['world_t_mm'])
        name = str(b['world_coordinate_name'].item())
        if not name.strip(): raise ValueError('empty frame name')
        if m.get('mode') != 'zero' and m.get('up_confirmed') is not True: raise ValueError('world-up not confirmed')
        return {'transform':t,'name':name,'metadata':m}, []
    except (ValueError, KeyError, TypeError) as e:
        return None, [f'WORLD INVALID: {e}; re-register W']


def load_readout_registration(path, actual_size=None):
    """Prefer a valid owner W/zero; otherwise derive the default camera midpoint.

    Default geometry is never saved as a physically confirmed world fit. It is
    recomputed from the selected stereo artifact on restart and on stereo solve.
    Invalid saved W remains visibly invalid even when the default is available.
    """
    registration, warnings = load_registration(path, actual_size)
    if registration is not None:
        return registration, warnings
    try:
        from stereo_pose.coordinates.camera_midpoint import camera_midpoint_registration
        b = read_bundle(path)
        validate_stereo_bundle(b)
        if actual_size is not None and 'image_size' in b:
            if tuple(np.asarray(b['image_size']).reshape(-1)) != tuple(actual_size):
                raise ValueError('capture resolution differs from stereo calibration; recalibrate C -> R')
        registration = camera_midpoint_registration(b)
        registration['metadata']['stereo_fingerprint'] = stereo_fingerprint(b)
        if actual_size is not None and 'image_size' not in b:
            warnings.append('DEFAULT FRAME: legacy calibration resolution unverified; confirm capture size unchanged')
        return registration, warnings
    except (ValueError, KeyError, TypeError, OSError) as e:
        return None, warnings + [f'DEFAULT FRAME UNAVAILABLE: {e}; CAMERA FRAME only']


def atomic_json(path, data):
    """Replace a preference/manifest only after a fully flushed staging write."""
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=p.name+'.', suffix='.partial', dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temporary,p)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_npz(path, bundle):
    """Publish a complete NPZ without replacing any existing archive."""
    final=Path(path);final.parent.mkdir(parents=True,exist_ok=True)
    temporary=final.with_name(final.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with temporary.open('xb') as f:
            np.savez(f,**bundle);f.flush();os.fsync(f.fileno())
        if os.name == 'nt':os.rename(temporary,final)
        else:os.link(temporary,final)
        return final
    finally:temporary.unlink(missing_ok=True)


def save_registered(source, registration, calibration_dir, runtime_root):
    """Keep all original stereo arrays/shapes; publish unique saved NPZ atomically."""
    saved = ensure_managed_location(Path(calibration_dir)/'saved', runtime_root, 'world saved directory')
    saved.mkdir(parents=True, exist_ok=True)
    b = read_bundle(source)
    if any(np.asarray(a).dtype.hasobject for a in b.values()): raise ValueError('pickle/object calibration is forbidden')
    validate_stereo_bundle(b)
    # Validate stereo component with the same reader as runtime before publication.
    from stereo_pose.geometry import StereoTriangulator
    StereoTriangulator(b)
    t = registration['transform']
    RigidTransform(t.R,t.t)
    name = str(registration['name']).strip()
    if not name: raise ValueError('frame name is required')
    m = dict(registration['metadata'])
    if 'image_size' not in b and 'capture_image_size' in m:
        b['image_size']=np.asarray(m['capture_image_size'],dtype=np.int64)
    m.update(stereo_fingerprint=stereo_fingerprint(b),source_system='rectified_left_camera',
             unit='mm',created_at=utc_now(),transform_direction='C_to_W')
    if m.get('mode') != 'zero' and m.get('up_confirmed') is not True: raise ValueError('confirm physically upward +Z before saving')
    b.update(world_R=t.R,world_t_mm=t.t,world_coordinate_name=np.array(name),world_schema_version=np.array('1'),
             world_metadata_json=np.array(json.dumps(m,ensure_ascii=False,allow_nan=False)))
    final=saved/('world_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex+'.npz')
    return atomic_npz(final,b)


def activate_calibration(config_path, path):
    """Persist exact NPZ + SHA without discarding unrelated user settings."""
    p=Path(config_path)
    data=json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
    if not isinstance(data,dict) or not isinstance(data.get('stereo',{}),dict): raise ValueError('config must contain object stereo')
    read_bundle(path)
    stereo=dict(data.get('stereo',{}))
    stereo.update(load='explicit',explicit_file=str(Path(path).resolve()),active_sha256=file_sha256(path))
    data['stereo']=stereo
    atomic_json(p,data)
    return stereo


def restore_moved_calibration(config_path, cfg):
    """Recover a moved explicit selection only by the stored complete-file SHA.

    Never pick newer geometry or trust a coincident filename. Search only the
    configured managed calibration directory; archives are not changed. Atomically
    update the selection after validating the exact archive, preserving settings.
    RUN_ME calls this before its camera picker and before startup cleanup.
    """
    stereo = cfg['stereo']
    if stereo.get('load') != 'explicit':
        return None
    selected = stereo.get('explicit_file')
    if not selected:
        raise ValueError('stereo.load=explicit requires a selected NPZ path')
    root = Path(config_path).resolve().parent
    path = Path(selected)
    if not path.is_absolute():
        path = root / path
    expected = stereo.get('active_sha256')
    if expected is not None and (not isinstance(expected, str) or len(expected) != 64 or
                                any(ch not in '0123456789abcdef' for ch in expected)):
        raise ValueError('invalid selected calibration SHA-256; reselect the known NPZ')
    if path.is_file():
        if expected and file_sha256(path) != expected:
            raise ValueError('selected calibration SHA-256 mismatch; changed NPZ will not be substituted')
        return path
    if not expected:
        raise FileNotFoundError(f'Selected calibration missing: {path}; restore the original NPZ (no recorded SHA for safe relocation)')
    def anchored(value):
        p = Path(value)
        return p if p.is_absolute() else root / p
    cal_dir = ensure_managed_location(anchored(stereo['calibration_dir']),
        anchored(cfg['runtime']['root']), 'calibration relocation search')
    candidates = sorted(cal_dir.rglob('*.npz'), key=lambda p: (p.name != path.name, str(p)))
    for candidate in candidates:
        # Do not follow an archive symlink outside the configured managed root.
        if not candidate.resolve().is_relative_to(cal_dir):
            continue
        try:
            matches = candidate.is_file() and file_sha256(candidate) == expected
        except OSError:
            continue
        if matches:
            validate_stereo_bundle(read_bundle(candidate))
            # A preference write failure must report the actual error rather
            # than pretending the matching archive was missing.
            stereo.update(activate_calibration(config_path, candidate))
            print(f'[setup] RESTORED exact moved calibration: {path} -> {candidate} (SHA-256 unchanged)')
            return candidate
    raise FileNotFoundError(f'Selected calibration missing: {path}; copy its unchanged runtime/calibrations folder into this project. No identical SHA-256 archive found; no latest-file fallback.')
