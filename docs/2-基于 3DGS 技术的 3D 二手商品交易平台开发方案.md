# 基于 3DGS 技术的 3D 二手商品交易平台开发方案

## 一、 项目核心愿景与架构总览

本项目旨在开发一款类似“闲鱼”的 Android 二手交易 APP。核心创新点在于：**卖家只需环绕商品拍摄一段视频，系统即可自动生成高保真的 3D 交互模型，并在商品详情页供买家 360° 自由查看。**

### 1.1 技术栈选型
- **前端客户端**：Flutter（跨平台，首发 Android，包含完整的相机、相册、WebView 交互机制）。
- **后端 API**：FastAPI（Python 异步框架，极速响应，原生契合 AI/3D 处理脚本）。
- **数据库**：MySQL 8.4（存储用户、商品、订单、训练任务详情）。
- **文件与存储**：本地磁盘存储（分为 `uploads/` 原始视频源 和 `outputs/` 3D模型产物）。
- **3DGS 训练链**：FFmpeg (抽帧) -> COLMAP (位姿) -> Splatfacto (训练) -> SplatTransform (压缩) -> PlayCanvas (渲染)。

### 1.2 3DGS 工具链的核心工具及其官方文档链接

#### 1. COLMAP（相机位姿恢复与稀疏重建）
用于对用户上传的视频抽帧图像进行 SfM（Structure-from-Motion）处理，计算相机位姿并生成稀疏点云，为 3DGS 提供初始化数据。
*   **开源仓库**：https://github.com/colmap/colmap
*   **官方教程**：https://colmap.github.io/tutorial.html

#### 2. Splatfacto / Nerfstudio（3DGS 模型训练）
基于 COLMAP 提取的数据，进行 3D Gaussian Splatting 的核心训练过程，最终输出基础的 `.ply` 格式 3D 模型。
*   **官方文档**：https://docs.nerf.studio/nerfology/methods/splat.html

#### 3. SplatTransform（模型格式转换与压缩）
将体积庞大的 `.ply` 文件转换为针对移动端和 Web 端优化的 `.sog` 或 `.splat` 格式，大幅缩减文件体积，提升手机端加载速度（阶段四优化项）。
*   **开源仓库**：https://github.com/playcanvas/splat-transform?tab=readme-ov-file#splattransform---3d-gaussian-splat-converter

#### 4. PlayCanvas Engine API（移动端 3D 模型渲染查看）
轻量级的 WebGL 引擎，用于编写网页端 3D 渲染器，配合 Flutter 的 `webview_flutter` 插件，在 App 内实现商品 3D 模型的流畅交互浏览。
*   **3DGS 引擎 API 开发文档**：https://developer.playcanvas.com/user-manual/gaussian-splatting/building/your-first-app/engine/
*   **PlayCanvas 3DGS 综合手册**：https://developer.playcanvas.com/user-manual/gaussian-splatting/

#### 5. FFmpeg

工作流第一步必备的工具，用于将卖家上传的商品视频按指定帧率（如 2~3 fps）抽帧为连续图片供 COLMAP 使用。

*   **官网链接**：https://ffmpeg.org/documentation.html
*   **开源仓库**：https://github.com/ffmpeg/ffmpeg

---

## 二、 核心业务与技术工作流设计

为了保证移动端体验和后端服务器不被撑爆，我们将整个 3DGS 生成过程设计为**异步解耦**的架构。

### 2.1 卖家发布商品工作流（APP 端 -> 服务端）
1. **素材采集**：卖家在 Flutter APP 内填写商品基础信息（名称、价格、描述），并直接调用相机**环绕商品录制一段 15~30 秒的视频**（比单拍几十张照片上传更稳健，不易丢包）。
2. **切片上传**：Flutter 将视频文件和商品图文数据上传给 FastAPI。
3. **入库与排队**：FastAPI 在 MySQL `goods` 表创建商品记录（状态为“3D模型生成中”），并在 `tasks` 表创建一条训练任务，随后向客户端返回“发布成功”。
4. **后台工作节点接单**：后端独立的 Python Worker 轮询 `tasks` 表，发现新任务后开始流水线作业。

