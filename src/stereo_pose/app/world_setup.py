"""W frozen-pair preview, editable reference CSV, fit/axes/confirm/cancel."""
from __future__ import annotations
import csv
import os
import subprocess
from pathlib import Path
import cv2
import numpy as np

from stereo_pose.calibration.experiment import preview_pair
from stereo_pose.geometry.projection import project_points
from stereo_pose.calibration.package import activate_calibration, save_registered, read_bundle
from stereo_pose.coordinates.rigid import fit_rigid, relative_origin
from stereo_pose.coordinates.markers import detect_markers, read_references, match_features
from stereo_pose.persistence import ensure_managed_location
from stereo_pose.app.desktop import configure_highgui


def world_axis_pixels(transform, projection, length=100., anchor_world=(0.,0.,0.)):
    C=transform.inverse().apply(np.array([[0,0,0],[length,0,0],[0,length,0],[0,0,length]])+np.asarray(anchor_world))
    if np.any(C[:,2] <= 0): return None
    uv=np.c_[C,np.ones(4)] @ np.asarray(projection).T
    return uv[:,:2]/uv[:,2:3]


def world_axis_pixels_raw(transform, triangulator, length=100., anchor_world=(0.,0.,0.)):
    """Project world axes onto the ORIGINAL left camera frame.

    The candidate world fit lives in rectified-left coordinates. Undo R1 first
    to return to the physical left camera, then apply its actual K1 and D1.
    This keeps the UI's raw image and proposed axis overlay in one pixel space.
    """
    points = np.array([[0.,0.,0.],[length,0.,0.],
                       [0.,length,0.],[0.,0.,length]],dtype=float)
    rectified_xyz = transform.inverse().apply(points + np.asarray(anchor_world,dtype=float))
    original_xyz = (np.asarray(triangulator.R1,dtype=float).T @ rectified_xyz.T).T
    if not np.all(np.isfinite(original_xyz)) or np.any(original_xyz[:,2] <= 0):
        return None
    uv = project_points(getattr(triangulator, 'camera_model', 'pinhole'),
                        original_xyz, triangulator.K1, triangulator.D1)
    return uv if np.all(np.isfinite(uv)) else None


def raw_frozen_markers(frame_left, frame_right, detected_left, detected_right):
    """Annotate untouched frozen sensor images, not zoomed/rectified views.

    Actual 3D fitting still rectifies individual 2D marker corners internally
    in StereoTriangulator; preview rendering must not hide markers under a
    zooming camera rectification map.
    """
    frames=[]
    for image, detected in ((frame_left, detected_left),(frame_right, detected_right)):
        canvas=image.copy()
        height,width=canvas.shape[:2]
        for marker_id,corners in detected.items():
            raw=np.asarray(corners,dtype=float).reshape(-1,2)
            if len(raw)<4 or not np.all(np.isfinite(raw)):
                continue
            outline=np.rint(raw).astype(np.int32).reshape(-1,1,2)
            cv2.polylines(canvas,[outline],True,(0,255,255),2)
            anchor=np.rint(raw[0]).astype(int)
            at=(int(np.clip(anchor[0],0,width-1)),int(np.clip(anchor[1],0,height-1)))
            cv2.putText(canvas,str(marker_id),at,cv2.FONT_HERSHEY_SIMPLEX,
                        .7,(0,255,255),2)
        frames.append(canvas)
    return frames


