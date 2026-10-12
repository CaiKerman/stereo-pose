# Stereo Pose Task003A 编码与审核交接 — 2026-10-12

> 本文件供编码智能体与 GPT 审核者使用。只含任务/架构/验证要求，不含真实用户图像、快照、人体记录或标定 NPZ。
> 正式需求：[Issue #5](https://github.com/CaiKerman/stereo-pose/issues/5) 和 [完整规格](../instructions/003A_WORLD_ALIGNMENT_LIVE_READOUT_CSV.md)。任务入口：[CURRENT_TASK.md](../../CURRENT_TASK.md)。

## 1. 最新业主决定与职责

2026-10-12 17:16（Asia/Shanghai），业主明确指示：

> 直接在当前分支继续开发吧。你弄好交接文档后我通知其他智能体开始开发。

**已授权在当前 `trae/agent-c3dfMx` 分支继续 Task003A 编码，并使用原 PR #3。无需再为这个分支方案索取批准。**
本次 GPT 只整理交接与架构审核要求；由业主通知其他编码智能体开始。
编码智能体实现和自测；GPT 独立审查代码、复现测试、给出验收结论；业主完成摄像头/图码/Windows 实机验收。

旧文档中“新编码分支未授权”“另建 stacked 分支后才可编码”“精度闭环后才做 Task003”的表述被本次决定覆盖。
这不授权合并、修改 PR base、关闭 PR、变基、强推或删除分支。

## 2. 仓库与现有 PR 依赖

私有仓库：[CaiKerman/stereo-pose](https://github.com/CaiKerman/stereo-pose)。

| 项目 | 分支 / 目标 | 本次更新前的 head | 状态 |
|---|---|---|---|
| main | main | d26e64772b8c634851b5812b6015a7ab57124e83 | Task001 基线，缺少 002/002A/002B |
| PR #2 | feat/002-metric-validation-diagnostics → main | ed0421ae595bb2fe19b38ea209b05fba3084ae41 | OPEN，未合并 |
| PR #3 | trae/agent-c3dfMx → feat/002-metric-validation-diagnostics | d7adf887cba73608c1ea2eecdfef586fa1b20985 | OPEN，未合并；Task003A 继续使用 |
| 最后审核通过的实现 | PR #3 | 288860d297ef32a4258b5f5b5f1d632de6a4497c | 通过代码审查，可做实机验收；未获合并批准 |

祖先关系已核实：PR #2 比 main 多 9 次提交，PR #3 比 PR #2 多 20 次提交，均无落后/分叉。
`288860d` 到 `d7adf88` 的 4 次提交只改文档。
本交接也是文档更新；编码前必须获取最新 remote head，不能将上述历史 SHA 当作回退目标。
当前已有 214 项测试通过的开发者报告；本次交接未独立复跑，也未做硬件/Windows 运行验证。

## 3. 编码智能体启动顺序

1. 在现有检出目录先运行 `git status --short`，检查未提交工作，不得 reset/clean 丢弃其他人的改动。
2. `git fetch origin` 后切换现有 `trae/agent-c3dfMx`；若只有远端此分支，可建立**同名本地跟踪分支**，这不是创建新的远端任务分支。
3. `git pull --ff-only origin trae/agent-c3dfMx`；发生分叉则报告实际状态，不自动 rebase/force-push。
4. 用 `git branch --show-current`、`git rev-parse HEAD`、`git rev-parse origin/trae/agent-c3dfMx` 核实工作分支与起点。
5. 按顺序阅读 `AGENTS.md`、`CURRENT_TASK.md`、`REVIEW_INBOX.md` 顶部 Task003A、完整规格和本文件；旧 inbox 保留为历史审核记录。
6. 读相关模块和测试，先跑完整基线，再分 003A-1/2/3 编码、自测、提交检查点。
7. Push 到 **同一个** `trae/agent-c3dfMx`，更新 **同一个 PR #3**；PR base 保持 `feat/002-metric-validation-diagnostics`。
8. 如编码平台强制使用其他远端分支，先报告具体限制；本授权不含自行改变拓扑。

## 4. 本轮 P0 交付

| 功能 | 必须交付的行为 |
|---|---|
| 工程世界坐标 W | 用户输入至少 3 个不共线图码特征点真实 XYZ（mm），推荐 4–6 个以上；拟合 `W=R_wc C+t_wc`，无缩放；显示残差/轴向，用户确认 +Z 物理向上 |
| 置零/相对参考原点 | 只改变原点，保持当前轴向与尺度；记录参考点与派生关系，不声称平移建立了重力方向 |
| 统一 NPZ | 一份新版本包含原 stereo 数组和 W 变换/参考点/方法/时间/身份/残差；旧文件不覆盖；明确启用，重启恢复同一文件 |
| 实时 XYZ | 左眼、右眼、双眼三维中点和用户选择关节；中点要求两眼同帧都有效；明确坐标系、mm、accepted/rejected/candidate/missing |
| 手动 CSV | 默认停止；`T` 启停，默认 5Hz 输出采样；只采样新鲜已处理帧，推理慢不复制旧帧；长表 joints.csv + session.json |
| 状态与兼容 | 简洁读数、坐标系名称、REC 时长/样本数/路径；保持既有 S/M/D/V/C/R/P/F/G/Q 和标定模式热键 |

不开发：视频、Bookmarks/事件标签、绘图/回放、历史会话浏览器、额外 AI 人眼模型、复杂 GUI、多人识别、RAMSIS 对接、持续图码追踪。
Task002C 绝对精度/误差根因闭环暂缓但未解决；不放宽任何现有质量门槛，不宣传眼点 ±5mm 或关节 ±10mm 已实现。

## 5. 已有代码与架构预审重点

应用是 Windows 解压运行的 Python/OpenCV/YOLO 工程，`RUN_ME.bat` + 本地模型。
现有流水线：一对图像 → 一次双视图 YOLO 推理 → rectified-left-camera（双目校正后左相机）C 坐标三角重建 → 几何/速度门槛 → One Euro 平滑 → legacy v1.2。

| 接口/模块 | 当前事实 | Task003A 设计要求 |
|---|---|---|
| coordinates/rigid.py | RigidTransform 仅检查数组形状；没有对应点拟合或正规旋转校验 | 增加纯数学拟合/有限值/正交/det=+1/退化检测；测试逆变换与无缩放 |
| calibration/selection.py + app/runner.py | 默认选最新 auto；仅 explicit 模式读取指定文件 | 同一完整标定包作为激活来源；持久化明确选择；缺失/损坏时报警，不能悄悄换文件 |
| persistence/promote.py + P | 当前 P 复制到 saved，但不切换/持久化 active | 复用保存库机制，明确区分“保留副本”和“启用文件”，确保 W 重启不丢 |
| joints.py + runner | 默认 ergonomics 不含眼点，循环只处理选中关节 | 用一次推理结果处理所需关节合集；旧输出按原选择投影，保持旧计数/均值口径 |
| models.py + quality | PoseFrame.joints 只有 accepted；候选在几何/诊断阶段 | 保留每帧候选及拒绝原因到独立数据视图；不能把候选放入有效 XYZ |
| outputs/v1_message.py | xyz_mm/xyz_raw_mm 表示 C，coordinate_system=rectified_left_camera | 保留相机 PoseFrame/旧字段语义；显示/CSV 经独立 W 变换，不原地覆盖旧结构 |
| runner 标定切换和过滤切换 | C→R 会换 triangulator；F 会切换平滑 | 记录中的标定/坐标系改变须显式结束/分段；过滤状态变更须记录适用状态或结束/分段 |

架构实施边界：

- **平面标定板有效。** 3 个及以上不共线共面点可建立刚体对应；不能要求控制点必须非共面或中心化矩阵秩=3。拒绝共线/近共线，恰好 3 点提示缺少独立冗余。
- **中心与角点不是同一个特征。** ArUco 左右 ID、dictionary、feature_type 和角点顺序显式匹配；WORLD TRIAD 的 P0/P1/P2 不等于未经核实的 ID0/1/2。倾斜透视/畸变条件下测试中心定义，不能直接把原始像素四角算术平均当作物理中心真值。
- **两个身份用途分开。** 完整 NPZ 文件 SHA-256（内容校验）与 stereo 几何指纹（W 所依附的标定）分别定义；文件加入 W 后不能用新增文件的整体 hash 循环引用自己。保留原数组 shape/dtype/内容与额外 metadata，allow_pickle=False。
- **物理移动不能靠数值索引自动识别。** 重算标定/几何或分辨率不匹配使 W 失效或明确拒绝；仅 USB 枚举索引变化提示人工确认。索引相同和文件指纹一致也不能证明摄像头没有移动。
- **W 确认是完整操作。** 导入/检测/预览/拟合/保存/明确激活和持久化需有一致的成功/失败状态；取消与失败保留旧 active。可保留新生成但未启用的文件并说明，不得显示“成功”而重启后丢失。
- **坐标与候选按同帧来源区分。** Accepted raw/filtered C、对应 W 和 candidate 分开；失效有效坐标留空，不使用零值或旧帧。eye_midpoint 是观测眼点中点，不是眼球转动中心/注视点。
- **5Hz 是记录频率。** 调度使用单调时钟，保留原帧 wall_timestamp_ns/frame_index；不加第二路摄像头读取/YOLO，不用固定帧取模，不追赶式写多份旧帧。
- **停止/故障保留用户数据。** session 唯一命名、流式写入、及时 flush，记录失败状态与部分文件；磁盘满/路径错误不崩溃跟踪，G 不清理 recordings，退出关闭句柄。
- ArUco 支持检查真实已安装 OpenCV 的 `cv2.aruco`；缺失时清楚诊断，不在线安装。ChArUco/十字点阵只留可扩展识别/对应接口，本轮实现自由 ArUco 与 WORLD TRIAD。

## 6. 三阶段编码与审查

| 阶段 | 交付及检查点 |
|---|---|
| 003A-1 | 纯刚体拟合、图码对应、输入拒绝、统一 NPZ、显式启用与真实启动/重载；先通过数学和保存恢复测试 |
| 003A-2 | W 向导/CSV 参考点导入、ID/坐标轴预览确认撤销、眼点和所选关节实时读数、候选状态、legacy 输出投影 |
| 003A-3 | T 手动 CSV、单调时钟采样、冻结 session 标定与配置状态、磁盘/退出恢复、Windows 文档、完整回归 |

每阶段做独立提交和测试结果，避免把三阶段揉成无法审查的大提交。
各阶段正常实施不需要再次询问是否开发；遇到改变范围、协议或 Git 拓扑的决定再交业主/GPT。

## 7. 审核者验收矩阵

| 主题 | 必须有的确定性证据 |
|---|---|
| 刚体数学 | 任意正规 R/t 精确恢复；det=+1、正交、逆变换、距离/mm 不变；平面/倾斜平面可用；少于 3 点、共线/近共线、NaN/Inf、错配/重复 ID、离群/不足内点拒绝 |
| 图码 | 同 ID/特征严格对应、缺失/遮挡/重复/错误 dictionary；合成真实投影下中心/角点定义正确；确认/取消/失败路径 |
| NPZ | allow_pickle=False；旧 stereo-only；D=(1,5)/(5,1)/(5,) 原样保留；唯一文件不覆盖、保存/启用失败；重启仍启用 W；新 auto 不抢占；新 stereo 解算失效 W；几何指纹篡改 |
| 显示/数据语义 | 两眼均有效才有中点；raw/filtered/candidate 分列；丢失/拒绝留空；旧 v1.2 坐标、字段及原选中关节统计保持一致 |
| CSV 时间 | 假时钟 30/7/5/2FPS、抖动；真时间戳、无重复 frame；T 默认 OFF/快切/停止/退出；慢推理不补旧帧 |
| 文件/会话 | 长表每 sample×requested joint；缺失/拒绝原因；冻结 NPZ hash/坐标系/模型/配置；写失败/磁盘满保留已写数据；历史文件不覆盖，G 不删除 |
| 旧功能与平台 | 完整 001/002/002A/002B 回归、S 保存→离线重放、M/D/V/C/R/P/F/G、相机选择取消/重扫、Windows 启动；真实/模拟测试明确区分 |

基线和完整回归命令（现有测试引导可发现 src，无需联网安装）：

```bash
python -m pytest tests/ -q
python -m unittest discover -s tests -t .
python -m pytest tests/unit/test_snapshot.py -q
```

PowerShell 离线诊断：

```powershell
$env:PYTHONPATH = "src"
python -m stereo_pose doctor
```

报告 exact commands、head SHA、操作系统/Python/NumPy/OpenCV、通过/失败/跳过数。
新增测试命令按实际文件提供，不能把 mock 算作 Windows GUI、摄像头或真实模型验证。

## 8. 完成时必须提交

更新 CHANGE_SUMMARY.md、TEST_REPORT.md、REVIEW_FOR_OWNERS.md、REVIEW_INBOX.md、中文 README_先看我.txt、README.md、DATA_FLOW.md、config schema 和协议/NPZ/CSV 定义。
交付实现 head SHA、PR #3 链接、阶段差异、运行命令、合成 reference_points.csv 和合成 CSV/session 例子。
PR 描述应改写为最终 Task002A/002B + Task003A 的实际范围，并保留未合并依赖说明；不能声称尚未实现的功能已经通过。
标记 Task003A “READY FOR GPT REVIEW”，停止自动推进，不自行合并。
GPT 审核后，由业主验收图码轴向/真实输入、实时眼点、T 录制、重启恢复 W 与旧热键。
旧 M 完整检查、相机选择 cancel/rescan 尚未正式确认的项目并入这次实机验收，不虚构已通过。

## 9. 已打印图案与已知精度事实

已打印 StereoPose_Markers_A4_ALL_14pages.pdf：
DICT_4X4_50 自由 ID0–7、黑边长 60mm；WORLD TRIAD 三中心 P0=(0,0)、P1=(100,0)、P2=(0,100)；
ChArUco 5×7（28/20mm）和 7×10（20/14mm）；备份 DICT_5X5_50 ID0–5（50mm）；50mm 十字点阵。
打印实物以测量输入为准。真实布局未读取时使用用户映射，不猜 WORLD TRIAD 数字 ID；通用 ArUco/对应关系开发不依赖先拿到 PDF。

最新私人快照曾为 LEFT1/RIGHT2、1280×720、基线约 555.5mm；索引可能变化。
棋盘局部几何较稳定但眼点极线残差明显，缺少独立眼点真实三维真值。
重复性和自洽性不能证明绝对精度；普通 USB 相机不能承诺真实硬件曝光同步。
用户面部与坐标数据仅在本地/获授权的私人诊断中处理，不提交 GitHub。

## 10. 业主可复制给编码智能体的消息

> 从现有 `trae/agent-c3dfMx` 分支最新 head 继续实现 Task003A，更新原 PR #3，base 保持 `feat/002-metric-validation-diagnostics`。我已授权在这个分支继续，无需新建分支/PR。先读取 AGENTS.md、CURRENT_TASK.md、REVIEW_INBOX.md 顶部、Issue #5、完整 Task003A 规格与本交接，先跑基线测试。只开发 P0：工程世界坐标与置零、统一 stereo+world NPZ 保存及重启恢复、眼点/关节实时 XYZ、T 手动 5Hz CSV；按 003A-1/2/3 提交检查点。精度闭环暂缓，P1/P2 不做。保留质量门槛、legacy v1.2 和既有热键，不上传用户人脸/快照/NPZ/人体记录。提交代码与精确测试报告后停止，交 GPT 审核；不合并、改 base、变基、强推或删分支。
