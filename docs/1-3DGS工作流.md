# 3DGS 工作流

- COLMAP：相机位姿恢复、稀疏重建
- Splatfacto：训练 3DGS
- SplatTransform - 3D Gaussian Splat Converter：将 PLY 转换成 SOG
- PlayCanvas - Using the Engine API：查看器

## 相关文档：

- COLMAP 仓库：https://github.com/colmap/colmap
- COLMAP 教程：https://colmap.github.io/tutorial.html
- Playcanvas Docs：https://developer.playcanvas.com/user-manual/gaussian-splatting/
- Splatfacto：https://docs.nerf.studio/nerfology/methods/splat.html
- SplatTransform 仓库：https://github.com/playcanvas/splat-transform?tab=readme-ov-file#splattransform---3d-gaussian-splat-converter
- PlayCanvas - Using the Engine API：https://developer.playcanvas.com/user-manual/gaussian-splatting/building/your-first-app/engine/

----

# 开发方案

## 一、你的开发方案总览

你的当前方案是**合理的**，而且很适合学校项目的第一版：

- **前端客户端**：Flutter
- **后端 API**：FastAPI
- **数据库**：MySQL
- **文件存储**：先直接存后端服务器本地磁盘，不先上对象存储
- **3DGS 训练链**：COLMAP + Splatfacto + SplatTransform
- **查看器**：PlayCanvas Engine API
- **开发方式**：先全部在本地电脑上开发
- **备选部署**：AutoDL 作为临时 GPU 训练环境