def prepare_reference_file(path, ids, dictionary):
    """Never overwrite the user's entered coordinates, even on cancellation."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():
        with p.open('x',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['dictionary','id','feature_type','X_mm','Y_mm','Z_mm'])
            for i in sorted(ids): w.writerow([dictionary,i,'center','','',''])
    return p


def run_world_setup(*, frame_left, frame_right, triangulator, calib_path, config_path,
                    cfg, registration=None, detector=detect_markers, desktop=None):
    """No camera read, no YOLO call, no imagery written. Return activated NPZ or None."""
    world=cfg['world'];dictionary=world['dictionary'];runtime=cfg['runtime']['root']
    size=(frame_left.shape[1],frame_left.shape[0])
    bundle=read_bundle(calib_path)
    if frame_right.shape[:2] != frame_left.shape[:2] or ('image_size' in bundle and tuple(bundle['image_size'].reshape(-1)) != size):
        raise ValueError('camera resolution differs from stereo calibration; recalibrate C -> R before W')
    reference=ensure_managed_location(world['reference_file'],runtime,'reference CSV')
    left=detector(frame_left,dictionary);right=detector(frame_right,dictionary)
    prepare_reference_file(reference,set(left)&set(right),dictionary)
    print(f'[world] frozen current frame pair. IDs L={sorted(left)} R={sorted(right)}')
    print(f'[world] edit real XYZ mm: {reference.resolve()} (R=reload/fit, U=confirm physical +Z up, ENTER=save+activate, Z=zero-only, ESC=cancel)')
    if os.name=='nt' and desktop is None:
        try: subprocess.Popen(['notepad.exe',str(reference.resolve())])
        except OSError as e: print(f'[world] open CSV manually: {e}')
    # Start with the complete raw FOV and raw corner labels. The optional
    # display remap happens after annotations; detector/fitter inputs stay raw.
    frames=raw_frozen_markers(frame_left,frame_right,left,right)
    fit=None;candidate=None;up=False;zero=False;error='Enter real XYZ in CSV, save it, then R=fit'; report={}; naming=False
    name=world['coordinate_name']
    dialog=None
    try:
        if desktop is not None:
            from stereo_pose.app.world_form import WorldForm
            dialog=WorldForm.__new__(WorldForm)
            WorldForm.__init__(dialog,desktop,reference,left,right,dictionary,name)
        return _setup_loop(frames,left,right,reference,triangulator,calib_path,config_path,cfg,registration,dictionary,runtime,size,
                           fit,candidate,up,zero,error,report,naming,name,dialog)
    finally:
        if dialog is not None:dialog.close()
        else:
            try:cv2.destroyWindow('World alignment')
            except cv2.error:pass


def _setup_loop(frames,left,right,reference,triangulator,calib_path,config_path,cfg,registration,dictionary,runtime,size,
                fit,candidate,up,zero,error,report,naming,name,dialog=None):
    world=cfg['world']
    window_ready=False
    rectified_preview = False
    preview_maps = None
    while True:
        a,b=[x.copy() for x in frames]
        if candidate is not None:
            pixels=world_axis_pixels_raw(candidate['transform'],triangulator,
                                        anchor_world=candidate['metadata']['reference_points'][0]['xyz_mm'])
            if pixels is not None:
                origin=tuple(np.round(pixels[0]).astype(int))
                for i,(color,label) in enumerate([((0,0,255),'+X'),((0,255,0),'+Y'),((255,0,0),'+Z')],1):
                    tip=tuple(np.round(pixels[i]).astype(int));cv2.arrowedLine(a,origin,tip,color,2);cv2.putText(a,label,tip,cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
        if rectified_preview:
            try:
                (a, b), preview_maps = preview_pair((a, b), triangulator, preview_maps)
            except (ValueError, cv2.error) as preview_error:
                error = f'Rectified preview unavailable: {preview_error}'
                rectified_preview = False
        if dialog is not None and hasattr(dialog, 'preview_button'):
            dialog.preview_button.configure(text='切回原始完整画面  H' if rectified_preview else '看矫正预览  H')
        images=[cv2.resize(x,(int(x.shape[1]*300/x.shape[0]),300)) for x in (a,b)]
        canvas=cv2.hconcat(images);panel=np.zeros((180,canvas.shape[1],3),np.uint8)
        lines=[f'FROZEN PAIR | {dictionary} | mode={"ZERO (axes unchanged)" if zero else "WORLD"} | name={name}',
               f'{"RECTIFIED PREVIEW" if rectified_preview else "RAW FULL PREVIEW"} | CSV: {reference}', 'H=preview  R=reload/fit  Z=toggle zero  U=physical +Z up  N=edit frame name  ENTER=save  ESC=cancel',
               f'Up confirmed={up} | registration RMS={report.get("rms_mm","---")} max={report.get("max_mm","---")} mm',
               error, report.get('warning',''), 'Residual is registration consistency, not absolute eye accuracy.']
        for i,line in enumerate(lines): cv2.putText(panel,str(line),(12,23+i*22),cv2.FONT_HERSHEY_SIMPLEX,.44,(255,255,255),1,cv2.LINE_AA)
        if dialog is not None:
            key=dialog.show((a,b),zero=zero,up=up,candidate=candidate,report=report,error=error)
            name=dialog.name.get().strip()
            if getattr(dialog,'dirty',False):candidate=None;up=False
        else:
            if not window_ready:
                configure_highgui('World alignment',(480,canvas.shape[1],3));window_ready=True
            cv2.imshow('World alignment',cv2.vconcat([canvas,panel]));key=cv2.waitKey(30)&0xff
        if key==27 or (key in (ord('q'),ord('Q')) and not naming):
            return None
        # A window close is equivalent to cancellation (not a hung modal loop).
        if dialog is None and cv2.getWindowProperty('World alignment',cv2.WND_PROP_VISIBLE) < 1:return None
        if naming:
            if key==13: naming=False
            elif key in (8,127):name=name[:-1]
            elif 32 <= key <= 126:name+=chr(key)
            continue
        if key in (ord('h'), ord('H')) and getattr(triangulator, 'image_size', None) is not None:
            rectified_preview = not rectified_preview
            continue
        if key in (ord('n'),ord('N')): naming=True;name='';error='Type ASCII frame name; ENTER finishes name';continue
        if key in (ord('u'),ord('U')): up=not up
        if key in (ord('z'),ord('Z')):zero=not zero;candidate=None;error='Mode changed; press R to fit'
        if key in (ord('r'),ord('R')):
            try:
                refs=read_references(reference,first_only=zero)
                up=False  # Physical-axis confirmation belongs to this fit only.
                C,W=match_features(refs,left,right,triangulator,dictionary,cfg['quality']['max_epipolar_error_px'],cfg['quality']['max_reprojection_error_px'])
                if zero:
                    transform=relative_origin(None if registration is None else registration['transform'],C[0],W[0])
                    report={'method':'translation_only','reference_index':0,'warning':'axes preserved; no new gravity direction'}
                else:
                    fit=fit_rigid(C,W,world['max_residual_mm']);transform=fit.transform;report=fit.report()
                candidate={'transform':transform,'name':name,'metadata':{**report,'mode':'zero' if zero else 'world',
                    'reference_points':refs,'camera_controls_mm':C.tolist(),'capture_image_size':list(size),
                    'parent_coordinate_name':None if registration is None else registration['name'],
                    'axes':'preserved axes; no new gravity claim' if zero else 'owner-defined X/Y; +Z physically confirmed'}}
                if zero and registration is not None:
                    # Origin-only alignment must retain the default frame's
                    # installation assumption; it cannot establish world-up.
                    for field in ('up_reference', 'mount_assumption'):
                        if field in registration.get('metadata', {}):
                            candidate['metadata'][field] = registration['metadata'][field]
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
                print(f'[world] SAVED + ACTIVATED {saved}');return saved
            except Exception as e: error=f'Save/activate failed; previous active retained: {e}';print('[world]',error)
