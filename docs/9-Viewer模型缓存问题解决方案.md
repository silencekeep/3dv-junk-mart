# Viewer 模型缓存问题解决方案

本文记录移动端 Viewer 中 `正在加载资源...` 时间过长的问题、根因判断和当前采用的缓存方案。

## 1. 问题现象

- 同一个 ready 任务重复进入 Viewer，仍然在 `正在加载资源...` 阶段等待较久。
- 后端日志可以看到 `/storage/models/<task_id>/model.ply` 被请求，当前测试模型约 `46 MB`。
- 移动端用户感知上像是“每次都重新加载模型”，即使之前已经进入过同一个 Viewer。

## 2. 根因

### 2.1 Flutter WebView 主动清空缓存

早期 `mobile_app/lib/src/pages/viewer_page.dart` 每次打开 Viewer 都执行：

```dart
await _controller.clearCache();
await _controller.clearLocalStorage();
```

同时还会给 Viewer 页面追加 `ts=DateTime.now().millisecondsSinceEpoch`。这会导致 WebView HTTP 缓存和本地存储没有复用机会。

当前已移除这两处逻辑，只保留稳定的 `viewer_build` 参数用于 Viewer 代码版本切换。

### 2.2 HTTP 缓存不等于 PlayCanvas 模型实例复用

即使 WebView HTTP 缓存命中，PlayCanvas 每次新建 WebView 页面时仍需要：

- 读取 `model.ply` 的字节数据。
- 解析 PLY header 和二进制 splat 数据。
- 对 splat 数据排序 / 重排。
- 创建 `GSplatResource` 并上传 GPU 资源。

所以“重复进入仍然等一段时间”不一定代表重新下载网络资源，也可能是本地读取、PLY 解析和 GPU 上传耗时。

### 2.3 Android WebView 对大文件 HTTP 缓存不可控

后端已经给 `/storage/**/*.ply` 返回 `Cache-Control: public, max-age=604800`，但 Android WebView 是否持久缓存 46 MB 级响应不完全由业务代码控制。为了让重复进入更可控，Viewer 层增加了显式模型缓存。

## 3. 当前方案

### 3.1 Flutter 侧

文件：`mobile_app/lib/src/pages/viewer_page.dart`

当前行为：

- 不再调用 `clearCache()`。
- 不再调用 `clearLocalStorage()`。
- 不再追加每次变化的 `ts` 查询参数。
- 只保留 `viewer_build` 查询参数，确保 Viewer 代码版本升级时能拉到新页面。

### 3.2 后端静态资源缓存头

文件：`backend/app/main.py`

新增 `CacheControlledStaticFiles`，按扩展名设置缓存头：

- `/storage/**/*.ply`：`Cache-Control: public, max-age=604800`
- `/viewer/*.js`：`Cache-Control: public, max-age=31536000, immutable`
- `/viewer/*.css`：`Cache-Control: public, max-age=31536000, immutable`
- `/viewer/*.html`：`Cache-Control: no-cache`

这样做的目的：

- 模型文件允许复用一周。
- JS / CSS 文件通过 `?v=<viewer_build>` 控制版本，内容不可变时可长期缓存。
- HTML 保持 `no-cache`，避免入口页面一直停留在旧版本。

### 3.3 模型版本参数

文件：`backend/app/routes/reconstructions.py`

后端组装 `viewer_url` 时增加：

```text
model_v=<model_file_mtime_ns>_<model_file_size>
```

这个值用于 Viewer 本地模型缓存 key。模型文件内容变化后，`mtime + size` 会变化，旧缓存不会被误用。

### 3.4 IndexedDB 显式模型缓存

文件：

- `viewer/model-cache.js`
- `viewer/viewer.js`

Viewer 增加 IndexedDB 缓存库：

```text
DB: 3dgs-viewer-model-cache
Store: models
Key: <absolute_model_url>::<model_v>
```

加载流程：

```text
进入 Viewer
  -> 正在检查本地模型缓存
  -> IndexedDB 命中：用本地 Blob 构造 Response 交给 PlayCanvas
  -> IndexedDB 未命中：fetch(model.ply)，同时写入 IndexedDB
  -> PlayCanvas 解析 PLY
  -> 创建 GSplat GPU 资源
```

旧版本缓存清理：

- 写入新缓存时，会删除同一个模型 URL 下其他 `model_v` 的缓存记录。

### 3.5 缓存管理接口

文件：

- `viewer/cache.html`
- `viewer/cache-manager.js`
- `viewer/model-cache.js`

当前提供一个简单管理页：

```text
/viewer/cache.html
```

该页面支持：

- 查看已缓存模型列表。
- 查看缓存数量和总大小。
- 删除单个模型缓存。
- 清空所有模型缓存。

当前 App 内已有两个入口：

- 发布首页：`管理模型缓存` 按钮。
- 已生成模型列表页：右上角 `storage` 图标。

页面会在 `window` 上暴露一个轻量 JS API，供后续 Flutter 用户设置页通过同源 WebView 调用：

```js
window.viewerModelCache.list()
window.viewerModelCache.delete(key)
window.viewerModelCache.clear()
window.viewerModelCache.refresh()
```

其中 `list()` 返回的条目不包含 Blob 本体，只包含 `key`、`url`、`version`、`size`、`sizeLabel`、`storedAt` 等管理元数据。

## 4. 状态文案

为了区分“网络下载慢”和“本地解析慢”，Viewer 状态文案已拆分：

- `正在检查本地模型缓存...`
- `正在下载模型...`
- `正在下载并解析模型...`
- `正在读取本地模型缓存...`
- `正在解析本地模型...`
- `正在创建渲染资源...`

测试时应重点观察第二次进入是否出现 `正在读取本地模型缓存...` 或 `正在解析本地模型...`。如果仍显示 `正在下载模型...`，说明 IndexedDB 缓存未命中或写入失败。

## 5. 已知限制

- 第一次进入仍然必须下载完整模型。
- 命中 IndexedDB 后仍然需要解析 PLY 和上传 GPU，因此不会瞬间打开。
- 当前缓存单位是原始 `model.ply`，不是 PlayCanvas 已解析的 `GSplatResource` 或 GPU texture。
- 如果模型继续增大，真正的性能优化方向应是改产物格式，例如 SOG / 压缩 splat / 分级加载，而不是只依赖缓存。

## 6. 验证方式

推荐验证流程：

1. 重启后端，确保 `VIEWER_BUILD_VERSION` 已更新。
2. 重新运行或安装 App，确保移动端使用新的 `_viewerBuild`。
3. 第一次进入同一个 ready 任务，确认会下载模型。
4. 退出 Viewer 后再次进入同一个任务，确认状态出现 `正在读取本地模型缓存...` 或 `正在解析本地模型...`。
5. 如果第二次仍显示 `正在下载模型...`，检查 WebView 控制台中的 `Model cache lookup failed` / `Model cache write failed` 警告。
6. 打开 `/viewer/cache.html`，确认可以看到 IndexedDB 中的模型缓存，并可删除单条缓存或清空全部缓存。
