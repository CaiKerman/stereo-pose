"""Read-only operator view models; no measurement/capture/coordinate mutations."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    key: int
    label: str
    enabled: bool = True


class PendingAction:
    """One outstanding user command; stale commands never cross mode changes."""
    def __init__(self):
        self.mode = None
        self.actions = {}
        self.pending = None

    def configure(self, mode, actions):
        if mode != self.mode:
            self.pending = None
        self.mode = mode
        self.actions = {a.key: a.enabled for a in actions}

    def offer(self, key, *, keyboard=False):
        # Keyboard force/diagnostic semantics remain in the existing runner.
        if self.pending is None and (keyboard or self.actions.get(key, False)):
            self.pending = key

    def take(self):
        key, self.pending = self.pending, None
        return 255 if key is None else key


def fit_size(source, bounds):
    """Contain without distortion. Sizes are display-only, never capture sizes."""
    sw, sh = source
    bw, bh = bounds
    if min(sw, sh, bw, bh) <= 0:
        raise ValueError('positive image and viewport sizes required')
    scale = min(bw / sw, bh / sh)
    return max(1, min(bw, round(sw * scale))), max(1, min(bh, round(sh * scale)))


def initial_size(screen_width, screen_height, scale=1.):
    return min(round(1320*scale), max(1, int(screen_width * .90))), min(round(900*scale), max(1, int(screen_height * .85)))


JOINT_NAMES = {'left_eye':'左眼', 'right_eye':'右眼', 'eye_midpoint':'双眼中点',
    'nose':'鼻部', 'left_shoulder':'左肩', 'right_shoulder':'右肩',
    'left_elbow':'左肘', 'right_elbow':'右肘', 'left_wrist':'左腕', 'right_wrist':'右腕',
    'left_hip':'左髋', 'right_hip':'右髋', 'left_knee':'左膝', 'right_knee':'右膝',
    'left_ankle':'左踝', 'right_ankle':'右踝'}


def readout_cells(rows, registration):
    """Rejected candidates never appear as accepted XYZ, even in the GUI."""
    field = 'world_filtered_mm' if registration is not None else 'camera_filtered_mm'
    result = []
    for row in rows:
        xyz = row.get(field) if row['status'] == 'accepted' else None
        values = ['—'] * 3 if xyz is None else [f'{float(v):.1f}' for v in xyz]
        label = {'accepted':'有效', 'candidate':'候选：未通过检查', 'missing':'未检测到',
                 'rejected':'未通过检查'}.get(row['status'], row['status'])
        result.append((JOINT_NAMES.get(row['joint'], row['joint']), *values, label, row.get('reason', '')))
    return result


def coordinate_label(registration):
    if registration is None:
        return '相机坐标系（双目校正后的左相机）'
    meta = registration.get('metadata', {})
    if meta.get('mode') == 'camera_midpoint':
        return '默认相机中点｜+X 向前，+Y 右→左，+Z 假定向上'
    if meta.get('mode') == 'zero':
        return f'相对原点：{registration["name"]}｜轴向保持不变'
    return f'已标定坐标系：{registration["name"]}'


def tracking_view(rows, registration, *, calibrated, recording, record_status, smoothing,
                  cameras, fps, details=(), warnings=(), notice=''):
    hint = ('已加载双目标定。可直接读取坐标；需要改变原点或轴向时，点击「坐标与原点」。'
            if calibrated else '尚无有效双目标定。点击「双目标定」，完整显示棋盘格并在不同姿态保持静止。')
    meta = {} if registration is None else registration.get('metadata', {})
    if meta.get('up_reference') == 'camera_mount_assumption':
        hint += ' 默认向上基于相机水平正立安装；严格水平请设置完整坐标系。'
    return {'mode':'tracking', 'title':'实时测量',
        'summary':f'左相机 {cameras[0]} / 右相机 {cameras[1]}  ·  {fps}  ·  {"正在录制" if recording else "未录制"}',
        'hint':hint, 'frame':coordinate_label(registration), 'rows':readout_cells(rows,registration),
        'details':'\n'.join(map(str, details)), 'warnings':'\n'.join(map(str,warnings)),
        'notice':notice, 'record_status':record_status, 'progress':None,
        'actions':[Action(ord('c'),'双目标定  C'), Action(ord('w'),'坐标与原点  W',calibrated),
            Action(ord('t'),'停止录制  T' if recording else '开始录制  T',calibrated),
            Action(ord('f'),'关闭平滑  F' if smoothing else '开启平滑  F'),
            Action(ord('m'),'详细信息  M'), Action(ord('q'),'退出')],
        'extra_actions':[Action(ord('s'),'保存诊断快照  S'), Action(ord('v'),'检查棋盘尺寸  V',calibrated),
            Action(ord('p'),'保留当前标定副本  P',calibrated),Action(ord('d'),'切换终端诊断  D'),
            Action(ord('g'),'清理项目临时数据  G')]}


CAPTURE_REASONS = {
    'detection_failed':'左右画面都需要完整识别棋盘格。',
    'board_too_small':'棋盘格在画面中太小，请靠近一些。',
    'insufficient_observations':'正在积累有效检测，请继续保持静止。',
    'settling':'已识别棋盘格，正在确认持续静止。',
    'moving':'检测到角点移动，请固定棋盘格。',
    'corner_order_jump':'角点顺序发生变化，正在重新确认。',
    'duplicate_pose':'这个姿态已经采样，请明显移动或倾斜棋盘格。',
    'waiting_interval':'已稳定，等待自动采样间隔。',
    'auto_disabled':'自动采样已在配置中关闭；可使用手动采样。',
    'auto_captured':'自动采样成功！保持不动不会重复采样，请换一个姿态。',
    'manual_captured':'手动采样成功。重复姿态不增加标定覆盖范围。',
    'capture_failed':'保存采样图片失败，样本未计数。请检查磁盘与目录权限。',
    'invalid_corners':'角点数据异常，正在重新检测。',
    'invalid_timestamp':'观测时间异常，等待下一次有效检测。',
    'duplicate_observation':'等待新的观测数据。', 'ready':'条件满足，可以采样。'}


def calibration_view(calibrator, *, notice=''):
    cur = calibrator.current or {}
    def number(key, unit=''):
        value = cur.get(key)
        return '—' if value is None else f'{float(value):.2f}{unit}'
    count = len(calibrator.samples)
    ready = calibrator.can_solve()
    progress = cur.get('stability_progress', 0)
    progress = min(1., max(0., float(progress))) if math.isfinite(float(progress)) else 0.
    details = [f'自动采样：{"开启" if calibrator.auto_capture else "关闭"}',
        f'有效双目检测频率：{number("effective_detection_hz", " Hz")}；标定循环：{number("calibration_loop_hz", " Hz")}',
        f'检测耗时 左 / 右：{number("detector_left_ms", " ms")} / {number("detector_right_ms", " ms")}',
        f'角点运动 左 / 右：{number("motion_left_px", " px")} / {number("motion_right_px", " px")}',
        f'持续漂移 左 / 右：{number("drift_left_px", " px")} / {number("drift_right_px", " px")}',
        f'静止观测：{number("stable_dwell_s", " s")}；有效次数：{cur.get("stability_observations", 0)}',
        f'面积比例 左 / 右：{number("area_ratio_left")} / {number("area_ratio_right")}',
        f'姿态距离：{number("pose_distance")}；最小多样性：{calibrator.diversity_threshold:g}',
        f'间隔剩余：{number("interval_remaining_s", " s")}；稳定性重置：{cur.get("stability_reset_reason") or "无"}',
        f'覆盖评分：{calibrator.readiness():.0f}/100（启发式，不是精度保证）',
        f'原始状态：{cur.get("capture_reason", "detection_failed")}', str(cur.get('capture_error') or '')]
    hint = CAPTURE_REASONS.get(cur.get('capture_reason'), '让完整棋盘格出现在左右画面，保持静止以自动采样。')
    last=getattr(calibrator,'last_capture_notice','')
    now=getattr(calibrator,'_current_timestamp',None)
    until=getattr(calibrator,'_notice_until',None)
    if isinstance(last,str) and last and now is not None and until is not None and now<=until:
        recent=('手动采样成功，但姿态高度重复；已保留强制采样。' if 'DUPLICATE WARNING' in last else
                '采样图片保存失败：'+last if last.startswith('CAPTURE FAILED') else
                f'{"手动" if last.startswith("MANUAL") else "自动"}采样成功，当前共 {count} 对。')
        notice='\n'.join(x for x in (notice,recent) if x)
    return {'mode':'calibration', 'title':'双目标定 · 采集棋盘格',
        'summary':f'已采集 {count} / 目标 {calibrator.target_pairs}  ·  求解至少 {calibrator.min_pairs}  ·  自动采样 {"开启" if calibrator.auto_capture else "关闭"}',
        'hint':hint, 'frame':'1 放好棋盘 → 2 换姿态并静止 → 3 求解 → 返回实时测量',
        'rows':[], 'details':'\n'.join(details), 'warnings':'', 'notice':notice,
        'record_status':f'左侧识别：{"成功" if cur.get("detected_left") else "未识别"}  /  右侧识别：{"成功" if cur.get("detected_right") else "未识别"}',
        'progress':progress*100,
        'actions':[Action(ord(' '),'手动采样  SPACE', bool(cur.get('valid') and cur.get('good_area'))),
            Action(ord('r'),'计算标定  R',ready),Action(ord('c'),'返回测量  C'),
            Action(ord('x'),'丢弃本次采样  X'),Action(ord('q'),'退出')], 'extra_actions':[]}
