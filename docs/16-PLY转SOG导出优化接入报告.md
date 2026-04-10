# PLY 转 SOG 导出优化接入报告

## 1. 目标

根据以下规划文档，本次将 `PLY -> SOG` 接入到训练导出阶段，作为移动端 / Web 端加载优化：

- [2-基于 3DGS 技术的 3D 二手商品交易平台开发方案](D:/Projects/3dgs-app/docs/2-基于%203DGS%20技术的%203D%20二手商品交易平台开发方案.md)
- [4-3DGS二手交易平台本地MVP开发方案](D:/Projects/3dgs-app/docs/4-3DGS二手交易平台本地MVP开发方案.md)

目标原则：

- `PLY` 继续保留，作为训练和调试原始产物
- `SOG` 作为运行时优先交付格式
- `SOG` 转换失败时回退到 `PLY`，不影响任务完成

## 2. 接入位置

当前导出链路变为：

`ns-train splatfacto -> ns-export gaussian-splat -> model.ply -> splat-transform -> model.sog`

实现文件：

- [pipeline.py](D:/Projects/3dgs-app/trainer/pipeline.py)
- [reconstructions.py](D:/Projects/3dgs-app/backend/app/routes/reconstructions.py)
- [main.py](D:/Projects/3dgs-app/backend/app/main.py)
- [viewer.js](D:/Projects/3dgs-app/viewer/viewer.js)

## 3. 当前行为

### 3.1 导出阶段

- `trainer/pipeline.py` 在最终 `PLY` 产出后自动尝试执行：

```powershell
npx -y @playcanvas/splat-transform -w input.ply output.sog
```

- 默认会输出：
  - `storage/models/<task_id>/model.ply`
  - `storage/models/<task_id>/model.sog`（成功时）

### 3.2 运行时优先级

- 如果 `model.sog` 存在，任务返回的 `model_url` 和 `viewer_url` 会优先指向 `model.sog`
- 如果 `model.sog` 不存在，则自动回退到 `model.ply`

### 3.3 失败回退

以下情况不会导致整个任务失败：

- `splat-transform` 未安装
- `npx` 不可用
- `PLY -> SOG` 转换执行失败
- 转换后未产生 `model.sog`

以上情况都会记录到 `pipeline.log`，并继续以 `PLY` 作为最终运行时模型。

## 4. 任务元数据

任务状态中新增记录：

- `model_rel_path`：当前运行时优先模型
- `model_ply_rel_path`
- `model_sog_rel_path`
- `model_format`

其中：

- `model_rel_path` 用于 App 和 Viewer 的默认加载
- `model_ply_rel_path` / `model_sog_rel_path` 用于后续调试和切换

## 5. Viewer 侧变化

- Viewer 继续通过 `?model=...` 加载模型
- 现在支持更明确的提示：
  - 可传 `model.ply`
  - 也可传 `model.sog`
- 后端已为 `.sog` 增加和 `.ply` 相同的缓存头

## 6. 环境与配置

### 6.1 依赖

- Node.js
- `npx`
- `@playcanvas/splat-transform`

如果没有全局安装 `splat-transform`，pipeline 会自动尝试使用：

```powershell
npx -y @playcanvas/splat-transform
```

### 6.2 可选环境变量

- `SOG_EXPORT_ENABLED`
  - 默认：`1`
- `SOG_EXPORT_ITERATIONS`
  - 默认：`10`
- `SOG_EXPORT_GPU`
  - 默认：不指定，交给 `splat-transform` 自行选择

## 7. 实测结果

使用真实模型：

- 输入：`storage/models/task_20260408_104049_6eb437/model.ply`
- 大小：`28,403,049` bytes
- 输出：`.tmp/sog_smoke/model.sog`
- 大小：`4,128,540` bytes

压缩后体积约为原始 `14.54%`，下降约 `85.46%`。

实测转换耗时约 `16.5s`。

## 8. 后续建议

1. 给任务详情页增加 `model_format / model_ply_url / model_sog_url` 展示
2. 给 Viewer 增加“切换原始 PLY / 压缩 SOG”的调试开关
3. 评估是否将 `@playcanvas/splat-transform` 固化为本地依赖，而不是每次通过 `npx` 解析
