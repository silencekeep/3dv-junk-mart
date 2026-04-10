# COLMAP 位姿恢复与 BA 无法使用 GPU 遗留问题报告

## 1. 背景

在优化 3DGS 训练流水线时，曾尝试让 COLMAP 能走 GPU 的阶段尽量走 GPU，包括：

- `feature_extractor`：SIFT 特征提取。
- `sequential_matcher`：特征匹配。
- `mapper`：增量 SfM / 位姿恢复，其中包含图像注册、三角化、track 管理、局部/全局 BA 等步骤。
- `bundle_adjuster`：独立 bundle adjustment，用于 refine intrinsics。

用户在任务管理器中观察到 `GPU - CUDA = 0`，尤其是在“COLMAP 位姿恢复”阶段，因此需要确认是参数没有传入，还是 COLMAP/Ceres 本身无法执行 GPU BA。

## 2. 最新任务验证

验证任务：

```text
task_20260408_092336_1a471b
```

相关日志：

```text
storage/processed/task_20260408_092336_1a471b/pipeline.log
storage/processed/task_20260408_092336_1a471b/colmap_compat.log
```

当时兼容层曾主动追加 GPU 参数，`colmap_compat.log` 显示 mapper 实际命令已经收到：

```text
--Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0
```

独立 `bundle_adjuster` 也收到：

```text
--BundleAdjustment.use_gpu 1 --BundleAdjustment.min_num_images_gpu_solver 1 --BundleAdjustment.gpu_index 0
```

因此问题不是“参数没有传到 COLMAP”。

## 3. 关键诊断

对 `sparse/1` 执行 1 次迭代的 standalone BA 探针：

```powershell
colmap bundle_adjuster `
  --input_path storage\processed\task_20260408_092336_1a471b\dataset\colmap\sparse\1 `
  --output_path storage\processed\task_20260408_092336_1a471b\dataset\colmap\ba_gpu_probe `
  --BundleAdjustment.max_num_iterations 1 `
  --BundleAdjustment.use_gpu 1 `
  --BundleAdjustment.gpu_index 0 `
  --BundleAdjustment.min_num_images_gpu_solver 1 `
  --log_to_stderr 1
```

COLMAP 输出：

```text
Requested to use GPU for bundle adjustment, but Ceres was compiled without CUDA support. Falling back to CPU-based dense solvers.
Requested to use GPU for bundle adjustment, but Ceres was compiled without cuDSS support. Falling back to CPU-based sparse solvers.
```

结论：当前 `D:\colmap-x64-windows-cuda\bin\colmap.exe` 虽然是 CUDA build，但它链接的 Ceres 没有 CUDA/cuDSS 支持。即使命令行传入 GPU BA 参数，COLMAP 也会回退到 CPU solver。

## 4. 位姿恢复与 BA 的关系

这里需要区分两个层次：

- “位姿恢复”在 nerfstudio 日志中对应 COLMAP `mapper` 阶段。
- `mapper` 不等于单纯 BA。它还包含图像注册、PnP、三角化、track 管理、模型扩展、模型拆分/合并等逻辑。
- COLMAP 暴露的 GPU 相关参数主要作用于 `mapper` 内部的 bundle adjustment solver。
- 即使 Ceres 支持 GPU，位姿恢复整体也不会完全变成 CUDA 任务，仍会有大量 CPU 主导的步骤。

因此当前现象应解释为：

```text
位姿恢复整体：CPU 为主。
位姿恢复中的 BA 子步骤：请求 GPU 后也因 Ceres 缺 CUDA/cuDSS 回退 CPU。
独立 bundle_adjuster：同样因 Ceres 缺 CUDA/cuDSS 回退 CPU。
```

## 5. 当前决策

短期采用 CPU 路径，不再主动给 `mapper` 和 `bundle_adjuster` 追加 GPU BA 参数。

`trainer/colmap_compat.py` 当前只保留兼容行为：

- `--SiftExtraction.use_gpu` -> `--FeatureExtraction.use_gpu`
- `--SiftMatching.use_gpu` -> `--FeatureMatching.use_gpu`

这两个参数来自 nerfstudio 原始调用，用于适配 COLMAP 3.13 参数名变化。兼容层不再主动追加：

```text
--Mapper.ba_use_gpu
--Mapper.ba_gpu_index
--BundleAdjustment.use_gpu
--BundleAdjustment.gpu_index
--BundleAdjustment.min_num_images_gpu_solver
```

仍保留 `colmap_compat.log` 诊断日志，用于确认最终传给 COLMAP 的子命令。

## 6. 遗留风险

- COLMAP 位姿恢复耗时仍会主要消耗 CPU。
- 提高视频分辨率或使用 `quality/raw` 档，会增加特征数、观测数和 BA 问题规模，位姿恢复时间会明显变长。
- 任务管理器中的 `GPU - CUDA = 0` 对当前 COLMAP 位姿恢复阶段是预期结果，不表示训练阶段的 CUDA 不可用。

## 7. 后续可选方案

如果后续必须优化 COLMAP 位姿恢复耗时，优先级建议如下：

- 优先减少 COLMAP 输入规模：降低 COLMAP 输入分辨率、减少抽帧数、限制视频时长。
- 优先提升数据质量：减少模糊、反光、背景干扰，加入 object masking 或主体裁剪。
- 调整 SfM 参数：减少匹配范围、降低特征数量、降低全局 BA 频率，但要接受位姿质量风险。
- 长期方案：自行编译 COLMAP，并确保 Ceres 启用 CUDA/cuDSS 后再链接到 COLMAP。该方案环境成本高，不建议作为 MVP 当前阶段默认任务。