### 2.2 3DGS 自动化训练流水线（服务端 Worker）
为了防止 FastAPI 业务阻塞，这部分代码应独立为 `trainer_worker.py`：
1. **FFmpeg 抽帧**：从上传的视频中按 `2~3 fps` 提取图像序列，通常提取 50-100 张高质量图片。
2. **COLMAP 稀疏重建**：自动执行特征提取、匹配和 Bundle Adjustment，生成相机位姿和稀疏点云 (`cameras.txt`, `images.txt`, `points3D.txt`)。
3. **Splatfacto 训练**：调用 nerfstudio 的 splatfacto 算法，基于 COLMAP 输出进行 3DGS 训练，大约需要 10-20 分钟（取决于 GPU），产出标准 `.ply` 文件。
4. **SplatTransform 模型转化（优化期引入）**：将几百 MB 的 `.ply` 文件压缩转换为面向 Web/Mobile 优化的 `.sog` 或 `.splat` 格式，大幅减小体积。
5. **状态回写**：生成完毕，更新 MySQL 数据库中该商品的状态为“展示中”，并记录模型文件路径。

### 2.3 买家浏览工作流（APP 端）
1. 买家在首页看到商品列表，带有“3D”角标的商品具有 3D 浏览能力。
2. 进入商品详情页，默认展示封面图。点击“查看 3D 细节”按钮。
3. Flutter 弹出 `webview_flutter`，加载部署在后端的 PlayCanvas Engine API 静态网页。
4. 网页通过 URL 参数拉取对应的 `.ply` 或 `.sog` 模型，在手机端通过 WebGL 进行高帧率渲染，买家可拖拽、缩放查看。

---

## 三、 数据库表结构设计（针对电商+3DGS）

除了常规的用户表，核心在于将**商品**和**3D生成任务**解耦。

1. **`users` (用户表)**：ID、昵称、头像、手机号、密码哈希等。
2. **`goods` (商品表)**：
   - `id`, `user_id`, `title`, `description`, `price`
   - `cover_image` (封面图路径)
   - `video_path` (用户上传的原始视频路径)
   - `model_path` (生成的 PLY/SOG 模型路径)
   - `status` (状态：0-生成中, 1-在售, 2-已售出)
3. **`tasks` (3D重建任务表)**：
   - `id`, `goods_id`
   - `status` (状态：pending, extracting, colmap, splatting, completed, failed)
   - `progress` (进度百分比，供前端查询展示)
   - `error_message` (失败原因)
   - `created_at`, `updated_at`
4. **`orders` / `messages` (订单与留言表)**：常规二手交易必须模块。

---

## 四、 本地开发环境与目录结构（Mono-Repo）

开发阶段全部放在一个主目录下，方便前后端和训练脚本调试。

```text
3DGS_Marketplace/
├── mobile_app/             # Flutter 客户端源码
│   ├── lib/
│   ├── pubspec.yaml
│   └── ...
├── backend/                # FastAPI 业务后端逻辑
│   ├── main.py
│   ├── api/                # 路由接口 (users, goods, tasks)
│   ├── models/             # SQLAlchemy 数据模型
│   ├── database.py         # MySQL 连接
│   └── requirements.txt
├── trainer/                # 3DGS 自动化后台处理脚本 (重要!)
│   ├── worker.py           # 轮询数据库任务并执行流水线
│   ├── pipeline.py         # 串联 FFmpeg -> COLMAP -> Splatfacto
│   └── environment.yml     # 独立的 Conda 环境配置
├── viewer/                 # PlayCanvas 静态展示页面
│   ├── index.html
│   ├── viewer.js           # 封装 PlayCanvas Engine API
│   └── style.css
└── storage/                # 本地模拟对象存储
    ├── uploads/            # 原始视频 (如 /uploads/goods_123.mp4)
    ├── frames/             # FFmpeg 抽帧缓存
    └── models/             # 生成的 PLY/SOG 模型 (如 /models/goods_123.sog)
```

---

## 五、 四阶段落地开发计划

不要一上来就追求完美，按以下顺序能最快看到成果。

