"""Manual-only streaming CSV. Monotonic deadlines, fresh frames, no video IO."""
from __future__ import annotations
import csv
import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from stereo_pose.calibration.package import atomic_json, utc_now
from stereo_pose.persistence import ensure_managed_location

VECTOR_FIELDS = ('camera_raw_mm','camera_filtered_mm','world_raw_mm','world_filtered_mm',
                 'candidate_camera_mm','candidate_world_mm')
SCALAR_FIELDS = ('confidence_left','confidence_right','quality_score','epipolar_error_px',
                 'reprojection_error_px','speed_mm_s')
CSV_FIELDS = ['sample_index','frame_index','timestamp_ns','frame_monotonic_ns','sample_monotonic_ns','elapsed_s',
              'joint','status','valid','reason','derived','coordinate_frame','unit','calibration_sha256','filtering_enabled'] + [
              f'{name}_{axis}' for name in VECTOR_FIELDS for axis in ('x','y','z')] + list(SCALAR_FIELDS)


def finite_cell(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else ''
    except (TypeError,ValueError): return ''


class CsvRecorder:
    def __init__(self, output_dir, runtime_root, sample_rate_hz=5., include_candidates=True, clock=time.perf_counter_ns):
        if not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0: raise ValueError('positive finite sample_rate_hz required')
        self.output_dir=Path(output_dir);self.runtime_root=Path(runtime_root)
        self.rate=float(sample_rate_hz);self.period=max(1,int(round(1e9/self.rate)))
        self.include_candidates=bool(include_candidates);self.clock=clock
        self.active=False;self.path=None;self.error='';self._file=None;self.samples=0

    def start(self, metadata):
        """Caller is the tracking T handler. Construction/startup never records."""
        if self.active: raise RuntimeError('recording already active')
        # Recording subtrees cannot be redirected into G-managed capture sessions.
        output=ensure_managed_location(self.output_dir,self.runtime_root/'recordings','CSV recordings')
        output.mkdir(parents=True,exist_ok=True)
        self.path=output/('session_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex)
        self.path.mkdir(exist_ok=False)
        self._meta=json.loads(json.dumps(metadata,allow_nan=False))
        self.start_ns=int(self.clock());self.next_ns=self.start_ns
        self.last_frame=-1;self.samples=0;self.first_sample_ns=None;self.last_sample_ns=None;self.error=''
        self._meta.update(schema='stereo_pose_3d/csv/v1',status='in_progress',video_recording=False,unit='mm',
                          started_at=utc_now(),start_monotonic_ns=self.start_ns,sample_rate_hz_requested=self.rate,
                          samples_completed=0,csv_columns=CSV_FIELDS)
        try:
            atomic_json(self.path/'session.json',self._meta)
            self._file=(self.path/'joints.csv').open('x',newline='',encoding='utf-8-sig')
            self._writer=csv.DictWriter(self._file,fieldnames=CSV_FIELDS)
            self._writer.writeheader();self._file.flush();self.active=True
            return self.path
        except Exception as e:
            self.error=str(e)
            if self._file is not None:self._file.close();self._file=None
            self._meta.update(status='error',error=self.error,stop_reason='start_failed')
            try:atomic_json(self.path/'session.json',self._meta)
            except OSError:pass
            raise

    def sample(self, frame, rows, now_ns=None):
        if not self.active:return False
        now=int(self.clock() if now_ns is None else now_ns)
        if frame.calibration_file != self._meta.get('calibration_file'):
            self.stop('calibration_changed');return False
        capture=frame.timing.host_midpoint_perf_ns
        if frame.frame_index <= self.last_frame or now < self.next_ns or (capture is not None and capture < self.start_ns):return False
        try:
            for joint in rows:
                valid=joint['status']=='accepted'
                r={'sample_index':self.samples,'frame_index':frame.frame_index,'timestamp_ns':frame.wall_timestamp_ns,
                   'frame_monotonic_ns':capture,'sample_monotonic_ns':now,'elapsed_s':(now-self.start_ns)/1e9,
                   'joint':joint['joint'],'status':joint['status'],'valid':valid,'reason':joint['reason'],
                   'derived':joint['derived'],'coordinate_frame':self._meta['coordinate_frame'],'unit':'mm',
                   'calibration_sha256':self._meta.get('calibration_sha256',''),
                   'filtering_enabled':bool(frame.filtering['enabled'])}
                for name in VECTOR_FIELDS:
                    # Accepted and candidate values have separate validity contracts.
                    is_candidate=name.startswith('candidate_')
                    permitted=(not valid and self.include_candidates) if is_candidate else valid
                    vec=joint.get(name) if permitted else None
                    for i,axis in enumerate(('x','y','z')):r[f'{name}_{axis}']=finite_cell(vec[i]) if vec is not None else ''
                for k in SCALAR_FIELDS:r[k]=finite_cell(joint.get(k))
                self._writer.writerow(r)
            self._file.flush()
            self.last_frame=frame.frame_index;self.samples+=1
            if self.first_sample_ns is None:self.first_sample_ns=now
            self.last_sample_ns=now
            # Advance the absolute cadence past NOW, never generate catch-up copies.
            self.next_ns=self.start_ns+((now-self.start_ns)//self.period+1)*self.period
            return True
        except Exception as e:
            self.error=str(e);self.stop('write_failed',error=self.error);return False

    def stop(self, reason='manual', error=None):
        if not self.active:return self.path
        self.active=False;end=int(self.clock())
        try:
            self._file.flush()
        except OSError as e:self.error=str(e)
        finally:
            try:self._file.close()
            except OSError as e:self.error=str(e)
            self._file=None
        duration=max(0.,(end-self.start_ns)/1e9)
        span=0. if self.samples < 2 else (self.last_sample_ns-self.first_sample_ns)/1e9
        self._meta.update(status='error' if error or self.error else 'stopped',stop_reason=reason,
                          stopped_at=utc_now(),duration_s=duration,samples_completed=self.samples,
                          sample_rate_hz_achieved=(self.samples-1)/span if span > 0 else 0.,
                          error=error or self.error or None)
        try:atomic_json(self.path/'session.json',self._meta)
        except OSError as e:
            # Initial in_progress manifest + existing CSV still identify partial data.
            self.error=f'{self.error}; manifest could not be finalized: {e}'
        return self.path

    def status(self):
        if self.active:
            return f'REC ON | {max(0.,(self.clock()-self.start_ns)/1e9):.1f}s | samples={self.samples} | {self.path}/joints.csv'
        return 'REC OFF'+(f' | ERROR: {self.error}' if self.error else '')
