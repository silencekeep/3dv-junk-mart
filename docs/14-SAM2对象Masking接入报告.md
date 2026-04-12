# SAM 2 对象 Masking 接入报告

## 1. 当前实现范围

本次接入目标是让 3DGS 训练支持“用户点选商品主体后，只用商品区域参与 splatfacto 训练”。

当前已实现：

- 为 SAM 2 新增独立 Conda 环境配置：`trainer/sam2_environment.yml`。
- 已在本机创建环境：`sam2_app`。
- 新增 SAM 2 分割脚本：`trainer/sam2_masking.py`。
- 后端新增 mask prompt 提交接口。
- Flutter 端开放 Object masking 开关，并新增第一帧点选 UI。
- pipeline 增加两段式流程：COLMAP 后暂停等待用户提示，提交提示后继续 SAM 2 masking 和 splatfacto 训练。
- 每个任务仍然使用 `storage/processed/<task_id>/pipeline.log` 跟踪完整阶段日志。

当前暂不实现：

- 不做 3D pruning。
- 不修改 COLMAP 输入为 masked images。
- 不对 SAM 2 结果做人工多帧修正闭环，只支持第一帧正点/负点。

## 2. 环境

SAM 2 与 nerfstudio 使用独立环境，避免破坏当前 `3dgs_app` 的 `torch 2.1.2 + cu118` 组合。

```powershell
conda env create -f trainer\sam2_environment.yml
conda activate sam2_app
```

本机已验证：

```text
sam2_app -> D:\miniconda3\envs\sam2_app
torch 2.5.1
torchvision 0.20.1
SAM-2 1.0
huggingface_hub 1.9.1
CUDA available: True
```

默认模型：

```text
facebook/sam2.1-hiera-small
```

如需切换模型：

```powershell
$env:SAM2_MODEL_ID = "facebook/sam2.1-hiera-base-plus"
```

如需指定环境 Python：

```powershell
$env:SAM2_PYTHON = "D:\miniconda3\envs\sam2_app\python.exe"
```

## 3. 状态流

不开启 Object masking：

```text
uploaded -> queued -> preprocessing -> training -> exporting -> ready
```

开启 Object masking：

```text
uploaded
-> queued
-> preprocessing
-> awaiting_mask_prompt
-> 用户在 Flutter 点选第一帧并提交
-> queued
-> masking
-> training
-> exporting
-> ready
```

`raw` 质量档位暂不允许开启 Object masking，原因是 MVP 里不希望 SAM 2 在原始全分辨率上运行导致显存和耗时失控。

## 4. 产物

用户提交点选后会生成：

```text
storage/processed/<task_id>/mask_prompts.json
storage/processed/<task_id>/dataset/masks/*.png
storage/processed/<task_id>/dataset/masks_2/*.png
storage/processed/<task_id>/dataset/masks_4/*.png
storage/processed/<task_id>/dataset/mask_summary.json
```

随后 pipeline 会把每个训练帧写入：

```json
{
  "file_path": "images/frame_00001.png",
  "mask_path": "masks/frame_00001.png"
}
```

训练仍通过 nerfstudio 的 `nerfstudio-data --data <dataset> --downscale-factor <profile.train_downscale_factor>` 消费数据。nerfstudio 会按 downscale factor 自动读取对应的 `masks_2` 或 `masks_4`。

## 5. 已知限制

- SAM 2 安装在 Windows 上会提示 `_C` 扩展未导入，官方提示可跳过后处理；当前 smoke test 仍能生成 mask。
- 单帧点选对反光、透明、遮挡或物体背面变化大的商品可能不稳定。
- 训练 mask 会减少背景监督，但由于 splatfacto 仍可能从 COLMAP sparse points 初始化背景点，最终 PLY 仍可能存在背景 floaters。
- 后续应补充 3D pruning：基于 mask 投影过滤 `sparse_pc.ply` 或导出后的 Gaussian PLY。

## 6. 已验证

已完成检查：

```powershell
python -m py_compile shared\task_store.py backend\app\schemas.py backend\app\routes\reconstructions.py trainer\pipeline.py trainer\worker.py trainer\sam2_masking.py
backend\.venv\Scripts\python.exe -m py_compile shared\task_store.py backend\app\schemas.py backend\app\routes\reconstructions.py trainer\pipeline.py trainer\worker.py
flutter analyze
git diff --check
```

额外用三帧 smoke dataset 验证了 `trainer.sam2_masking` 可在 CUDA 上生成 mask 金字塔。
