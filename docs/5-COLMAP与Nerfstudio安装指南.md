# COLMAP 与 Nerfstudio 安装指南

## 1. 目的

本文档用于在当前这台 Windows 开发机上安装 3DGS 工作链的两个关键组件：

- `COLMAP`：从图片或视频帧中恢复相机位姿，供后续 3DGS 初始化使用
- `nerfstudio`：训练框架，提供 `ns-process-data`、`ns-train splatfacto`、`ns-export gaussian-splat`

这两个组件不是同一个东西，也不是二选一。

按我们当前项目的路线：

`普通商品视频 -> ns-process-data video -> COLMAP 恢复位姿 -> ns-train splatfacto -> ns-export gaussian-splat`

因此二者都要安装。

## 2. 它们分别是什么

### 2.1 COLMAP

`COLMAP` 是经典的 SfM / MVS 工具链。对我们的项目来说，它负责从用户上传的普通视频帧中恢复相机位姿和稀疏点云。

COLMAP 官方文档：

- 安装页：https://colmap.github.io/install.html
- 教程页：https://colmap.github.io/tutorial.html

官方文档说明：

- Windows 可以直接使用预编译二进制
- 预编译包同时提供 GUI 和命令行
- 命令行可以通过 `COLMAP.bat -h` 调用

### 2.2 Nerfstudio

`nerfstudio` 是一个 NeRF / Gaussian Splatting 训练框架。我们项目里用它做三件事：

1. `ns-process-data video`
2. `ns-train splatfacto`
3. `ns-export gaussian-splat`

官方文档：

- 安装页：https://docs.nerf.studio/quickstart/installation.html
- 自定义数据页：https://docs.nerf.studio/quickstart/custom_dataset.html
- Splatfacto 文档：https://docs.nerf.studio/nerfology/methods/splat.html

官方资料明确说明：

- `ns-process-data {video,images}` 需要 `COLMAP`
- `Splatfacto` 是 nerfstudio 的 Gaussian Splatting 实现
- `ns-export gaussian-splat` 可以导出 `.ply`

## 3. 当前机器基线

我已经在这台机器上确认了以下事实：

- 操作系统：Windows
- GPU：`NVIDIA GeForce RTX 4060 Laptop GPU`
- 驱动版本：`595.71`
- `nvidia-smi` 显示 CUDA Runtime 版本：`13.2`
- `conda 25.3.1` 已安装
- `git 2.50.1` 已安装
- `ffmpeg 8.0.1` 已安装并可直接调用
- `Python 3.13.2` 是宿主机默认 Python
- `Visual Studio 2022 Community` 已安装
- `colmap` 当前还不在 `PATH`
- 当前 shell 中 `cl.exe`、`cmake`、`ninja` 都还不可直接调用

对本项目的含义：

- 宿主机 Python `3.13.2` 不适合直接承担 nerfstudio 训练环境
- `COLMAP` 还需要安装并加入 `PATH`
- `nerfstudio` 需要单独放进 Conda 环境
- `tiny-cuda-nn` 在 Windows 上大概率会依赖 VS 的 C++ 编译工具链

## 4. 版本策略

### 4.1 为什么不直接用宿主机 Python 3.13

我们的仓库代码和 3D 训练依赖都不适合直接绑在宿主机 Python 上。训练环境必须独立。

另外，当前仓库里的 Python 代码已经使用了 Python 3.10 的类型语法，比如 `Path | None`。因此本项目训练环境不建议降到 Python 3.8。

### 4.2 本项目推荐版本

本项目建议固定为：

- Conda 环境名：`3dgs_app`
- Python：`3.10`
- PyTorch：按 nerfstudio 安装页中的 `Torch 2.1.2 + CUDA 11.8`
- CUDA Toolkit：`11.8`

说明：

- nerfstudio 官方安装页示例环境是 `python=3.8`
- PyPI 上 nerfstudio 的 `Requires-Python` 为 `>=3.8`
- 但当前项目代码要求至少 Python 3.10，因此这里统一提升到 `3.10`

PyPI：

- https://pypi.org/project/nerfstudio/

## 5. 安装顺序总览

建议严格按这个顺序执行：

1. 安装并验证 `COLMAP`
2. 创建 `3dgs_app` Conda 环境
3. 在 `3dgs_app` 里安装 PyTorch + CUDA Toolkit
4. 安装 `tiny-cuda-nn`
5. 安装 `nerfstudio`
6. 验证 `ns-process-data`、`ns-train`、`ns-export`

