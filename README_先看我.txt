Stereo Pose Task002 — 先看我（双目标定 / 度量验证 / 关节拒绝诊断）

最简单的使用方式：

1. 解压整个 ZIP 到一个新文件夹。
2. 把你之前已经用过的 yolo11n-pose.pt 复制到这个文件夹，
   与 RUN_ME.bat / RUN_ME.py 同级。
3. 双击 RUN_ME.bat。

它不会：
- pip install 本项目
- 修改 site-packages
- 往系统目录写项目文件

它会：
- 直接从本 ZIP 的 src/ 目录加载程序
- 第一次运行时从 configs/default.json 复制出一个本地 config.json
- 把标定、session、日志等运行数据放在本解压目录下的 runtime/

所以试完不想要了，直接删除整个解压文件夹即可。

如果 RUN_ME.bat 报：
OpenCV / PyTorch / Ultralytics missing

说明 Windows 双击时调用的 python 不是你以前成功运行双目 PoC 的那个 Python。
它不会自行安装依赖。

默认摄像头：
left = 0
right = 1

如果不对，用记事本打开 config.json 修改即可。

当前标定板：
- 10 x 7 个方格
- 9 x 6 内角点
- 单格 25 mm
- A4 横向
- 打印必须 100% / Actual Size，不要 Fit to Page

热键：
C       进入标定 / 返回（自动采样会等待画面 STABLE）
SPACE   强制手动采样（左右都完整识别 + 最小棋盘面积）
R       求解标定
X       放弃当前标定 session
P       固定保存当前激活标定
D       开/关逐关节拒绝诊断（按 explain 帧率打印，默认关）
V       单帧棋盘度量验证（需要已激活标定，保存报告到 runtime/validation/）
F       开关 One Euro 平滑
G       清理自动标定历史
Q/ESC   退出

Task002 新增说明：
- D 键：逐关节输出每个被拒绝关节的精确原因（置信度/极线/重投影/深度/质量/速度），
  用于解释偶尔消失的肩/肘等关节点为什么没被接受。
- V 键：用同一块 25mm 棋盘做 3D 度量验证，输出横向/纵向间距、尺度误差、
  平面拟合残差、极线/重投影误差、深度范围，并保存 JSON 报告到
  runtime/validation/metric_YYYYMMDD_HHMMSS.json（不会被标定历史清理删除）。
- 度量验证为单帧（sample_mode=single_frame），报告内明确标注。当前不设通过/失败阈值，
  只暴露测量值。

第一次实机验收建议：
- 先只做静态/慢动作
- 标定采 24~30 组
- 尽量覆盖画面左中右、上中下、近中远，并改变棋盘姿态
- readiness >= 75 后再按 R


当前标定行为（默认参数）：
- 自动稳定时间 0.30 s，稳定角点运动容忍 5 px
- 棋盘最小画面面积 1.2%
- 自动采样等待稳定（STABLE）；SPACE 为人工强制采样（需左右完整识别 + 最小面积）
- 标定画面会显示左右棋盘面积百分比和 corner motion
