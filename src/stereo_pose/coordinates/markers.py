"""On-demand ArUco adapter + explicit physical-feature correspondence.

Center is the mean of the four triangulated physical corners, NOT the mean
of their raw perspective pixels. Detection remains extensible via keyed maps.
"""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np
import cv2

DICTIONARIES = ('DICT_4X4_50', 'DICT_5X5_50')
FEATURES = ('center','corner0','corner1','corner2','corner3')


def detect_markers(frame, dictionary):
    if dictionary not in DICTIONARIES: raise ValueError('unsupported ArUco dictionary')
    if not hasattr(cv2,'aruco'): raise RuntimeError('cv2.aruco missing: install an ArUco-capable OpenCV build locally; no automatic install')
    aruco=cv2.aruco
    d=aruco.getPredefinedDictionary(getattr(aruco,dictionary))
    parameters=aruco.DetectorParameters() if hasattr(aruco,'DetectorParameters') else aruco.DetectorParameters_create()
    parameters.cornerRefinementMethod=aruco.CORNER_REFINE_SUBPIX
    if hasattr(aruco,'ArucoDetector'): corners,ids,_=aruco.ArucoDetector(d,parameters).detectMarkers(frame)
    else: corners,ids,_=aruco.detectMarkers(frame,d,parameters=parameters)
    result={}
    if ids is not None:
        for c,i in zip(corners,ids.reshape(-1)):
            if int(i) in result: raise ValueError(f'duplicate marker ID {i}; use unique IDs in each view')
            result[int(i)]=np.asarray(c,dtype=float).reshape(4,2)
    return result


def read_references(path, first_only=False):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if first_only:rows=rows[:1]
    references=[];seen=set()
    for row in rows:
        try:
            d=row['dictionary']; i=int(row['id']); feature=row['feature_type']
            xyz=[float(row[k]) for k in ('X_mm','Y_mm','Z_mm')]
        except (KeyError,ValueError,TypeError) as e: raise ValueError('reference CSV: dictionary,id,feature_type,X_mm,Y_mm,Z_mm required') from e
        key=(d,i,feature)
        if d not in DICTIONARIES or not 0 <= i < 50 or feature not in FEATURES or not np.all(np.isfinite(xyz)):
            raise ValueError(f'invalid reference point {key}; finite real XYZ in mm required')
        if key in seen: raise ValueError(f'duplicate reference {key}')
        seen.add(key);references.append({'dictionary':d,'id':i,'feature_type':feature,'xyz_mm':xyz})
    if not references: raise ValueError('reference CSV is empty')
    return references


def match_features(references, left, right, triangulator, dictionary, max_epi, max_reproj):
    controls=[]; targets=[]
    for r in references:
        i=r['id']
        if r['dictionary'] != dictionary or i not in left or i not in right:
            raise ValueError(f'missing/mismatched reference ID {i} ({r["dictionary"]}) in both views')
        points=[]
        indexes=range(4) if r['feature_type']=='center' else [int(r['feature_type'][-1])]
        for k in indexes:
            q=triangulator.triangulate_with_quality(left[i][k],right[i][k])
            if q is None or not np.all(np.isfinite(q['xyz_mm'])) or q['xyz_mm'][2] <= 0 or q['epipolar_error_px'] > max_epi or q['reprojection_error_max_px'] > max_reproj:
                raise ValueError(f'ID {i} corner{k} fails stereo geometry; hold target still/check correspondence')
            points.append(q['xyz_mm'])
        controls.append(np.mean(points,axis=0));targets.append(r['xyz_mm'])
    return np.asarray(controls), np.asarray(targets)