## 6. 安装 COLMAP

## 6.1 推荐方案：Windows 预编译二进制

COLMAP 官方安装页说明，Windows 可直接使用预编译二进制，命令行通过 `COLMAP.bat` 进入。

参考：

- https://colmap.github.io/install.html

### 步骤

1. 打开官方安装页中给出的下载入口：

   https://demuc.de/colmap/

2. 下载 Windows 预编译包。

3. 解压到一个固定目录，建议：

   ```text
   D:\tools\COLMAP
   ```

4. 把这个目录加入用户级或系统级 `PATH`。

5. 关闭并重新打开 PowerShell。

6. 验证命令：

   ```powershell
   colmap -h
   ```

如果 `colmap -h` 仍然失败，也可以直接试：

```powershell
COLMAP.bat -h
```

只要 `COLMAP.bat` 所在目录已经进了 `PATH`，Windows 一般也可以直接用 `colmap` 调起它。

### 本项目验收标准

必须通过：

```powershell
colmap -h
```

因为我们的训练脚本会直接检查 `colmap` 是否可执行。

## 6.2 备选方案：按官方建议用 vcpkg 编译

如果预编译包运行异常，官方在 Windows 上推荐通过 `vcpkg` 构建：

```powershell
git clone https://github.com/microsoft/vcpkg
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg install colmap[cuda,tests]:x64-windows
```

参考：

- https://colmap.github.io/install.html

这条路更重，优点是可控；缺点是耗时长。对当前项目来说，不建议第一步就走这条路。

## 7. 安装 Nerfstudio

## 7.1 创建 Conda 环境

在新的命令行窗口执行：

```powershell
cmd /c conda create --name 3dgs_app -y python=3.10
```

激活环境：

```powershell
cmd /c conda activate 3dgs_app
```

如果你是在普通 PowerShell 里执行，`cmd /c conda activate ...` 只会在子进程里生效。更稳妥的方式是：

1. 先运行：

   ```powershell
   cmd /k conda activate 3dgs_app
   ```

2. 然后在弹出的新 `cmd` 窗口里继续执行后面的安装命令。

进入环境后先升级 pip：

```powershell
python -m pip install --upgrade pip
```

## 7.2 安装 PyTorch 与 CUDA Toolkit

按 nerfstudio 官方安装页，推荐使用：

```powershell
pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
conda install -c "nvidia/label/cuda-11.8.0" cuda-toolkit
```

参考：

- https://docs.nerf.studio/quickstart/installation.html

说明：

- 你当前 `nvidia-smi` 显示的是驱动支持到 CUDA Runtime `13.2`
- 这不要求你安装 `13.2` 的 toolkit
- 当前项目仍然按 nerfstudio 官方推荐的 `Torch 2.1.2 + CUDA 11.8` 走

### 验证

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

预期结果：

- 能正常输出 torch 版本
- `torch.cuda.is_available()` 为 `True`

## 7.3 安装 tiny-cuda-nn

按 nerfstudio 官方 Windows 安装方式：

```powershell
pip install git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```

参考：

- https://docs.nerf.studio/quickstart/installation.html

### 先修 Python 打包环境

在当前 Windows 环境下，直接安装时很容易先遇到：

```text
ModuleNotFoundError: No module named 'pkg_resources'
```

根因是：

- `tiny-cuda-nn` 的 `bindings/torch/setup.py` 仍然直接导入 `pkg_resources`
- 新版本 `setuptools` 已经不再稳定提供这个模块
- 如果直接 `pip install ...`，`pip` 还会创建隔离构建环境，把新版 `setuptools` 拉回来

因此在 `3dgs_app` 环境里，建议先固定：

```powershell
python -m pip install setuptools==80.9.0 wheel "numpy<2" ninja
```

说明：

- `setuptools==80.9.0`：恢复 `pkg_resources`
- `numpy<2`：避免 PyTorch 2.1.2 在 Windows 下出现 NumPy 2 兼容告警
- `ninja`：让 PyTorch 扩展优先走 ninja 后端，而不是慢且更脆弱的 distutils 后端

然后安装 `tiny-cuda-nn` 时，必须关闭构建隔离：

```powershell
pip install --no-build-isolation git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```

如果不加 `--no-build-isolation`，`pip` 会重新创建一个临时构建环境，`pkg_resources` 错误会再次出现。

### 重要说明

这一步在 Windows 上最容易失败，常见原因有三个：

