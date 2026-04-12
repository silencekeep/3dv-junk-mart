# Viewer 解决方案与优化方向

本文总结当前 3DGS 商品查看器的实现方案，并记录后续可以继续提升体验的方向。

## 1. 当前目标

当前 Viewer 的目标不是做完整编辑器，而是在移动端商品详情页里提供一个可用的 3DGS 查看入口：

- Flutter 端通过 WebView 打开查看器页面。
- 后端返回 `viewer_url`，并把模型地址和展示参数带到 URL 查询参数中。
- Web 查看器使用 PlayCanvas 加载 `PLY` 格式的 Gaussian Splat 模型。
- 一期优先保证可查看、可旋转、可缩放、可平移，后续再优化压缩、自动摆正和商品化展示体验。

## 2. 当前实现

### 2.1 整体链路

当前链路如下：

```text
FastAPI 任务接口
  -> 返回 viewer_url
  -> Flutter WebView 打开 /viewer/index.html
  -> viewer.js 加载 model 参数指向的 PLY
  -> PlayCanvas gsplat 组件渲染模型
```

相关文件：

- `backend/app/routes/reconstructions.py`：组装 `viewer_url`，读取每个模型目录下的 `viewer.json`。
- `mobile_app/lib/src/pages/viewer_page.dart`：WebView 容器，关闭网页缩放并保留本地缓存。
- `viewer/index.html`：查看器页面入口。
- `viewer/style.css`：禁用页面滚动、缩放、边缘拉扯等浏览器默认触摸行为。
- `viewer/viewer.js`：PlayCanvas 初始化、模型加载和手势控制。

### 2.2 手势控制

当前使用单模式 `OrbitControls`。双模式 `Orbit / Fly` 的尝试会让模式状态和相机姿态之间出现同步问题，并导致触摸后视角跳变，因此不再作为当前实现继续保留。

当前手势定义：

- 单指拖动：围绕当前焦点做 Orbit 旋转，内部使用 `azim / elevation`，相机 roll 固定为 0。
- 双指同向移动：平移视角。
- 双指捏合：缩放视角。
- 双指顺时针 / 逆时针扭转：绕当前视线轴旋转视角。
- 双击或点击“重置视角”：恢复初始视角。
- 点击“设置初始视角”：重置到当前初始视角后进入单指 Orbit 调整模式，确认后保存为该模型后续打开和重置视角使用的默认相机视角。
- 点击“动画展示”：进入播放模式，底部显示 Play / Pause 和 360° 环绕进度条；播放时相机沿水平 Orbit 自动环绕，触摸操作会暂停并保留断点。
- 桌面端鼠标滚轮：缩放。
- 桌面端右键 / 中键拖动：平移。

这个方案的目标是先保证内部状态简单、手势不会突然切换模式，也不会因为 `Fly / Orbit` 状态残留导致下一次触摸瞬移。单指旋转已从自由 arcball 调整为接近 SuperSplat Orbit Mode 的 `azim / elevation + focal point + distance` 模式；只要用户没有双指平移焦点，相机会始终围绕校准后的模型中心旋转并保持正对焦点。双指扭转保留为显式 roll 操作，重置视角会恢复默认 roll。

### 2.3 坐标系校准模式

当前 Viewer 已加入最小版“校准坐标”模式，使用 PlayCanvas Engine 原生 `RotateGizmo` / `TranslateGizmo` 调整 `ModelRoot`，而不是修改相机控制器。

当前行为：

