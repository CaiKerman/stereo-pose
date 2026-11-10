"""Offline calibration refits and NPZ audit. All observations stay on this PC."""
from __future__ import annotations

import argparse
import json
import sys
import time

import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from stereo_pose.calibration.collection import RuntimeCalibration
from stereo_pose.calibration.experiment import mapping_report, reference_errors, write_mapping_plot
from stereo_pose.calibration.package import (atomic_json, file_sha256, load_registration, read_bundle,
                                              stereo_fingerprint)
from stereo_pose.config import load_config
from stereo_pose.geometry.projection import CAMERA_MODELS, camera_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='local config.json (optional)')
    commands = parser.add_subparsers(dest='command', required=True)
    audit = commands.add_parser('audit', help='audit one or more NPZ files against the same controls')
    audit.add_argument('archives', nargs='+', type=Path)
    audit.add_argument('--image-size', nargs=2, type=int, metavar=('WIDTH', 'HEIGHT'),
                       help='confirmed raw dimensions for legacy files with no image_size')
    audit.add_argument('--references', type=Path, help='independent reference observations in JSON')
    fit = commands.add_parser('fit', help='refit saved observations without opening cameras')
    fit.add_argument('observations', type=Path)
    fit.add_argument('--model', choices=(*CAMERA_MODELS, 'all'), default='all')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.command == 'fit':
        calibrator = RuntimeCalibration(cfg['stereo'], cfg['calibration_runtime'])
        calibrator.open_dataset(args.observations)
        failed = False
        for model in CAMERA_MODELS if args.model == 'all' else (args.model,):
            try:
                print(calibrator.solve(model, stage=True, quality=cfg['quality'])['report_path'])
            except ValueError as error:
                print(error, file=sys.stderr)
                failed = True
        return int(failed)
    references = json.loads(args.references.read_text(encoding='utf-8')) if args.references else None
    out = Path(cfg['runtime']['root']) / 'diagnostics' / 'calibration' / f'audit_{time.time_ns()}'
    out.mkdir(parents=True, exist_ok=False)
    failed = False
    for i, archive in enumerate(args.archives):
        path = out / f'{i+1}_{archive.stem}.json'
        report = {'path': str(archive.resolve()), 'validation_type': 'geometric_consistency_only',
                  'opencv_version': cv2.__version__, 'audit_version': 'issue9-projection-v1'}
        try:
            bundle = read_bundle(archive)
            size = bundle.get('image_size', args.image_size)
            if size is None:
                raise ValueError('legacy NPZ without image_size: supply --image-size WIDTH HEIGHT')
            if args.image_size and tuple(size) != tuple(args.image_size):
                raise ValueError('specified image_size differs from the NPZ')
            bundle.setdefault('image_size', size)
            registration, warnings = load_registration(archive, tuple(size))
            report.update(camera_model=camera_model(bundle), npz_sha256=file_sha256(archive),
                          stereo_fingerprint=stereo_fingerprint(read_bundle(archive)),
                          image_size=list(map(int, size)), warnings=warnings,
                          dataset_id=str(bundle['dataset_id'].item()) if 'dataset_id' in bundle else None,
                          capture_context=json.loads(str(bundle['capture_context_json'].item()))
                          if 'capture_context_json' in bundle else None,
                          mapping=mapping_report(bundle, tuple(size)))
            plot = path.with_suffix('.png')
            write_mapping_plot(plot, report['mapping'], tuple(size))
            report['mapping_plot_path'] = str(plot)
            if references:
                report['reference_sha256'] = file_sha256(args.references)
                report.update(reference_errors(bundle, references, cfg['quality'], registration))
        except (OSError, ValueError, KeyError, TypeError, cv2.error, np.linalg.LinAlgError) as error:
            report['error'] = str(error)
            failed = True
        atomic_json(path, report)
        print(path)
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