这条线的优点是：**简单、便宜、能快速闭环**。
而且 Flutter 有成熟的相机和 WebView 插件；FastAPI 适合快速写 API，并自带很好的教程与自动文档生态；MySQL 8.4 仍是官方长期维护的主线版本之一。([Dart packages](https://pub.dev/packages/webview_flutter?utm_source=chatgpt.com))

------

## 二、你这个项目的完整系统架构

你不要把它理解成“一个 Flutter 项目”，而应该理解成**四层系统**：

### 1. Flutter 客户端

负责用户直接接触到的功能：

- 登录/注册
- 拍照 / 录视频
- 上传素材
- 查看训练进度
- 社区页面
- 作品详情页
- WebView 内嵌 3DGS viewer

Flutter 官方生态里，`webview_flutter` 提供 WebView 组件，在 iOS 背后用 `WKWebView`，在 Android 背后用系统 `WebView`。([Dart packages](https://pub.dev/packages/webview_flutter?utm_source=chatgpt.com))

### 2. FastAPI 后端

负责业务逻辑：

- 用户认证
- 素材上传
- 创建训练任务
- 查询任务状态
- 返回作品信息
- 点赞/评论/作品列表
- 向前端返回 viewer 地址

FastAPI 官方文档明确支持用 Python 直接构建 API，并且推荐先建立虚拟环境后安装。([FastAPI](https://fastapi.tiangolo.com/tutorial/?utm_source=chatgpt.com))

### 3. MySQL 数据库

负责结构化数据：

- 用户表
- 作品表
- 训练任务表
- 点赞评论表
- 文件路径表
- 权限表

MySQL 官方文档目前覆盖 8.4 主线版本，适合你这种常规业务数据库场景。([MySQL Developer Zone](https://dev.mysql.com/doc/en/?utm_source=chatgpt.com))

### 4. 本地训练链

负责 GPU 相关的 3DGS 处理：

- COLMAP：位姿恢复、稀疏重建
- Splatfacto：训练 Gaussian Splat
- SplatTransform：转换为发布格式
- PlayCanvas Viewer：最终展示

Splatfacto 官方文档明确说明它使用 `gsplat` 作为 Gaussian rasterization backend，并且相关 CUDA 代码会在第一次执行时编译；Nerfstudio 也推荐用 conda 管理依赖。([Nerf Studio](https://docs.nerf.studio/nerfology/methods/splat.html?utm_source=chatgpt.com))

------

## 三、你的项目工作流

我建议你把工作流写成这一版，最清楚：

### 业务工作流

1. 用户在 Flutter App 里拍摄物体或场景
2. Flutter 把图片/视频上传到 FastAPI
3. FastAPI 把文件保存到本地磁盘，并在 MySQL 里记录任务
4. FastAPI 触发本地训练任务
5. 本地训练任务执行：
   - COLMAP
   - Splatfacto
   - SplatTransform
6. 训练结果保存到本地目录
7. FastAPI 更新数据库中的任务状态
8. Flutter 轮询或刷新任务状态
9. 用户在作品页通过 WebView 打开 PlayCanvas viewer 查看结果

------

## 四、你现在最适合的“完整开发环境”

下面这部分最重要，我按**你电脑上要装什么**来列。

### A. 基础开发环境

这是你日常写代码一定会用到的：

- **VS Code**
  你已经比较熟，继续用最合适。
- **Git**
  用来管理代码版本。
- **Chrome**
  调试 PlayCanvas viewer 和 FastAPI 文档页都方便。

------

### B. Flutter 开发环境

你选 Flutter 后，客户端开发环境就是：

- **Flutter SDK**
- **Dart SDK**（随 Flutter 一起）
- **Android Studio**
  - 主要是为了 Android SDK、模拟器、adb
- **Android SDK / Platform Tools**
- **Flutter 插件（VS Code）**
- **Dart 插件（VS Code）**

#### Flutter 侧建议用的插件/包

第一版先用这些就够了：

- `camera`
  用于拍照/录像
- `webview_flutter`
  用于内嵌 viewer
- `dio`
  用于上传文件、请求接口
- `go_router` 或先直接用基础 Navigator
- `provider` / `riverpod`
  状态管理二选一，第一版用 `provider` 更轻

`webview_flutter` 是官方 Flutter 插件生态里提供的 WebView 组件。([Dart packages](https://pub.dev/packages/webview_flutter?utm_source=chatgpt.com))

------

### C. FastAPI 开发环境

后端建议全部走 Python 这条线。

你电脑上装：

- **Python 3**
- **uv** 或 **pip + venv**
  - 你如果想简单，先用 `venv`
- **FastAPI**
- **Uvicorn**
- **SQLAlchemy**
- **Alembic**
- **Pydantic**
- **python-multipart**
  - 处理文件上传
- **PyMySQL** 或 `mysqlclient`
  - 连接 MySQL
- **passlib[bcrypt]**
  - 密码哈希
- **python-jose`
  - JWT 登录令牌

#### FastAPI 目录建议

```text
backend/
  app/
    main.py
    api/
    models/
    schemas/
    services/
    db/
    core/
    tasks/
  requirements.txt
```

FastAPI 官方教程就是从 `FastAPI()` 实例和路由开始构建。([FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/?utm_source=chatgpt.com))

------

### D. MySQL 开发环境

你现在说数据库选 MySQL，那本地建议装：

- **MySQL Server 8.4**
- **MySQL Workbench**
  用图形界面看表、写 SQL、查数据更方便

不过要注意一个现实点：
官方文档说明 Workbench 是以 MySQL 8.0 测试开发的，虽然可以连接 8.4+，但个别功能可能不完全同步。对你这个项目影响一般不大。([MySQL Developer Zone](https://dev.mysql.com/doc/refman/8.2/en/workbench.html?utm_source=chatgpt.com))

#### MySQL 在你项目里存什么

- 用户信息
- 作品元数据
- 文件路径
- 训练状态
- 社区互动数据

#### 不存什么

- 原始图片本体
- 视频文件
- splat 文件本体

这些先直接存在本地磁盘，数据库里只存路径。

------

### E. 本地文件存储方案

你现在暂时不做对象存储，这很合理。

我建议你本地先约定一个清晰目录：

```text
project_root/
  storage/
    uploads/
      user_001/
        task_001/
          images/
          video/
    outputs/
      task_001/
        colmap/
        splat/
        viewer/
    covers/
```

这样好处是：

- 调试简单
- 改路径容易
- 以后迁移到对象存储时，也能直接按这个目录映射

#### 数据库存什么

例如作品表里存：

- `raw_input_path`
- `output_ply_path`
- `output_sog_path`
- `cover_image_path`

------

### F. 3DGS 训练环境

这是最容易把环境搞乱的部分，所以建议你**单独做一个 conda 环境**。

你电脑上需要：

- **Miniconda / Anaconda**
- **COLMAP**
- **nerfstudio**
- **gsplat**
- **SplatTransform**
- **FFmpeg**
  - 如果你要支持“上传视频后自动抽帧”
- **NVIDIA 驱动**
- **CUDA 可用环境**

Nerfstudio 官方推荐用 conda 管理依赖；custom data 文档里也直接提到 COLMAP 和 FFmpeg。([Nerf Studio](https://docs.nerf.studio/quickstart/installation.html?utm_source=chatgpt.com))

#### 训练环境建议单独隔离

比如：

```text
conda create -n gsplat python=3.10
conda activate gsplat
```

把以下东西都装在这个环境里：

- `nerfstudio`
- `gsplat`
- `torch`
- 训练脚本依赖

#### 为什么要单独隔离

因为这套和你的 FastAPI 业务依赖不是一类东西。
你把业务后端和训练后端混在一个 Python 环境里，后面很容易炸版本。

------

### G. PlayCanvas Viewer 环境

这部分其实不复杂。

你需要：

- 一个单独的前端目录，放 viewer 页面
- PlayCanvas Engine API 示例代码
- 本地静态服务器

建议结构：

```text
viewer/
  index.html
  main.js
  assets/
```

你可以用最简单的静态服务跑它，比如：

- Python `http.server`
- Node 的静态服务器
- 或者以后让 FastAPI 直接托管静态文件

PlayCanvas 这部分本质是网页，不需要你额外上复杂前端框架。

------

## 五、你电脑上的“完整软件清单”

下面这份最接近“装机清单”。

### 必装

- VS Code
- Git
- Chrome
- Python 3
- Flutter SDK
- Android Studio
- MySQL Server
- MySQL Workbench
- Miniconda
- FFmpeg
- NVIDIA 显卡驱动

### 训练相关

- COLMAP
- nerfstudio
- gsplat
- SplatTransform

### VS Code 插件建议

- Flutter
- Dart
- Python
- Pylance
- GitLens
- MySQL 或 SQLTools
- REST Client（可选）

------

## 六、你的项目代码应该怎么分仓库/分目录

你现在一个人做，**不用拆很多仓库**，先一个大项目就行。

建议结构：

```text
project/
  mobile_app/        # Flutter
  backend/           # FastAPI
  viewer/            # PlayCanvas viewer
  trainer/           # 训练脚本、任务脚本
  storage/           # 本地文件
  docs/              # 设计文档
```

### 各目录职责

#### `mobile_app/`

Flutter 客户端代码

#### `backend/`

FastAPI 接口、数据库、业务逻辑

#### `trainer/`

训练流水线脚本，例如：

- `run_colmap.py`
- `run_splatfacto.py`
- `run_transform.py`
- `pipeline.py`

#### `viewer/`

PlayCanvas viewer 页面

#### `storage/`

本地上传文件和产物

------

### 七、你本地开发时的运行方式

我建议你一开始就固定成这个模式：

#### 1. 启动 MySQL

本地数据库先开着。

#### 2. 启动 FastAPI

比如运行在：

- `http://127.0.0.1:8000`

FastAPI 默认会生成接口文档页，调试很方便。([FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/?utm_source=chatgpt.com))

#### 3. 启动 Viewer 静态页

比如运行在：

- `http://127.0.0.1:8080`

#### 4. Flutter 连本地 API

真机调试时要注意：

- Android 模拟器访问宿主机常用 `10.0.2.2`
- 真机要用你电脑局域网 IP

#### 5. 训练先用后台脚本触发

先别一上来就做复杂消息队列。
第一版可以直接让 FastAPI 收到任务后：

- 写数据库
- 调一个后台线程/子进程
- 执行 `trainer/pipeline.py`

------

## 八、AutoDL 作为备选方案时，怎么接进来

你现在先不部署，但要提前留好迁移位。

### 你现在本地开发时，就要做到这几点

#### 1. 训练逻辑和 FastAPI 解耦

不要把训练代码直接写进接口函数里。
而是写成独立脚本：

- `trainer/pipeline.py`
- 输入：任务 ID、输入目录
- 输出：产物目录、状态结果

这样以后迁到 AutoDL，只是把“本地执行脚本”改成“远程执行脚本”。

#### 2. 文件路径不要写死

统一从配置文件读，比如：

- `UPLOAD_ROOT`
- `OUTPUT_ROOT`

#### 3. 配置用 `.env`

你以后换到 AutoDL 或其他机器时，只改环境变量，不改代码。

#### 4. 训练环境单独记录

保留一份：

- `environment.yml`
- `requirements.txt`
- 安装步骤文档

Nerfstudio 官方本身就推荐 conda，这很适合你后续迁到另一台 GPU 机器。([Nerf Studio](https://docs.nerf.studio/quickstart/installation.html?utm_source=chatgpt.com))

------

## 九、你的第一版开发顺序

别全开工，按这个顺序最稳：

### 第 1 步：Flutter 空壳

先做：

- 首页
- 上传页
- 作品页
- 查看页（WebView）

### 第 2 步：FastAPI 基础接口

先做：

- 注册/登录
- 上传文件
- 创建任务
- 查询任务状态
- 获取作品详情

### 第 3 步：MySQL 表结构

先建：

- users
- tasks
- works
- likes
- comments

### 第 4 步：本地文件存储打通

确保上传文件能真正存到本地目录。

### 第 5 步：手动跑通训练链

先不要接自动化。
你手动拿一组图片跑：

- COLMAP
- Splatfacto
- SplatTransform

确保能产出 viewer 能看的结果。

### 第 6 步：FastAPI 接训练脚本

让 API 创建任务后，自动调用训练脚本。

### 第 7 步：Flutter 查看结果

训练完成后，在作品页 WebView 打开 viewer。





我准备开发一款安卓端的APP，APP是一个类似闲鱼的二手市场交易平台，我的创新点是引入 3D 商品模型，使用 3DGS 技术帮助用户录入商品、生成模型，并在商品页面展示 3D 模型效果。
我的开发方案：前端使用 Flutter，后端使用 FastAPI，数据库使用 MySQL，暂时不使用对象存储而是存储到后端服务器（也就是开发阶段的本地电脑）上。详细的内容请看我上传的文档。
下面是 3DGS 工具链的设计：

1. 首先用户需要拍摄一组图片，或录制一段视频，视频会被处理成一个视频帧序列，上传到服务器进行处理
2. 使用 COLMAP 对用户上传的图片或视频帧进行 SfM 处理，得到相机位姿和系数点云，作为 3DGS 的初始化。COLMAP 的相关文档：
   - COLMAP 仓库：https://github.com/colmap/colmap
   - COLMAP 教程：https://colmap.github.io/tutorial.html
3. 使用 Splatfacto 进行 3DGS 训练。Splatfacto 的相关文档：
   - Splatfacto：https://docs.nerf.studio/nerfology/methods/splat.html
4. 使用 SplatTransform - 3D Gaussian Splat Converter 将 PLY 转换成 SOG，这步是可选的，可以暂时先不实现，后续再补上。相关文档：
   - SplatTransform 仓库：https://github.com/playcanvas/splat-transform?tab=readme-ov-file#splattransform---3d-gaussian-splat-converter
5. 将 3DGS 模型（PLY 或 SOG）传到用户设备，使用 PlayCanvas - Using the Engine API 作为查看器在用户手机上渲染。相关文档：
   - PlayCanvas - Using the Engine API：https://developer.playcanvas.com/user-manual/gaussian-splatting/building/your-first-app/engine/

现在，请你帮我梳理一下完整的开发方案，进行完善和优化写一篇文档