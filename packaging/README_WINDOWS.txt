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

重新封包（原始 PR #11 的 ModuleNotFoundError: stereo_pose.diagnostics）：
- 原因：PyInstaller 自动发现无法稳定枚举 PyArmor 混淆后的全部内部模块。
- 已修改 packaging/StereoPose.spec，直接扫描 build/obfuscated/stereo_pose 下所有 .py，把模块逐个列入 hiddenimports。
- 更新源码后，在仓库根目录双击 BUILD_LOCAL_EXE.bat，构建后使用新的 dist/StereoPose 整个文件夹。
- 重新构建会重建 dist/StereoPose；如果旧 EXE 文件夹里已有 config.json、runtime 标定和录制数据，请先复制到别处，再放回新目录。
- 此修复尚未在 Windows 编译环境实测，所以不宣称新生成包已通过运行验证。

保护说明：
- 第一方 Python 模块以 PyArmor 形式混淆，再由 PyInstaller 作为独立 Windows 程序打包。
- 不附加用户输入密钥、远程授权检查、文件哈希门禁或设备绑定。
- 这是基础混淆/提高逆向成本，不是无法破解的密码学安全承诺。
- 本包在 CI 中打包，不代表已经在用户的 DJI Action 4 和现场几何中做过实测。
- Ultralytics/YOLO 与 PyTorch 等第三方组件有各自许可证；外部分发或商业使用前应核对许可条件。
