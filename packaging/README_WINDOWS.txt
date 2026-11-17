Stereo Pose / PR #10 - Windows 便携版

1. 解压下载的整个 StereoPose 文件夹（不要只拷贝 EXE）。
2. 双击 StereoPose.exe。无须安装 Python、PyTorch、OpenCV、Ultralytics 或 Conda。
3. 首次启动自动在 EXE 所在目录创建 config.json；默认姿态模型 yolo11n-pose.pt 已放在 EXE 同级目录。
4. 配置、已有的 runtime 文件夹以及模型权重均为可编辑文件；移动旧数据时直接复制到 EXE 同级目录。
5. 标定、记录和诊断均保存在 EXE 同级的 runtime 文件夹。启动时无需输入任何密钥；不联网验证授权、不绑定设备、不设置到期时间。
6. 本包包含 CUDA 12.8 版 PyTorch，可在支持的 NVIDIA 显卡上加速，没有 CUDA 时由程序选择 CPU；Windows 10/11 x64。
7. 如 Windows SmartScreen 报未知发布者：当前包未做 Authenticode 代码签名，不能将“已混淆”误认为“已签名”。
8. 如在另一台计算机运行，摄像头索引、设备设置与物理标定几何需要按实际情况核对。
9. EXE 旁的 _internal 文件夹是程序运行库，不可只复制 StereoPose.exe 单独运行。

本次重新修复封装模块缺失（2026-11-17）：
- 原封包方式让 PyInstaller 直接分析已混淆的入口代码，导致先后缺少 diagnostics、calibration.package 等内部模块。
- 已移除“扫描混淆产物推测内部模块”的不可靠方案。
- 新构建从 build/package_source 中完整、未混淆的入口及 stereo_pose 源码进行 PyInstaller 依赖分析，
  再用 PyArmor 官方的 gen --pack <spec> 替换并封装为受保护的二进制。
- 原始源代码和打包脚本仍留在 Git 仓库，最终 EXE 目录不包含 src 源码。
- 构建前自动备份旧 dist/StereoPose/config.json、runtime、*.pt 到
  build/portable_user_data，构建完成后复制回新 EXE 目录，不进行哈希门禁。
- 在项目根目录双击 BUILD_LOCAL_EXE.bat 重新封包；原先生成的旧 EXE 不会自行修复。
- 如已将数据另存到其他位置，继续按照已有配置使用即可。
- 新版本尚未在 Windows 上验证完整打包与摄像头运行；代码提交不代表构建通过。