### 阶段一：打通跑道（跑通全栈极简版）
1. **环境搭建**：配置好 Flutter 环境，FastAPI 虚拟环境，并为 `nerfstudio` 建立独立的 Conda 虚拟环境。
2. **基础业务 API**：用 FastAPI 配合 MySQL 写出商品发布（接受传视频并落盘）、获取商品列表的接口。
3. **Flutter 界面**：做极简的首页列表和商品发布页。
4. **手动训练测试**：不写自动化脚本，拿一部手机拍一段视频，手动用命令行跑 FFmpeg -> COLMAP -> Splatfacto，拿到 `.ply` 文件。

### 阶段二：3D 查看器嵌入（惊艳呈现）
1. **构建 Viewer**：使用 PlayCanvas Engine API 编写 `index.html`，能够读取本地的 `.ply` 文件并渲染。
2. **FastAPI 静态挂载**：在 FastAPI 中挂载 `/viewer` 和 `/storage/models` 静态目录，使得通过 `http://127.0.0.1:8000/viewer/index.html?model=goods_123.ply` 能够直接看 3D 模型。
3. **Flutter 引入 WebView**：在商品详情页嵌入 `webview_flutter` 插件，加载上述 URL，在 Android 模拟器/真机上跑通 3D 交互体验。

### 阶段三：自动化流水线（解放双手）
1. **编写 Worker 脚本**：在 `trainer/` 目录下编写 Python 脚本，轮询数据库的 `tasks` 表。
2. **自动化 Pipeline**：用 Python 的 `subprocess` 模块，按顺序调用抽帧、COLMAP 和 Splatfacto 命令。
3. **状态同步**：Worker 跑完后自动把生成的模型拷贝到 `storage/models`，并将 MySQL 中商品的 `status` 改为在售。
4. **Flutter 端联动**：App 详情页显示“模型正在生成中（例如 30%）”，生成完毕后自动变为 3D 浏览视图。

### 阶段四：性能优化与格式压缩（准备上线必备）
1. **引入 SplatTransform**：把 `.ply` 动辄百兆的体积，通过 SplatTransform 转化为体积更小的 `.sog` 格式，大幅降低手机端下载和加载时间。
2. **PlayCanvas 解析更新**：修改 Viewer 代码，使其支持拉取并解析 `.sog` 文件。
3. **前端体验打磨**：加上加载 3D 模型的进度条、增加买家留言系统、优化 UI。

---

## 六、开发过程中的避坑与优化建议

### 1. 为什么建议传视频而不是图片？
- **网络稳定性**：Android App 如果一次性上传 100 张高清图片，容易因为网络抖动导致部分失败。传一个压缩后的 H.264 视频（大概十几MB），上传稳定性极高。
- **质量可控**：服务端通过 `ffmpeg -i input.mp4 -vf fps=2 frames/%04d.jpg` 抽帧，能保证帧与帧之间的连续性，有助于 COLMAP 更好地提取特征。

### 2. 避免 FastAPI 被阻塞
FastAPI 虽然支持 `BackgroundTasks`，但 3DGS 训练需要大量显存并耗时极长。
**强烈建议：** FastAPI 只负责把任务插入数据库；另外开一个终端窗口运行单纯的 `python trainer/worker.py` 去执行训练流程。这样即使训练报错崩溃，也不会影响你的 web 接口服务。

### 3. Android 端的网络配置
如果你在 Android 模拟器测试，请求本地 FastAPI 时，URL 必须使用 `http://10.0.2.2:8000` 而不是 `127.0.0.1`。
如果是真机调试，确保手机和电脑在同一个 WiFi 下，使用电脑的局域网 IP（如 `192.168.1.100`），并确保电脑防火墙放行 8000 端口。

### 4. GPU 显存控制
Splatfacto 训练如果遇到 OOM（Out of Memory），可以降低分辨率：
- 在调用 `ns-train splatfacto` 时，加入 `--pipeline.datamanager.camera-optimizer.mode off` 或通过设定参数将训练时的图像分辨率 downscale。二手商品不需要做到微距级精度，保证整体结构和纹理即可。

### 5. PlayCanvas 性能优化
移动端的 WebGL 性能受限。当你在 App 的 WebView 中加载 3DGS 时：
- 确保禁用不需要的阴影或复杂的后处理抗锯齿。
- 设定相机的最大和最小缩放距离，防止买家把镜头拉进模型内部产生穿模破绽。