1. 当前 shell 没有 MSVC 编译器
2. 没有安装 VS 的 C++ 工作负载
3. CUDA 架构没有被正确识别

### 如果提示 `cl.exe` 找不到

先确认你安装了 Visual Studio 2022 的 `Desktop development with C++` 工作负载。

然后不要继续在普通 PowerShell 里硬装，改用下面任一方式：

1. 打开 `Developer PowerShell for VS 2022`
2. 打开 `x64 Native Tools Command Prompt for VS 2022`

再重新激活 `3dgs_app` 环境后执行安装。

### 如果当前 Visual Studio 太新，导致 CUDA 11.8 报编译器版本错误

在当前机器上，我们实际踩到了这一类错误：

```text
error STL1002: Unexpected compiler version, expected CUDA 12.4 or newer.
```

根因是：

- 当前环境使用 `CUDA 11.8`
- 系统默认 `MSVC` 版本过新
- `nvcc` 虽然可以通过 `-allow-unsupported-compiler` 绕过第一层版本检查
- 但新的 MSVC / STL 头文件仍可能在编译阶段继续拦截

### 正确做法：安装旧版 x64/x86 MSVC v143 工具集

在 Visual Studio Installer 的“单个组件”里安装：

```text
MSVC v143 - VS 2022 C++ x64/x86 生成工具集(v14.38-17.8)
```

注意：

- 要装的是 `x64/x86`
- 不是 `ARM`

### 如何在指定旧工具集的环境里安装

不要把下面的命令理解成永久设置：

```powershell
cmd /k ""C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.38"
```

它的含义只是：

- 打开一个新的 `cmd` 窗口
- 在这个新窗口里加载 VS 的编译环境变量
- 并把工具集切到 `14.38`

它不是系统永久设置，也不会改写你的全局 PATH。

关闭这个 `cmd` 窗口后，这次切换就失效了。

如果你想“恢复”，不用做任何卸载或回滚操作，直接：

- 关闭当前窗口
- 下次开普通 PowerShell / cmd 即恢复默认环境

### 在这个旧工具集窗口里执行的推荐命令

进入新的 `cmd` 窗口后执行：

```cmd
conda activate 3dgs_app
python -m pip install setuptools==80.9.0 wheel "numpy<2" ninja
pip install --no-build-isolation git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```

### 如果提示 CUDA 架构错误

NVIDIA 官方 CUDA GPU 计算能力页显示：

- `GeForce RTX 4060` 的 Compute Capability 是 `8.9`

参考：

- https://developer.nvidia.com/cuda/gpus

如果 `tiny-cuda-nn` 编译阶段报架构相关错误，可以先显式设置：

```powershell
set TCNN_CUDA_ARCHITECTURES=89
```

然后重新执行：

```powershell
pip install git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```

## 7.4 安装 nerfstudio

在 `3dgs_app` 环境里执行：

```powershell
pip install nerfstudio
```

参考：

- https://docs.nerf.studio/quickstart/installation.html

如果你以后要调源码，也可以用官方给出的源码安装方式：

```powershell
git clone https://github.com/nerfstudio-project/nerfstudio.git
cd nerfstudio
pip install --upgrade pip setuptools
pip install -e .
```

但对当前项目的目标来说，先用 `pip install nerfstudio` 就够了。

### 7.4.1 Windows 上建议立即切换到 gsplat 官方预编译 wheel

如果直接从普通 PyPI 源安装 `nerfstudio`，`gsplat` 很可能会被装成“运行时再本地 JIT 编译 CUDA 扩展”的形态。  
在我们当前这台机器的组合里：

- `Windows`
- `Python 3.10`
- `torch 2.1.2+cu118`
- `CUDA Toolkit 11.8`

这会在第一次运行 `ns-train splatfacto` 时才暴露问题，常见报错类似：

```text
RuntimeError: Error building extension 'gsplat_cuda'
...dispatch_segmented_sort.cuh...
```

更稳的做法是直接安装 `gsplat` 官方提供的预编译 wheel：

```powershell
pip install --force-reinstall --no-deps gsplat==1.4.0 --index-url https://docs.gsplat.studio/whl/pt21cu118
```

说明：

- 这里的 `pt21cu118` 对应 `PyTorch 2.1 + CUDA 11.8`
- `--no-deps` 是为了只替换 `gsplat` 本体，不重新扰动你已经装好的 `torch / nerfstudio`
- 当前项目已验证这一步可以避免首次训练时在 Windows 上触发本地 CUDA 编译失败

