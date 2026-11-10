"""Immutable local observations reused by every projection model."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from stereo_pose.calibration.package import atomic_npz, file_sha256, read_bundle, utc_now

DATASET_FILENAME = 'observations.npz'


@dataclass
class Observations:
    path: Path
    metadata: dict
    objects: np.ndarray
    left: np.ndarray
    right: np.ndarray
    aligned_right: np.ndarray

    @property
    def size(self):
        return tuple(self.metadata['image_size'])

    @property
    def pairs(self):
        idx = self.metadata['accepted_indices']
        return ([self.objects[i] for i in idx], [self.left[i] for i in idx],
                list(self.aligned_right))

    def split(self):
        # Whole poses are held out. Keep the existing minimum for every fit.
        count = len(self.aligned_right)
        n = min(count // 5, count - max(3, self.metadata['fit_minimum']))
        holdout = np.linspace(1, count-1, n, dtype=int).tolist() if n > 0 else []
        return [i for i in range(count) if i not in holdout], holdout


def save_observations(session, obj, left, raw_right, aligned_right, alignment, size,
                      paths, settings, board, captures, fit_minimum):
    path = Path(session) / DATASET_FILENAME
    if path.exists():
        raise FileExistsError(f'observation dataset already exists: {path}')
    metadata = {
        'version': 1, 'dataset_id': path.parent.name, 'created_at_utc': utc_now(),
        'image_size': list(size), 'camera': settings or {}, 'board': list(board),
        'fit_minimum': fit_minimum,
        'samples': [{'left': 'left/' + l.name, 'right': 'right/' + r.name,
                     'left_sha256': file_sha256(l) if l.is_file() else None,
                     'right_sha256': file_sha256(r) if r.is_file() else None,
                     'capture': captures.get(l.name, {})} for l, r in paths],
        **alignment,
    }
    bundle = dict(objects=np.array(obj), left=np.array(left), right=np.array(raw_right),
                  aligned_right=np.array(aligned_right))
    atomic_npz(path, {**bundle, 'metadata_json': np.array(json.dumps(metadata, allow_nan=False))})
    return Observations(path, metadata, **bundle)


def load_observations(path):
    path = Path(path).resolve()
    b = read_bundle(path)
    m = json.loads(str(b['metadata_json'].item()))
    if m['version'] != 1 or not re.fullmatch(r'session_[A-Za-z0-9_]+', m['dataset_id']):
        raise ValueError('unsupported observation dataset version')
    o, l, r, a = [b[k] for k in ('objects', 'left', 'right', 'aligned_right')]
    cols, rows, square = m['board']
    n = cols * rows
    indices = m['accepted_indices']
    size = np.asarray(m['image_size'])
    if (o.ndim != 3 or o.shape[1:] != (n, 3) or
            l.shape != (len(o), n, 1, 2) or r.shape != l.shape or
            a.shape != (len(indices), n, 1, 2) or
            len(set(indices)) != len(indices) or any(not 0 <= i < len(o) for i in indices) or
            not 2 <= m['fit_minimum'] <= len(indices) or
            len(m['modes']) != len(indices) or len(m['samples']) != len(o) or
            any(mode not in ('direct', 'reversed_180') for mode in m['modes']) or
            size.shape != (2,) or np.any(size < 2) or np.any(size % 1) or
            square <= 0 or not all(np.isfinite(values).all() for values in (o, l, r, a))):
        raise ValueError('inconsistent calibration observation dataset')
    for i, corrected, mode in zip(indices, a, m['modes']):
        if not np.array_equal(corrected, r[i] if mode == 'direct' else r[i][::-1]):
            raise ValueError(f'corner correspondence mismatch at sample {i}')
    return Observations(path, m, o, l, r, a)
