# Task003A/003B — operator, default frame, world NPZ and manual CSV v1

## Default frame (Task003B)

Before W registration, a valid stereo-only package enables `camera_midpoint`
live readout and CSV W columns: optical-center midpoint zero, +X forward,
+Y right camera -> left camera, +Z up assuming level optical centers and upright,
level camera mounting. No fiducials/new config/dependencies/NPZ write needed.
UI labels DEFAULT: CAMERA MIDPOINT and assumed up. Ground is usually at negative
Z because the origin is at lens height. Relative stereo parameters do not
observe gravity or common rig pitch/roll; physically align W for actual world-up.

Centers solve `P_i[:,:3] @ c_i = -P_i[:,3]`, in the triangulated rectified frame;
raw T/2 is not this midpoint. Proper no-scale basis: y=normalize(c_left-c_right),
z=normalized camera-up projected perpendicular to y, x=y cross z, t=-R@midpoint.
Camera-up is the average R1/R2-transformed raw up (0,-1,0). x must face forward;
invalid/ambiguous rig or size mismatch visibly disables the default frame.
Valid saved W/relative registration wins; invalid W is warned and does not
masquerade as accepted W. If valid stereo permits, the named DEFAULT is used.
Restart derives the same default; C/R stereo solve recomputes it; cancelled W
preserves it. Origin-only zero retains its axis provenance/mount assumption.

CSV schema remains v1, column names unchanged. In default mode `coordinate_frame`
is `camera_midpoint`, world_* and candidate_world_* hold default-frame coordinates
with existing validity separation. `session.json.world` freezes R/t and
`definition.mode=camera_midpoint`, method, origin and optical centers in C,
baseline_mm, axis vectors/definitions, stereo_fingerprint, `up_confirmed=false`,
`up_reference=camera_mount_assumption` and mounting caveat. No world NPZ schema
change: only explicit W/zero is persisted; zero from default stores the inherited
up_reference/mount_assumption. Legacy v1.2 wire fields still mean C coordinates.

