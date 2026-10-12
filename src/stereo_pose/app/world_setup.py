"""W frozen-pair preview, editable reference CSV, fit/axes/confirm/cancel."""
from __future__ import annotations
import csv
import os
import subprocess
from pathlib import Path
import cv2
import numpy as np
from stereo_pose.calibration.package import activate_calibration, save_registered
from stereo_pose.coordinates.rigid import fit_rigid, relative_origin
from stereo_pose.coordinates.markers import detect_markers, read_references, match_features
from stereo_pose.persistence import ensure_managed_location


def world_axis_pixels(transform, projection, length=100.):
    C=transform.inverse().apply(np.array([[0,0,0],[length,0,0],[0,length,0],[0,0,length]]))
    if np.any(C[:,2] <= 0): return None
    uv=np.c_[C,np.ones(4)] @ np.asarray(projection).T
    return uv[:,:2]/uv[:,2:3]


def prepare_reference_file(path, ids, dictionary):
    """Never overwrite the user's entered coordinates, even on cancellation."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():
        with p.open('x',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['dictionary','id','feature_type','X_mm','Y_mm','Z_mm'])
            for i in sorted(ids): w.writerow([dictionary,i,'center','','',''])
    return p


def run_world_setup(*, frame_left, frame_right, triangulator, calib_path, config_path,
                    cfg, registration=None, detector=detect_markers):
    """No camera read, no YOLO call, no imagery written. Return activated NPZ or None."""
    world=cfg['world'];dictionary=world['dictionary'];runtime=cfg['runtime']['root']
    reference=ensure_managed_location(world['reference_file'],runtime,'reference CSV')
    left=detector(frame_left,dictionary);right=detector(frame_right,dictionary)
    prepare_reference_file(reference,set(left)&set(right),dictionary)
    print(f'[world] frozen current frame pair. IDs L={sorted(left)} R={sorted(right)}')
    print(f'[world] edit real XYZ mm: {reference.resolve()} (R=reload/fit, U=confirm physical +Z up, ENTER=save+activate, Z=zero-only, ESC=cancel)')
    if os.name=='nt':
        try: subprocess.Popen(['notepad.exe',str(reference.resolve())])
        except OSError as e: print(f'[world] open CSV manually: {e}')
    frames=[]
    for image,K,D,R,P,detected in [(frame_left,triangulator.K1,triangulator.D1,triangulator.R1,triangulator.P1,left),
                                  (frame_right,triangulator.K2,triangulator.D2,triangulator.R2,triangulator.P2,right)]:
        h,w=image.shape[:2]
        maps=cv2.initUndistortRectifyMap(K,D,R,P,(w,h),cv2.CV_32FC1)
        rectified=cv2.remap(image,*maps,cv2.INTER_LINEAR)
        for i,c in detected.items():
            uv=cv2.undistortPoints(c.reshape(-1,1,2),K,D,R=R,P=P).reshape(-1,2)
            cv2.polylines(rectified,[uv.astype(np.int32)],True,(0,255,255),2)
            cv2.putText(rectified,str(i),tuple(uv[0].astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        frames.append(rectified)
    fit=None;candidate=None;up=False;zero=False;error='Enter real XYZ in CSV, save it, then R=fit'; report={}; naming=False
    name=world['coordinate_name']
    while True:
        a,b=[x.copy() for x in frames]
        if candidate is not None:
            pixels=world_axis_pixels(candidate['transform'],triangulator.P1)
            if pixels is not None:
                origin=tuple(np.round(pixels[0]).astype(int))
                for i,(color,label) in enumerate([((0,0,255),'+X'),((0,255,0),'+Y'),((255,0,0),'+Z')],1):
                    tip=tuple(np.round(pixels[i]).astype(int));cv2.arrowedLine(a,origin,tip,color,2);cv2.putText(a,label,tip,cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
        images=[cv2.resize(x,(int(x.shape[1]*300/x.shape[0]),300)) for x in (a,b)]
        canvas=cv2.hconcat(images);panel=np.zeros((180,canvas.shape[1],3),np.uint8)
        lines=[f'FROZEN PAIR | {dictionary} | mode={"ZERO (axes unchanged)" if zero else "WORLD"} | name={name}',
               f'CSV: {reference}', 'R=reload/fit  Z=toggle zero  U=physical +Z up  N=edit frame name  ENTER=save  ESC=cancel',
               f'Up confirmed={up} | registration RMS={report.get("rms_mm","---")} max={report.get("max_mm","---")} mm',
               error, report.get('warning',''), 'Residual is registration consistency, not absolute eye accuracy.']
        for i,line in enumerate(lines): cv2.putText(panel,str(line),(12,23+i*22),cv2.FONT_HERSHEY_SIMPLEX,.44,(255,255,255),1,cv2.LINE_AA)
        cv2.imshow('World alignment',cv2.vconcat([canvas,panel]));key=cv2.waitKey(30)&0xff
        if key in (27,ord('q')) and not naming:
            cv2.destroyWindow('World alignment');return None
        if naming:
            if key==13: naming=False
            elif key in (8,127):name=name[:-1]
            elif 32 <= key <= 126:name+=chr(key)
            continue
        if key in (ord('n'),ord('N')): naming=True;name='';error='Type ASCII frame name; ENTER finishes name';continue
        if key in (ord('u'),ord('U')): up=not up
        if key in (ord('z'),ord('Z')):zero=not zero;candidate=None;error='Mode changed; press R to fit'
        if key in (ord('r'),ord('R')):
            try:
                refs=read_references(reference)
                C,W=match_features(refs,left,right,triangulator,dictionary,cfg['quality']['max_epipolar_error_px'],cfg['quality']['max_reprojection_error_px'])
                if zero:
                    transform=relative_origin(None if registration is None else registration['transform'],C[0],W[0])
                    report={'method':'translation_only','reference_index':0,'warning':'axes preserved; no new gravity direction'}
                else:
                    fit=fit_rigid(C,W,world['max_residual_mm']);transform=fit.transform;report=fit.report()
                candidate={'transform':transform,'name':name,'metadata':{**report,'mode':'zero' if zero else 'world',
                    'reference_points':refs,'camera_controls_mm':C.tolist(),'axes':'owner-defined X/Y; +Z physically confirmed for full world'}}
                error='Review axes/residuals. U confirms world-up; ENTER saves+activates.'
                print('[world] fit:',report)
            except Exception as e: candidate=None;error=str(e);print('[world] fit failed:',e)
        if key==13:
            if candidate is None:error='Press R and obtain a valid fit first';continue
            if not zero and not up:error='Confirm physically upward +Z with U before saving';continue
            try:
                candidate['name']=name;candidate['metadata']['up_confirmed']=up
                saved=save_registered(calib_path,candidate,cfg['stereo']['calibration_dir'],runtime)
                activate_calibration(config_path,saved)
                print(f'[world] SAVED + ACTIVATED {saved}');cv2.destroyWindow('World alignment');return saved
            except Exception as e: error=f'Save/activate failed; previous active retained: {e}';print('[world]',error)