- 点击“校准坐标”：进入校准模式，默认显示红 / 绿 / 蓝旋转环，可在“旋转”和“移动”之间切换，两个工具互斥。
- 校准模式下：额外显示世界参考坐标，红色为 X 轴，蓝色为 Z 轴，浅灰色 XZ 密集网格为世界水平面；不再绘制独立绿色 Y 轴，Y 方向由 `RotateGizmo` 的绿色旋转环表达。
- 校准模式下：旋转环和移动箭头沿用 PlayCanvas / SuperSplat 风格的屏幕固定大小；水平面网格使用固定世界间距，每 10 * 10 个小格使用一条亮白主线；中心网格线跳过，由红 / 蓝坐标轴替代，避免坐标轴中间叠白线。
- 校准模式下：`RotateGizmo` 和 `TranslateGizmo` 使用 `world` 坐标空间，红 / 绿 / 蓝旋转环或移动箭头分别与世界 X / Y / Z 轴对齐，避免参考轴和操作组件颜色错位。
- 校准模式下：网格已经从 WebGL 原生线段改成细矩形 mesh 条带，小格间距调整为 `0.35`，坐标轴宽度降为 `0.018`，同时 Viewer 打开 WebGL 抗锯齿并把 canvas DPR 上限设为 2，降低移动端 WebView 中的锯齿感。
- 校准模式下：网格范围为 `24` 世界单位半径，使用 mesh 条带绘制固定世界间距网格、X / Z 坐标轴，并按 `Calibration Reference -> Product Splat -> Gizmo overlay` 的顺序渲染；当前版本基于 `20260407_21` 的自然遮挡状态，移除了独立绿色 Y 轴，以避免 Y 轴实体与水平网格相交导致局部网格线变绿。
- 当前网格仍是“大范围固定网格”的近似，极端移动时仍可能看到边界；如果后续需要真正数学意义上的无限网格，应改为专用 grid shader。
- 校准模式下：空白处仍可正常移动视角；只有按住红 / 绿 / 蓝旋转环或移动箭头时，普通相机手势才会临时禁用，避免和坐标系调整互相抢输入。
- 点击“保存校准”：把当前 `ModelRoot` 的欧拉角和平移写回 `storage/models/<task_id>/viewer.json` 的 `model_rotation_deg` / `model_translation`。
- 点击“撤销”：恢复进入校准模式前的模型旋转和平移，并退出校准模式。
- 点击“退出校准”：只退出校准模式，不写文件；当前页面内的临时旋转和平移仍保留，刷新后会回到上次保存的校准。

这套方案刻意只做“展示姿态修正”，不改训练产物、不重写 PLY，也不改变普通查看手势。它的目标是先让每个商品可以人工摆正，降低模型坐标系歪斜对浏览体验的影响。

### 2.4 WebView 与浏览器手势处理

之前出现过双指缩放时页面文字也一起缩放、边缘被系统拉扯的问题。现在通过几层处理避免冲突：

- Flutter WebView 调用 `enableZoom(false)`，关闭网页级缩放。
- Flutter WebView 使用 `EagerGestureRecognizer`，让 WebView 优先接收触摸事件。
- 查看器页面设置 `maximum-scale=1.0` 和 `user-scalable=no`。
- CSS 设置 `touch-action: none`、`overscroll-behavior: none`、`overflow: hidden`。
- `viewer.js` 里拦截 `touchstart`、`touchmove` 和 Safari 风格的 `gesture*` 事件。

### 2.5 展示姿态修正

3DGS 训练结果不一定天然符合商品展示坐标系。当前没有直接修改训练产物，而是在 Viewer 层给模型加了一个 `ModelRoot` 父节点，用它来承载展示修正。

每个模型目录可以放一个 `viewer.json`：

```json
{
  "model_rotation_deg": [0, 0, 0],
  "model_translation": [0, 0, 0],
  "model_scale": 1.0,
  "camera_rotation_deg": [-18, 26, 0],
  "camera_distance": 1.6
}
```

字段含义：

- `model_rotation_deg`：模型根节点的欧拉角旋转修正。
- `model_translation`：模型根节点的平移修正。
- `model_scale`：模型根节点的统一缩放。
- `camera_rotation_deg`：默认相机视角。
- `camera_distance`：默认相机距离。

这种方式的优点是不用重训，也不用修改 PLY 文件。Viewer 内的校准工具和初始视角设置只要写回 `viewer.json`，商品详情页就会使用新的展示姿态和默认相机视角。

## 3. 当前已解决的问题