Math reference: [OpenCV stereoRectify P1/P2/R1/R2 coordinate definitions](https://docs.opencv.org/4.5.2/d9/d0c/group__calib3d.html).

## Windows operator steps

Keep local config.json/runtime/yolo11n-pose.pt when updating code. Run RUN_ME.bat in the existing working environment, pick physical LEFT/RIGHT cameras and use the current stereo calibration if the rig is unchanged.
W freezes the CURRENT pair in memory: no new capture, second YOLO, saved image or continuous marker tracking.
Edit runtime/world/reference_points.csv (Notepad opens on Windows): dictionary,id,feature_type,X_mm,Y_mm,Z_mm. Enter independently known real mm coordinates. Full alignment requires >=3 non-collinear controls; coplanar controls valid, 4–6 spread points recommended.
R reloads/fits; inspect per-point residuals in console and RMS/max/colored axes. Arrows are anchored at the first reference point to show direction when the origin is outside view.
U confirms physically upward +Z for this fit; recomputing R clears confirmation. N edits an ASCII display name, Enter ends name editing. Enter saves a NEW combined NPZ and explicitly activates it; ESC/Q/window close cancels.
Z selects origin-only mode: ONLY first CSV row is required; other template rows may remain blank. The reference maps to its entered target XYZ (normally zero), preserving current world/default/camera axes. RELATIVE does not infer gravity.
Restart restores the exact selected file/frame without markers. C/R stereo re-solve publishes unique immutable stereo-only NPZ, persists selection and clears W; default midpoint is recomputed, re-register if W is desired. P retains preserve-copy semantics.
T starts/stops CSV manually, default OFF. C/W/F/exit ends the recording with an explicit reason; restart T creates another unique session.

## Coordinates and feature identity

C=rectified_left_camera (mm), W=named world/relative frame (mm):
W=R_wc @ C+t_wc_mm; C=R_wc.T @ (W-t_wc_mm); R.T@R=I, det(R)=+1. No scale/shear/reflection.
ArUco DICT_4X4_50 and configurable DICT_5X5_50 are supported. Missing cv2.aruco is diagnosed; no automatic dependency/model downloads.
WORLD TRIAD P0/P1/P2 are NOT automatically ID0/1/2. Each (dictionary,id,feature_type) is explicit/unique; center and corner0..3 differ.
Corners follow decoded ArUco order. Centers are means of four triangulated physical corners, not raw perspective-pixel averages. Missing/duplicate/mismatched controls and implausible stereo geometry fail.
Kabsch fit accepts planar rank-2 controls, rejects collinear/near-collinear/nonfinite controls and excessive residuals (world.max_residual_mm=10 by default). Outliers are reported/rejected, never silently dropped or corrected by scale.
Three controls lack independent redundancy. Consistent wrong user-entered correspondences cannot be detected solely by RMS. Registration residual is not absolute eye accuracy.
readout.joint_group/readout.joints select other joints; both eyes and eye_midpoint are always included. Midpoint requires two same-frame accepted eyes and is not eye rotation center/gaze.
Accepted raw/filtered C and W, rejected finite candidate C/W, and missing are separate. Missing/rejected accepted coordinates are blank, not zeros/old frames. Legacy v1.2 camera coordinates, selected joints, fields and statistics remain unchanged via projection from one shared measurement pass.

## Single versioned NPZ

Original arrays/shapes/dtypes/metadata are copied intact, including OpenCV D row/column vectors. A legacy package lacking image_size receives observed capture size in its NEW combined copy.

| Added key | Type |
|---|---|
| world_R | float64 (3,3), C->W proper rotation |
| world_t_mm | float64 (3,) |
| world_coordinate_name | non-object string scalar |
| world_schema_version | non-object string scalar "1" |
| world_metadata_json | non-object NumPy string scalar containing JSON |

Metadata records mode/method, C source/unit/direction, entered references/W XYZ, observed C controls, fit residual/spread/count/redundancy, axes/physical-up confirmation, parent frame, capture size, UTC creation and stereo_fingerprint.
stereo_fingerprint: SHA-256 over present ordered keys K1,D1,K2,D2,R,T,E,F,R1,R2,P1,P2,Q,image_size,square_mm. Each contributes compact JSON [key,dtype.str,shape], then C-contiguous bytes. Numeric camera indexes are not geometry identity.
Complete archive SHA-256 is separate, persisted as stereo.active_sha256 beside stereo.load=explicit and exact stereo.explicit_file. Missing/changed selection never silently falls back to newest auto.
All np.load calls forbid pickle/object arrays. Unknown/incomplete/bad W or fingerprint mismatch refuses W with an explicit warning; valid stereo may still enable the clearly labeled default frame. Size mismatch disables both W and default. Invalid selected stereo arrays disable 3D visibly.
Unique exclusive staging + flush/fsync + atomic non-overwriting publication (Windows rename / POSIX link+unlink) protects NPZ history. Preference JSON uses staging + os.replace.
Save and activation are separate transactions: failed activation may leave a complete unselected saved NPZ, but never reports success or changes the previous live selection.
Stereo re-solve also uses UUID names/atomic archive publication, with original algorithm/numeric matrices unchanged. Saved files/recordings and active auto NPZ are cleanup-protected.
Physical movement cannot be established from indexes/hashes: verify unchanged mounts/order or recalibrate/re-register.

## CSV/session contract

Paths: runtime/recordings/session_<UTC>_<UUID>/joints.csv + session.json. Output must remain inside runtime_root/recordings and cannot point into cleanup-managed capture sessions. No historical overwrite/deletion.
CSV is UTF-8 BOM, one row per fresh sample x requested joint (including missing midpoint rows). It streams/flushes per sample with bounded memory.

| Fields | Meaning |
|---|---|
| sample_index,frame_index | session index + original processed frame ID |
| timestamp_ns | original frame wall timestamp |
| frame_monotonic_ns | host pair midpoint, NOT sensor exposure |
| sample_monotonic_ns,elapsed_s | export clock + T-start elapsed time |
| joint,status,valid,reason,derived | accepted/candidate/rejected/missing, terminal reason, derived flag |
| coordinate_frame,unit,calibration_sha256,filtering_enabled | frozen frame/unit/artifact, current filtering state |
| camera_raw_mm_x/y/z,camera_filtered_mm_x/y/z | accepted C only |
| world_raw_mm_x/y/z,world_filtered_mm_x/y/z | accepted W/default only; blank if no valid readout transform |
| candidate_camera_mm_x/y/z,candidate_world_mm_x/y/z | distinct finite rejected candidates |
| confidence_left/right,quality_score,epipolar_error_px,reprojection_error_px,speed_mm_s | available evidence; missing/nonfinite blank |

recording.enabled enables T; auto_start MUST be false. Default sample_rate_hz=5 is export cadence, not camera/inference FPS.
Absolute monotonic deadlines skip missed periods; no modulo-frame sampling, catch-up duplicates or repeated frame IDs. Host-timestamped frames preceding T start are refused; slower inference exports fewer new frames with actual timestamps.
session.json schema stereo_pose_3d/csv/v1 freezes NPZ path/hash, C source/W definition/R/t, model/actual device/pose, camera indexes/requested and actual sizes, quality and FULL filtering including reset_after_s, selected joints and clock caveat.
Lifecycle records requested rate, UTC start/stop, monotonic start, completed count/duration, stop reason/error, achieved rate=(samples-1)/(last-first) for >=2 samples.
Initial in_progress marks partial/crash recovery; normal stop=stopped, recoverable failure=error. Disk full can prevent final manifest update; initial manifest and written CSV stay, with a visible error. Incomplete trailing rows/samples are not completed measurements.
Stop reasons include manual,app_exit,enter_calibration,world_setup,filter_changed,calibration_changed,capture_resolution_changed,write_failed. Cancelling W can still end recording intentionally; coordinate definitions never silently splice.

## Synthetic examples and acceptance

docs/examples/reference_points_SYNTHETIC.csv uses invented IDs/positions, not the owner's sheet mapping.
joints_SYNTHETIC.csv/session_SYNTHETIC.json illustrate valid/candidate/missing rows only; the zero SHA is an explicitly labeled placeholder, no calibration binary/person data is supplied.
261 methods + 26 subtests pass with real NumPy/OpenCV/ArUco/file IO and fake clocks/cameras/model/windows. Windows physical rig/YOLO/GPU/up/restart/CSV still require owner acceptance. Accuracy closure remains deferred; P1/P2/video/bookmarks/plots/replay/history/extra eye models excluded.
