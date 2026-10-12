"""One shared measurement pass, legacy projection, and separate live/CSV view."""
from __future__ import annotations
import numpy as np
from stereo_pose.joints import JOINT_INDEX
from stereo_pose.models import FilteredJoint3D, FrameDiagnostics, FrameTiming, JointQuality, PoseFrame
from stereo_pose.quality import aggregate_bucket, classify_joint


def measure_frame(*, selected_joints, readout_joints, triangulator, points_left, points_right,
                  conf_left, conf_right, kp_conf, qcfg, speed_gate, smoother, t_s,
                  frame_index, wall_timestamp_ns, pair_timing, calib_path):
    """Process union once, then project legacy counts/means onto original selection."""
    accepted={}; verdicts={}; geometry={}
    missing=points_left is None or points_right is None
    names=list(dict.fromkeys(list(selected_joints)+[x for x in readout_joints if x != 'eye_midpoint']))
    for name in names:
        i=JOINT_INDEX[name]; geom=None
        cl=0. if missing else float(conf_left[i]); cr=0. if missing else float(conf_right[i])
        if triangulator is not None and not missing and cl >= kp_conf and cr >= kp_conf:
            geom=triangulator.triangulate_with_quality(points_left[i],points_right[i])
        v=classify_joint(name,conf_l=cl,conf_r=cr,keypoint_confidence=kp_conf,geometry=geom,
                         qcfg=qcfg,missing_pose=missing,calibration_available=triangulator is not None)
        if v.accepted:
            raw=np.asarray(geom['xyz_mm'],dtype=float)
            ok,speed=speed_gate.check(name,raw,t_s)
            if not ok:
                v=classify_joint(name,conf_l=cl,conf_r=cr,keypoint_confidence=kp_conf,geometry=geom,
                                 qcfg=qcfg,speed_result=(False,speed))
            else:
                v.metrics['speed_mm_s']=float(speed)
                filtered=smoother.update(name,raw,t_s)
                accepted[name]=FilteredJoint3D(name,filtered.tolist(),raw.tolist(),
                    JointQuality(float(v.metrics['score']),float(geom['epipolar_error_px']),
                                 float(geom['reprojection_error_mean_px']),float(geom['reprojection_error_max_px']),float(speed)),
                    cl,cr,tuple(points_left[i]),tuple(points_right[i]),
                    tuple(geom['rectified_uv_left']),tuple(geom['rectified_uv_right']))
        verdicts[name]=v; geometry[name]=geom
    legacy_verdicts=[verdicts[x] for x in selected_joints]
    joints={x:accepted[x] for x in selected_joints if x in accepted}
    rejected=dict.fromkeys(('keypoint_confidence','geometry','depth','quality_score','speed'),0)
    fine={}
    for v in legacy_verdicts:
        bucket=aggregate_bucket(v.state)
        if bucket: rejected[bucket]+=1
        if not v.accepted: fine[v.state]=fine.get(v.state,0)+1
    geoms=[geometry[x] for x in selected_joints if geometry[x] is not None]
    epi=float(np.mean([g['epipolar_error_px'] for g in geoms])) if geoms else None
    rep=float(np.mean([g['reprojection_error_max_px'] for g in geoms])) if geoms else None
    diagnostics=FrameDiagnostics(len(selected_joints),len(joints),len(selected_joints)-len(joints),legacy_verdicts,fine)
    frame=PoseFrame(frame_index,wall_timestamp_ns,'rectified_left_camera','mm',str(calib_path) if calib_path else None,
        FrameTiming.from_dict(pair_timing),{'enabled':bool(smoother.enabled),'type':'one_euro',
        'min_cutoff':smoother.min_cutoff,'beta':smoother.beta,'d_cutoff':smoother.d_cutoff},
        {'accepted_joints':len(joints),'rejected':rejected,'mean_epipolar_error_px':epi,'mean_reprojection_error_px':rep},
        joints,diagnostics)
    return frame,accepted,verdicts,geometry


