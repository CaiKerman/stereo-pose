Stereo Pose Task001 RC — 先看我

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
C       进入标定 / 返回
SPACE   手动采样（仍然要求棋盘稳定）
R       求解标定
X       放弃当前标定 session
P       固定保存当前激活标定
F       开关 One Euro 平滑
G       清理自动标定历史
Q/ESC   退出

第一次实机验收建议：
- 先只做静态/慢动作
- 标定采 24~30 组
- 尽量覆盖画面左中右、上中下、近中远，并改变棋盘姿态
- readiness >= 75 后再按 R
