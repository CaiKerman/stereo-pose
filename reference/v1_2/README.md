# Stereo Pose 3D v1.2

本版重点解决普通 USB webcam 的**非同步采样**、运行时标定稳定性、三角测量误差过滤与低延迟平滑。

## 1. 启动

把本地模型放在项目根目录：

```text
yolo11n-pose.pt
```

把：

```text
config.example.json
```

复制为：

```text
config.json
```

运行：

```bash
python main.py
```

程序默认自动加载 `calibrations/` 中修改时间最新的 `stereo_*.npz`。如果不存在新版文件，但根目录还有旧版 `stereo_calib.npz`，仍会兼容加载。

---

# 2. 两个 webcam 不同步：这一版怎么处理

普通 webcam 通常没有硬件同步，也通常拿不到可靠的真实曝光时间戳。因此软件无法保证左右画面来自完全相同的物理时刻。

v1.2 做了两件事：

1. 每轮先对左右摄像头都执行 `grab()`，再执行 `retrieve()` 解码，减少“先完整读取左画面、再完整读取右画面”造成的软件顺序延迟。
2. `host_grab_skew_ms` 被记录并显示，但它**仅是主机侧抓帧时差诊断，不等于传感器真实曝光时间差**。

动态动作仍可能因两只 webcam 的内部缓存、曝光和刷新节奏不同而产生残余 3D 误差。要从物理上解决这一问题，需要可硬件同步的相机。

---

# 3. 运行时标定：只采静止棋盘

按：

```text
C
```

进入标定模式。

程序只有在以下条件同时满足时才允许保存样本：

- 左右摄像头都检测到完整棋盘；
- 棋盘在画面中面积足够；
- 棋盘连续稳定一段时间；
- 左右画面中的棋盘角点在稳定窗口内运动量都低于阈值；
- 自动采样时，还要求当前姿态与已有样本有足够差异。

默认参数：

```json
"stable_dwell_s": 0.55,
"stable_min_frames": 4,
"stable_corner_motion_px": 2.0
```

含义：棋盘需要连续稳定约半秒，并且稳定窗口内平均角点漂移不超过约 2 像素。

### 标定按键

```text
SPACE   手动保存，但仍必须满足“棋盘静止”条件
R       计算标定
X       放弃并删除当前临时样本
C       返回 Tracking，临时样本保留
Q/ESC   退出
```

### readiness

`readiness 0~100` 仍然是启发式“样本准备度”，不是统计置信区间。它综合：

- 样本数；
- 画面区域覆盖；
- 近/中/远尺度变化；
- 棋盘角度变化。

建议 `readiness >= 75` 再按 `R`。

---

# 4. 标定求解后的误差控制

标定完成后保存：

```text
calibrations/stereo_YYYYMMDD_HHMMSS.npz
```

除原矩阵外，还记录：

```text
Stereo RMS
左右单目标定 RMS
样本平均极线误差
样本最大极线误差
初始样本数
最终样本数
被剔除的异常样本数
创建日期时间
```

默认启用 robust prune：第一次求解后计算每组棋盘的校正后极线误差，把明显异常的样本有限度地剔除，再重新求解。

配置：

```json
"robust_prune": true,
"prune_min_epipolar_px": 0.8,
"prune_max_epipolar_px": 2.5,
"max_prune_fraction": 0.25
```

最多只剔除设定比例，且不会把有效样本降到 `min_pairs_to_solve` 以下。

---

# 5. 每个关节点的几何质量控制

每个关节点在输出前都会计算：

- 左右 Pose 置信度；
- 校正后的极线误差 `epipolar_error_px`；
- 三角化后重新投影到两台相机的误差 `reprojection_error_px`；
- 深度范围；
- 相对上一有效点的空间速度；
- 一个启发式 `quality.score`。

默认阈值：

```json
"quality": {
  "max_epipolar_error_px": 3.0,
  "max_reprojection_error_px": 2.5,
  "min_depth_mm": 250.0,
  "max_depth_mm": 7000.0,
  "min_quality_score": 0.12,
  "max_joint_speed_mm_s": 6000.0,
  "speed_gate_reset_after_s": 0.6
}
```

超过阈值的点不会进入最终 XYZ 输出。

`quality.score` 也是启发式质量分，不应解释为统计概率。

---

# 6. One Euro Filter 平滑

默认启用 One Euro Filter（单欧元滤波器）。它比简单移动平均更适合实时人体动作，因为可以在“静止时平滑”和“快速运动时低延迟”之间自动权衡。

默认：

```json
"smoothing": {
  "enabled": true,
  "type": "one_euro",
  "min_cutoff": 1.2,
  "beta": 0.015,
  "d_cutoff": 1.0,
  "reset_after_s": 0.6
}
```

运行时：

```text
F = 开关平滑
```

每个关节报文同时保留：

```text
xyz_mm       平滑后的 XYZ
xyz_raw_mm   通过质量过滤后的原始 XYZ
```

因此后续分析可以随时比较原始值和滤波值。

### 参数直觉

`min_cutoff`：
- 更低 -> 静止时更稳，但延迟更大；
- 更高 -> 响应更快，但抖动更多。

`beta`：
- 更高 -> 快速动作时更快放开滤波，跟手性更好；
- 太高 -> 快速动作时噪声也更容易放大。

当前 `1.2 / 0.015 / 1.0` 是偏保守的起点，不是最终人体工学测量参数。

---

# 7. 正常运行热键

```text
C       进入运行时标定
F       开/关 One Euro 平滑
G       垃圾清理
Q/ESC   退出
```

---

# 8. 垃圾清理

默认：

```text
只保留最新 10 个 calibration NPZ
删除 7 天前残留的失败/中断标定 session
成功标定后默认删除棋盘 PNG，只保留 NPZ
```

清理只作用于：

```text
calibrations/stereo_*.npz
calib_sessions/session_*
```

不会扫描项目其他文件。

---

# 9. 当前最重要的物理限制

即使软件误差控制和平滑都做得很好，**两个没有硬件同步的 webcam 在快速动作下仍可能产生时间视差**：左摄像头看到的是手腕在 t1 的位置，右摄像头看到的是 t1 + Δt 的位置，三角测量会把两个不同物理时刻强行解释成一个 3D 点。

因此：

- 静态姿态、慢速动作：当前方案很有价值；
- 快速手部动作：误差会增加；
- 要做真正高精度动态动作捕捉：最终应考虑硬件同步相机或更多视角。