- 移动端 WebView 双指缩放会缩放整页的问题已处理。
- 页面边缘拉扯、滚动、浏览器默认手势抢输入的问题已处理。
- 单指旋转灵敏度过低的问题已处理。
- 双指平移、缩放容易误触旋转的问题已初步缓解。
- 双模式控制器导致触摸后视角跳变的问题，已通过保留单模式 Orbit 控制规避。
- 模型坐标系歪斜导致固定世界轴 orbit 旋转混乱的问题，当前通过 `viewer.json` 展示姿态修正和 `azim / elevation` Orbit 控制缓解。
- 查看器静态资源缓存导致旧逻辑不生效的问题，已通过 `viewer_build` 处理；模型重复加载问题已通过 WebView 保留缓存、后端缓存头和 Viewer IndexedDB 显式模型缓存处理。
- 已提供 `/viewer/cache.html` 和 `window.viewerModelCache` 作为本地模型缓存管理接口，并已在发布首页和已生成模型列表页提供临时入口；后续可迁入 App 用户设置页。
- 已支持每个模型独立展示姿态配置 `viewer.json`，并可在 Viewer 内保存旋转和平移校准。
- 已支持在 Viewer 内设置模型初始视角，保存后会写回 `camera_rotation_deg` / `camera_distance` 并作为后续打开和重置视角使用的默认相机视角。
- 已支持动画展示模式：基于重置视角进行 360° 水平自动环绕，支持 Play / Pause、断点继续和用户操作自动暂停。

## 4. 当前局限

- 当前还不是完整 SuperSplat 风格的 Orbit 控制：双击仍是重置视角，而不是 `Set Focus`。
- 校准模式目前支持旋转和平移，不支持缩放。
- `RotateGizmo` / `TranslateGizmo` 是 PlayCanvas Engine 原生 gizmo，不是完整 SuperSplat 编辑器；复杂编辑能力后续需要单独实现。
- 双指平移、缩放、扭转同时存在，复杂手势下仍可能有轻微耦合。
- `viewer.json` 的缩放等高级字段目前仍需要手动调整。
- PLY 体积可能较大，移动端加载速度和内存占用还有优化空间。
- Viewer 目前没有按设备性能动态调参，例如点数裁剪、低清模式、渐进加载。
- 当前仍是 WebView + WebGL 路线，性能和手势系统受浏览器内核影响。

## 5. 后续优化方案

### 5.1 短期优化

优先做交互和调参类优化，成本低、收益直接：

- 继续对齐 SuperSplat Touch Orbit：补充双击 Set Focus。
- 增加灵敏度参数：旋转、平移、缩放、扭转分别可调，便于针对真机手感微调。
- 增加“一键回正”和“前 / 后 / 左 / 右 / 顶部”快捷视角。
- 在 Viewer HUD 中显示当前是否处于旋转、平移、缩放或扭转状态，方便调试。
- 把 `viewer_build` 版本集中到一个常量或配置文件，避免多处手动同步。

### 5.2 中期优化

重点解决“商品展示坐标系”和“模型加载性能”：

- 扩展姿态校准：在当前 `RotateGizmo` / `TranslateGizmo` 的基础上补充缩放和数值输入，统一写回 `storage/models/<task_id>/viewer.json`。
- 增加半自动摆正：基于点云包围盒或 PCA 主轴估算模型方向，再由用户微调。
- 增加桌面 / 支撑平面检测：如果商品放在桌面上，可以尝试估计桌面法线作为展示 `up`。
- 生成缩略图：任务完成后渲染一张预览图，用于已训练模型列表。
- 加入 SOG 或其他压缩格式：降低移动端传输体积，提高首次加载速度。

### 5.3 长期优化

长期可以把 Viewer 从“能看”升级成“商品展示体验”：

- 建立标准商品坐标系：为每个模型保存 `front / up / right`，商品详情页默认使用稳定转台视角。
- 引入模型质量评估：根据点云稀疏度、重建范围、背景噪声给出“可发布 / 建议重拍”的提示。
- 自动背景裁剪：减少桌面、键盘、手部等背景内容对商品查看的干扰。
- 做渐进式加载：先加载低精度模型或缩略预览，再替换成完整模型。
- 做移动端性能分级：根据设备能力选择不同模型质量、渲染分辨率或压缩格式。
- 评估原生渲染方案：如果 WebView 性能或手势限制明显，可以探索 Flutter 原生纹理、Unity、Filament 或独立原生 3DGS viewer。

## 6. 推荐下一步

建议按这个顺序推进：

1. 不再继续扩展当前失败的 `Orbit / Fly` 双模式方案。
2. 继续对齐 SuperSplat Touch Orbit：补充双击 Set Focus。
3. 在现有旋转 / 平移校准基础上，补充数值输入和缩放校准。
4. 对导出的 PLY 引入 SOG 压缩或等效压缩方案，改善手机加载速度。