def make_readout(names, accepted, verdicts, geometry, registration):
    """Fresh rows only; raw/filtered/candidates never share accepted columns."""
    rows=[]
    for name in names:
        v=verdicts.get(name); j=accepted.get(name); g=geometry.get(name)
        row={'joint':name,'status':'missing','reason':'not_observed','derived':name=='eye_midpoint',
             'camera_raw_mm':None,'camera_filtered_mm':None,'world_raw_mm':None,'world_filtered_mm':None,
             'candidate_camera_mm':None,'candidate_world_mm':None,'confidence_left':None,'confidence_right':None,
             'quality_score':None,'epipolar_error_px':None,'reprojection_error_px':None,'speed_mm_s':None}
        if name=='eye_midpoint':
            l,r=accepted.get('left_eye'),accepted.get('right_eye')
            if l is not None and r is not None:
                row.update(status='accepted',reason='',camera_raw_mm=((np.asarray(l.xyz_raw_mm)+r.xyz_raw_mm)/2).tolist(),
                    camera_filtered_mm=((np.asarray(l.xyz_mm)+r.xyz_mm)/2).tolist(),
                    confidence_left=min(l.confidence_left,r.confidence_left),confidence_right=min(l.confidence_right,r.confidence_right),
                    quality_score=min(l.quality.score,r.quality.score),epipolar_error_px=max(l.quality.epipolar_error_px,r.quality.epipolar_error_px),
                    reprojection_error_px=max(l.quality.reprojection_error_max_px,r.quality.reprojection_error_max_px))
            else: row['reason']='both_eyes_required'
        elif j is not None:
            row.update(status='accepted',reason='',camera_raw_mm=list(j.xyz_raw_mm),camera_filtered_mm=list(j.xyz_mm),
                confidence_left=j.confidence_left,confidence_right=j.confidence_right,
                quality_score=j.quality.score,epipolar_error_px=j.quality.epipolar_error_px,
                reprojection_error_px=j.quality.reprojection_error_max_px,speed_mm_s=j.quality.speed_mm_s)
        elif v is not None:
            row.update(reason=v.state,confidence_left=v.metrics.get('conf_l'),confidence_right=v.metrics.get('conf_r'),
                       quality_score=v.metrics.get('score'),epipolar_error_px=v.metrics.get('epipolar_error_px'),
                       reprojection_error_px=v.metrics.get('reprojection_error_max_px'),speed_mm_s=v.metrics.get('speed_mm_s'))
            row['status']='missing' if v.state in ('missing_pose','calibration_unavailable') else 'rejected'
            if g is not None and np.all(np.isfinite(g['xyz_mm'])):
                row.update(status='candidate',candidate_camera_mm=np.asarray(g['xyz_mm']).tolist())
        if registration is not None:
            for c,w in [('camera_raw_mm','world_raw_mm'),('camera_filtered_mm','world_filtered_mm'),('candidate_camera_mm','candidate_world_mm')]:
                if row[c] is not None: row[w]=registration['transform'].apply(row[c]).tolist()
        rows.append(row)
    return rows


def append_readout(canvas, rows, registration, recorder_status='REC OFF', world_warnings=()):
    import cv2
    h=70+23*((len(rows)+1)//2)+22*len(world_warnings)
    panel=np.zeros((h,canvas.shape[1],3),np.uint8)
    frame='CAMERA FRAME' if registration is None else registration['name']
    cv2.putText(panel,f'XYZ mm | {frame} | W=align / zero | T=CSV | eye_midpoint is not gaze',(14,22),cv2.FONT_HERSHEY_SIMPLEX,.46,(255,255,255),1,cv2.LINE_AA)
    for i,row in enumerate(rows):
        field='world_filtered_mm' if registration else 'camera_filtered_mm'
        p=row[field]; label=row['status'];color=(80,255,80) if p is not None else (0,190,255)
        if p is None and row['status']=='candidate':
            p=row['candidate_world_mm' if registration else 'candidate_camera_mm'];label='CANDIDATE '+row['reason']
        xyz='---' if p is None else ', '.join(f'{x:.1f}' for x in p)
        text=f'{row["joint"]}: {xyz} [{label if p is not None else row["reason"]}]'
        cv2.putText(panel,text,(14+(i%2)*(canvas.shape[1]//2),48+(i//2)*23),cv2.FONT_HERSHEY_SIMPLEX,.41,color,1,cv2.LINE_AA)
    cv2.putText(panel,recorder_status,(14,h-8-22*len(world_warnings)),cv2.FONT_HERSHEY_SIMPLEX,.43,(100,180,255),1,cv2.LINE_AA)
    for i,w in enumerate(world_warnings):
        cv2.putText(panel,str(w),(14,h-8-22*(len(world_warnings)-1-i)),cv2.FONT_HERSHEY_SIMPLEX,.40,(0,120,255),1,cv2.LINE_AA)
    return cv2.vconcat([canvas,panel])