安装后可用下面命令确认：

```powershell
python -c "import gsplat; print(gsplat.__version__)"
```

预期会看到类似：

```text
1.4.0+pt21cu118
```

## 8. 安装完成后的统一验收

在已经激活 `3dgs_app` 的前提下，依次执行：

```powershell
colmap -h
ffmpeg -version
python -c "import torch; print(torch.cuda.is_available())"
python -c "import gsplat; print(gsplat.__version__)"
python -c "import tinycudann as tcnn; print(hasattr(tcnn, 'Encoding')); print(hasattr(tcnn, 'NetworkWithInputEncoding'))"
ns-process-data --help
ns-train --help
ns-export --help
python -m trainer.pipeline --help
```

全部通过后，说明：

- `COLMAP` 可被训练脚本找到
- `FFmpeg` 可被训练脚本找到
- GPU 训练基础环境可用
- `gsplat` 已切换到与当前 `torch/cu118` 匹配的预编译 wheel
- `tiny-cuda-nn` 已成功装入当前 Conda 环境
- `nerfstudio` CLI 可用
- 项目里的训练模块可以直接运行

## 9. 与本项目的直接对应关系

安装完成后，本项目这条命令链才有机会跑通：

```powershell
ns-process-data video --data <input_video> --output-dir <processed_dir>
ns-train splatfacto --data <processed_dir>
ns-export gaussian-splat --load-config <config_yml> --output-dir <model_dir>
```

官方对应依据：

- `ns-process-data {video,images}` 用于处理自定义数据
- Video 数据类型要求 `COLMAP`
- `Splatfacto` 推荐从 COLMAP / `ns-process-data` 生成的数据初始化
- `ns-export gaussian-splat` 可导出 `.ply`

参考：

- https://docs.nerf.studio/quickstart/custom_dataset.html
- https://docs.nerf.studio/nerfology/methods/splat.html

## 10. 常见问题

### 10.1 只装 nerfstudio，不装 COLMAP，可以吗？

对我们当前这条“普通手机视频上传”的路线，不行。

因为 `ns-process-data video` 处理普通视频时需要 `COLMAP` 来恢复相机位姿。

例外情况是：

- Polycam
- Record3D
- KIRI Engine

这些输入方式自带位姿或已做过处理，可以跳过 `COLMAP`。但这不是我们当前 App 的主路线。

参考：

- https://docs.nerf.studio/quickstart/custom_dataset.html

### 10.2 为什么 `nvidia-smi` 显示 CUDA 13.2，文档却让我装 11.8？

因为当前项目需要遵循 nerfstudio 官方验证过的 PyTorch / CUDA 组合，而不是单纯追最新数字。

本项目优先目标是“先安装成功并跑通”，不是“把所有依赖都升到最新”。

### 10.3 为什么不建议把 nerfstudio 装进宿主机 Python？

因为宿主机 Python 现在是 `3.13.2`，而训练链依赖多、编译重、版本敏感度高。把训练链和业务后端混在同一个 Python 环境里，后续很容易爆版本冲突。

## 11. 推荐执行清单

建议按下面顺序逐项勾掉：

1. 下载并解压 COLMAP Windows 预编译包
2. 把 COLMAP 目录加入 `PATH`
3. 用 `colmap -h` 验证
4. 创建 Conda 环境 `3dgs_app`
5. 安装 PyTorch 2.1.2 + CUDA 11.8
6. 安装 `cuda-toolkit`
7. 在 VS 开发者命令行中安装 `tiny-cuda-nn`
8. 安装 `nerfstudio`
9. 立刻把 `gsplat` 替换成官方 `pt21cu118` 预编译 wheel
10. 用 `ns-process-data --help` / `ns-train --help` / `ns-export --help` 验证
11. 再回到项目里跑真实的训练链

## 12. 官方参考链接

- COLMAP 安装：https://colmap.github.io/install.html
- COLMAP 教程：https://colmap.github.io/tutorial.html
- Nerfstudio 安装：https://docs.nerf.studio/quickstart/installation.html
- Nerfstudio 自定义数据：https://docs.nerf.studio/quickstart/custom_dataset.html
- Splatfacto：https://docs.nerf.studio/nerfology/methods/splat.html
- gsplat wheel 索引：https://docs.gsplat.studio/whl/gsplat/
- Nerfstudio PyPI：https://pypi.org/project/nerfstudio/
- NVIDIA CUDA GPU Compute Capability：https://developer.nvidia.com/cuda/gpus
