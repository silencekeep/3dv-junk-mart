from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


PLY_DTYPE_MAP = {
    "char": "i1",
    "uchar": "u1",
    "int8": "i1",
    "uint8": "u1",
    "short": "<i2",
    "ushort": "<u2",
    "int16": "<i2",
    "uint16": "<u2",
    "int": "<i4",
    "uint": "<u4",
    "int32": "<i4",
    "uint32": "<u4",
    "float": "<f4",
    "float32": "<f4",
    "double": "<f8",
    "float64": "<f8",
}

FLOAT_PLY_TYPES = {"float", "float32", "double", "float64"}


@dataclass(frozen=True)
class PlyHeader:
    format: str
    comments: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]
    vertex_count: int
    data_offset: int


@dataclass(frozen=True)
class FrameRecord:
    frame_name: str
    mask_path: Path
    rotation: np.ndarray
    translation: np.ndarray
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float
    k3: float
    k4: float
    p1: float
    p2: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Object-aware 3D pruning driven by per-frame masks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sparse_parser = subparsers.add_parser("sparse", help="Filter COLMAP sparse points before training.")
    sparse_parser.add_argument("--dataset-dir", required=True)
    sparse_parser.add_argument("--input-ply", required=True)
    sparse_parser.add_argument("--output-ply", required=True)
    sparse_parser.add_argument("--summary-path", required=True)
    sparse_parser.add_argument("--mask-factor", type=int, default=1)
    sparse_parser.add_argument("--min-visible-views", type=int, default=6)
    sparse_parser.add_argument("--min-inside-views", type=int, default=4)
    sparse_parser.add_argument("--min-inside-ratio", type=float, default=0.6)
    sparse_parser.add_argument("--min-points", type=int, default=200)
    sparse_parser.add_argument("--chunk-size", type=int, default=100000)

    gaussian_parser = subparsers.add_parser("gaussian", help="Extract object gaussians from a full-scene model.")
    gaussian_parser.add_argument("--dataset-dir", required=True)
    gaussian_parser.add_argument("--input-ply", required=True)
    gaussian_parser.add_argument("--output-ply", required=True)
    gaussian_parser.add_argument("--raw-output-ply")
    gaussian_parser.add_argument("--summary-path", required=True)
    gaussian_parser.add_argument("--dataparser-transforms", required=True)
    gaussian_parser.add_argument("--mask-factor", type=int, default=1)
    gaussian_parser.add_argument("--min-front-inside-views", type=int, default=3)
    gaussian_parser.add_argument("--min-front-inside-ratio", type=float, default=0.15)
    gaussian_parser.add_argument("--min-front-visible-views", type=int, default=6)
    gaussian_parser.add_argument("--depth-margin-scale", type=float, default=1.5)
    gaussian_parser.add_argument("--depth-margin-min", type=float, default=0.01)
    gaussian_parser.add_argument("--spatial-voxel-ratio", type=float, default=0.02)
    gaussian_parser.add_argument("--spatial-voxel-min", type=float, default=0.01)
    gaussian_parser.add_argument("--spatial-neighbor-threshold", type=int, default=12)
    gaussian_parser.add_argument("--spatial-min-component-points", type=int, default=128)
    gaussian_parser.add_argument("--spatial-component-keep-ratio", type=float, default=0.015)
    gaussian_parser.add_argument("--min-points", type=int, default=500)
    gaussian_parser.add_argument("--chunk-size", type=int, default=100000)

    return parser.parse_args()


def parse_ply_header(path: Path) -> PlyHeader:
    comments: list[str] = []
    properties: list[tuple[str, str]] = []
    vertex_count: int | None = None
    fmt: str | None = None

    with path.open("rb") as handle:
        while True:
            raw_line = handle.readline()
            if not raw_line:
                raise RuntimeError(f"Unexpected EOF while reading PLY header: {path}")

            line = raw_line.decode("ascii", errors="strict").strip()
            if line == "ply":
                continue
            if line.startswith("format "):
                fmt = line.split()[1]
                continue
            if line.startswith("comment "):
                comments.append(line[8:])
                continue
            if line.startswith("element vertex "):
                vertex_count = int(line.split()[-1])
                continue
            if line.startswith("property "):
                _, prop_type, prop_name = line.split()
                properties.append((prop_type, prop_name))
                continue
            if line == "end_header":
                break

        data_offset = handle.tell()

    if fmt not in {"ascii", "binary_little_endian"}:
        raise RuntimeError(f"Unsupported PLY format '{fmt}' in {path}")
    if vertex_count is None:
        raise RuntimeError(f"PLY vertex count was not found in {path}")
    if not properties:
        raise RuntimeError(f"PLY contains no vertex properties: {path}")

    return PlyHeader(
        format=fmt,
        comments=tuple(comments),
        properties=tuple(properties),
        vertex_count=vertex_count,
        data_offset=data_offset,
    )


def ply_dtype(header: PlyHeader) -> np.dtype:
    try:
        fields = [(name, PLY_DTYPE_MAP[prop_type]) for prop_type, name in header.properties]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported PLY property type '{exc.args[0]}'") from exc
    return np.dtype(fields)


def load_vertex_ply(path: Path) -> tuple[PlyHeader, np.ndarray]:
    header = parse_ply_header(path)
    dtype = ply_dtype(header)

    if header.format == "binary_little_endian":
        with path.open("rb") as handle:
            handle.seek(header.data_offset)
            data = np.fromfile(handle, dtype=dtype, count=header.vertex_count)
    else:
        with path.open("r", encoding="utf-8", errors="strict") as handle:
            for line in handle:
                if line.strip() == "end_header":
                    break
            data = np.loadtxt(handle, dtype=dtype, max_rows=header.vertex_count, ndmin=1)

    if data.shape[0] != header.vertex_count:
        raise RuntimeError(
            f"PLY vertex count mismatch for {path}: header={header.vertex_count}, data={data.shape[0]}"
        )
    return header, data


def format_ascii_value(prop_type: str, value: Any) -> str:
    if prop_type in FLOAT_PLY_TYPES:
        return format(float(value), ".9g")
    return str(int(value))


def write_vertex_ply(path: Path, data: np.ndarray, header: PlyHeader, *, output_format: str | None = None) -> None:
    output_format = output_format or header.format
    header_lines = [
        "ply",
        f"format {output_format} 1.0",
    ]
    header_lines.extend(f"comment {comment}" for comment in header.comments)
    header_lines.append(f"element vertex {len(data)}")
    header_lines.extend(f"property {prop_type} {name}" for prop_type, name in header.properties)
    header_lines.append("end_header")

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    if output_format == "binary_little_endian":
        with temp_path.open("wb") as handle:
            handle.write(("\n".join(header_lines) + "\n").encode("ascii"))
            data.tofile(handle)
        temp_path.replace(path)
        return

    if output_format != "ascii":
        raise RuntimeError(f"Unsupported output PLY format '{output_format}'")

    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(header_lines) + "\n")
        for row in data:
            values = [format_ascii_value(prop_type, row[name]) for prop_type, name in header.properties]
            handle.write(" ".join(values) + "\n")
    temp_path.replace(path)


def load_transforms(dataset_dir: Path) -> dict[str, Any]:
    transforms_path = dataset_dir / "transforms.json"
    if not transforms_path.exists():
        raise RuntimeError(f"transforms.json was not found: {transforms_path}")
    return json.loads(transforms_path.read_text(encoding="utf-8"))


def mask_dir_for_factor(dataset_dir: Path, factor: int) -> Path:
    return dataset_dir / ("masks" if factor == 1 else f"masks_{factor}")


def build_frame_records(dataset_dir: Path, transforms: dict[str, Any], mask_factor: int) -> list[FrameRecord]:
    frames_payload = transforms.get("frames") or []
    if not frames_payload:
        raise RuntimeError("transforms.json contains no frames.")

    mask_dir = mask_dir_for_factor(dataset_dir, mask_factor)
    if not mask_dir.exists():
        raise RuntimeError(f"Mask directory does not exist: {mask_dir}")

    records: list[FrameRecord] = []
    for frame in frames_payload:
        c2w = np.array(frame["transform_matrix"], dtype=np.float64)
        w2c = np.linalg.inv(c2w)
        frame_name = Path(frame["file_path"]).name
        mask_path = mask_dir / frame_name
        if not mask_path.exists():
            raise RuntimeError(f"Mask does not exist for frame '{frame_name}': {mask_path}")

        records.append(
            FrameRecord(
                frame_name=frame_name,
                mask_path=mask_path,
                rotation=w2c[:3, :3],
                translation=w2c[:3, 3],
                fx=float(frame.get("fl_x", transforms["fl_x"])) / mask_factor,
                fy=float(frame.get("fl_y", transforms["fl_y"])) / mask_factor,
                cx=float(frame.get("cx", transforms["cx"])) / mask_factor,
                cy=float(frame.get("cy", transforms["cy"])) / mask_factor,
                k1=float(frame.get("k1", transforms.get("k1", 0.0))),
                k2=float(frame.get("k2", transforms.get("k2", 0.0))),
                k3=float(frame.get("k3", transforms.get("k3", 0.0))),
                k4=float(frame.get("k4", transforms.get("k4", 0.0))),
                p1=float(frame.get("p1", transforms.get("p1", 0.0))),
                p2=float(frame.get("p2", transforms.get("p2", 0.0))),
            )
        )
    return records


def project_points(points_xyz: np.ndarray, frame: FrameRecord) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    camera_points = points_xyz @ frame.rotation.T + frame.translation
    depth = -camera_points[:, 2]
    valid = depth > 1e-6
    if not np.any(valid):
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32)

    valid_indices = np.flatnonzero(valid)
    normalized_x = camera_points[valid, 0] / depth[valid]
    normalized_y = camera_points[valid, 1] / depth[valid]

    r2 = normalized_x * normalized_x + normalized_y * normalized_y
    r4 = r2 * r2
    r6 = r4 * r2
    r8 = r4 * r4
    radial = 1.0 + frame.k1 * r2 + frame.k2 * r4 + frame.k3 * r6 + frame.k4 * r8
    distorted_x = normalized_x * radial + 2.0 * frame.p1 * normalized_x * normalized_y + frame.p2 * (
        r2 + 2.0 * normalized_x * normalized_x
    )
    distorted_y = normalized_y * radial + frame.p1 * (r2 + 2.0 * normalized_y * normalized_y) + 2.0 * frame.p2 * normalized_x * normalized_y

    finite = np.isfinite(distorted_x) & np.isfinite(distorted_y)
    if not np.any(finite):
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32)

    valid_indices = valid_indices[finite]
    distorted_x = distorted_x[finite]
    distorted_y = distorted_y[finite]
    pixel_x_float = frame.fx * distorted_x + frame.cx
    pixel_y_float = frame.fy * distorted_y + frame.cy
    finite_pixels = (
        np.isfinite(pixel_x_float)
        & np.isfinite(pixel_y_float)
        & (np.abs(pixel_x_float) <= np.iinfo(np.int32).max)
        & (np.abs(pixel_y_float) <= np.iinfo(np.int32).max)
    )
    if not np.any(finite_pixels):
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32)

    valid_indices = valid_indices[finite_pixels]
    pixel_x = np.rint(pixel_x_float[finite_pixels]).astype(np.int32, copy=False)
    pixel_y = np.rint(pixel_y_float[finite_pixels]).astype(np.int32, copy=False)
    return valid_indices, pixel_x, pixel_y


def accumulate_mask_votes(
    points_xyz: np.ndarray,
    frames: list[FrameRecord],
    *,
    chunk_size: int,
    label: str,
) -> tuple[np.ndarray, np.ndarray]:
    point_count = points_xyz.shape[0]
    visible_counts = np.zeros(point_count, dtype=np.int32)
    inside_counts = np.zeros(point_count, dtype=np.int32)

    for frame_index, frame in enumerate(frames, start=1):
        mask = np.asarray(Image.open(frame.mask_path).convert("L"), dtype=np.uint8) >= 128
        height, width = mask.shape

        for start in range(0, point_count, chunk_size):
            end = min(start + chunk_size, point_count)
            valid_indices, pixel_x, pixel_y = project_points(points_xyz[start:end], frame)
            if valid_indices.size == 0:
                continue

            in_image = (pixel_x >= 0) & (pixel_x < width) & (pixel_y >= 0) & (pixel_y < height)
            if not np.any(in_image):
                continue

            chunk_indices = start + valid_indices[in_image]
            visible_counts[chunk_indices] += 1

            inside_mask = mask[pixel_y[in_image], pixel_x[in_image]]
            if np.any(inside_mask):
                inside_counts[chunk_indices[inside_mask]] += 1

        if frame_index == 1 or frame_index == len(frames) or frame_index % 10 == 0:
            print(
                f"{label}_progress frame={frame_index}/{len(frames)} "
                f"visible_mean={visible_counts.mean():.2f} inside_mean={inside_counts.mean():.2f}",
                flush=True,
            )

    return visible_counts, inside_counts


def ratio_array(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros(numerator.shape[0], dtype=np.float32),
        where=denominator > 0,
    )


def ensure_min_points(kept_points: int, min_points: int, label: str) -> None:
    if kept_points < min_points:
        raise RuntimeError(f"{label} kept too few points: {kept_points} < {min_points}")


def to_serializable_path(path: Path) -> str:
    return str(path.resolve())


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def transform_points_saved_to_training(points_xyz: np.ndarray, transforms: dict[str, Any], dataparser: dict[str, Any]) -> np.ndarray:
    applied = np.array(transforms.get("applied_transform"), dtype=np.float64) if transforms.get("applied_transform") else None
    applied_h = np.eye(4, dtype=np.float64)
    if applied is not None:
        applied_h[:3, :4] = applied

    dataparser_transform = np.array(dataparser["transform"], dtype=np.float64)
    dataparser_h = np.eye(4, dtype=np.float64)
    dataparser_h[:3, :4] = dataparser_transform

    saved_to_training = dataparser_h @ np.linalg.inv(applied_h)
    points_h = np.concatenate([points_xyz.astype(np.float64), np.ones((len(points_xyz), 1), dtype=np.float64)], axis=1)
    transformed = (saved_to_training @ points_h.T).T[:, :3]
    return (transformed * float(dataparser["scale"])).astype(np.float32)


def transform_points_training_to_saved(points_xyz: np.ndarray, transforms: dict[str, Any], dataparser: dict[str, Any]) -> np.ndarray:
    applied = np.array(transforms.get("applied_transform"), dtype=np.float64) if transforms.get("applied_transform") else None
    applied_h = np.eye(4, dtype=np.float64)
    if applied is not None:
        applied_h[:3, :4] = applied

    dataparser_transform = np.array(dataparser["transform"], dtype=np.float64)
    dataparser_h = np.eye(4, dtype=np.float64)
    dataparser_h[:3, :4] = dataparser_transform

    saved_to_training = dataparser_h @ np.linalg.inv(applied_h)
    training_to_saved = np.linalg.inv(saved_to_training)
    points_unscaled = points_xyz.astype(np.float64) / float(dataparser["scale"])
    points_h = np.concatenate([points_unscaled, np.ones((len(points_xyz), 1), dtype=np.float64)], axis=1)
    transformed = (training_to_saved @ points_h.T).T[:, :3]
    return transformed.astype(np.float32)


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def gaussian_world_radius(vertices: np.ndarray) -> np.ndarray:
    scale_fields = [name for name in ("scale_0", "scale_1", "scale_2") if name in vertices.dtype.names]
    if len(scale_fields) != 3:
        return np.full(len(vertices), 0.01, dtype=np.float32)

    scales = np.stack([vertices[name].astype(np.float32) for name in scale_fields], axis=1)
    return np.exp(np.max(scales, axis=1)).astype(np.float32)


def accumulate_front_mask_votes(
    points_saved_xyz: np.ndarray,
    point_saved_radii: np.ndarray,
    frames: list[FrameRecord],
    *,
    chunk_size: int,
    label: str,
    depth_margin_scale: float,
    depth_margin_min: float,
) -> tuple[np.ndarray, np.ndarray]:
    point_count = points_saved_xyz.shape[0]
    front_visible_counts = np.zeros(point_count, dtype=np.int32)
    front_inside_counts = np.zeros(point_count, dtype=np.int32)

    for frame_index, frame in enumerate(frames, start=1):
        mask = np.asarray(Image.open(frame.mask_path).convert("L"), dtype=np.uint8) >= 128
        height, width = mask.shape

        projected_indices: list[np.ndarray] = []
        projected_x: list[np.ndarray] = []
        projected_y: list[np.ndarray] = []
        projected_depth: list[np.ndarray] = []
        projected_margin: list[np.ndarray] = []

        for start in range(0, point_count, chunk_size):
            end = min(start + chunk_size, point_count)
            valid_indices, pixel_x, pixel_y = project_points(points_saved_xyz[start:end], frame)
            if valid_indices.size == 0:
                continue

            in_image = (pixel_x >= 0) & (pixel_x < width) & (pixel_y >= 0) & (pixel_y < height)
            if not np.any(in_image):
                continue

            chunk_indices = start + valid_indices[in_image]
            camera_points = points_saved_xyz[chunk_indices] @ frame.rotation.T + frame.translation
            depth = -camera_points[:, 2]
            projected_indices.append(chunk_indices)
            projected_x.append(pixel_x[in_image])
            projected_y.append(pixel_y[in_image])
            projected_depth.append(depth.astype(np.float32, copy=False))
            projected_margin.append(
                np.maximum(point_saved_radii[chunk_indices] * depth_margin_scale, depth_margin_min).astype(np.float32, copy=False)
            )

        if projected_indices:
            frame_indices = np.concatenate(projected_indices, axis=0)
            frame_x = np.concatenate(projected_x, axis=0)
            frame_y = np.concatenate(projected_y, axis=0)
            frame_depth = np.concatenate(projected_depth, axis=0)
            frame_margin = np.concatenate(projected_margin, axis=0)

            packed_pixel = frame_y.astype(np.int64) * width + frame_x.astype(np.int64)
            order = np.lexsort((frame_depth, packed_pixel))
            packed_sorted = packed_pixel[order]
            depth_sorted = frame_depth[order]
            margin_sorted = frame_margin[order]
            indices_sorted = frame_indices[order]
            x_sorted = frame_x[order]
            y_sorted = frame_y[order]

            min_depth = np.empty_like(depth_sorted)
            start = 0
            while start < len(order):
                end = start + 1
                while end < len(order) and packed_sorted[end] == packed_sorted[start]:
                    end += 1
                min_depth[start:end] = depth_sorted[start]
                start = end

            front = depth_sorted <= (min_depth + margin_sorted)
            if np.any(front):
                front_indices = indices_sorted[front]
                front_visible_counts[front_indices] += 1
                inside_mask = mask[y_sorted[front], x_sorted[front]]
                if np.any(inside_mask):
                    front_inside_counts[front_indices[inside_mask]] += 1

        if frame_index == 1 or frame_index == len(frames) or frame_index % 10 == 0:
            print(
                f"{label}_progress frame={frame_index}/{len(frames)} "
                f"front_visible_mean={front_visible_counts.mean():.2f} front_inside_mean={front_inside_counts.mean():.2f}",
                flush=True,
            )

    return front_visible_counts, front_inside_counts


def spatial_cleanup_mask(
    points_xyz: np.ndarray,
    candidate_mask: np.ndarray,
    *,
    voxel_ratio: float,
    voxel_min: float,
    neighbor_threshold: int,
    min_component_points: int,
    component_keep_ratio: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    if not np.any(candidate_mask):
        raise RuntimeError("Spatial cleanup received an empty candidate mask.")

    candidate_indices = np.flatnonzero(candidate_mask)
    candidate_points = points_xyz[candidate_indices]
    bbox_min = candidate_points.min(axis=0)
    bbox_max = candidate_points.max(axis=0)
    bbox_diag = float(np.linalg.norm(bbox_max - bbox_min))
    voxel_size = max(bbox_diag * voxel_ratio, voxel_min)

    voxel_coords = np.floor((candidate_points - bbox_min) / voxel_size).astype(np.int32)
    unique_voxels, inverse, voxel_counts = np.unique(voxel_coords, axis=0, return_inverse=True, return_counts=True)

    voxel_count_map = {tuple(voxel): int(count) for voxel, count in zip(unique_voxels, voxel_counts)}
    neighbor_offsets = np.array(
        [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)],
        dtype=np.int32,
    )

    local_neighbor_points = np.zeros(len(unique_voxels), dtype=np.int32)
    for voxel_index, voxel in enumerate(unique_voxels):
        total = 0
        for offset in neighbor_offsets:
            total += voxel_count_map.get((int(voxel[0] + offset[0]), int(voxel[1] + offset[1]), int(voxel[2] + offset[2])), 0)
        local_neighbor_points[voxel_index] = total

    dense_voxel_mask = local_neighbor_points >= neighbor_threshold
    dense_candidate_mask = dense_voxel_mask[inverse]
    dense_indices = candidate_indices[dense_candidate_mask]

    active_voxel_indices = np.flatnonzero(dense_voxel_mask)
    active_voxels = {tuple(unique_voxels[index]): int(index) for index in active_voxel_indices}
    visited: set[tuple[int, int, int]] = set()
    components: list[list[int]] = []
    adjacency_offsets = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

    for voxel_index in active_voxel_indices:
        voxel_key = tuple(unique_voxels[voxel_index])
        if voxel_key in visited:
            continue

        stack = [voxel_key]
        visited.add(voxel_key)
        component_voxel_indices: list[int] = []
        while stack:
            current = stack.pop()
            component_voxel_indices.append(active_voxels[current])
            for dx, dy, dz in adjacency_offsets:
                neighbor = (current[0] + dx, current[1] + dy, current[2] + dz)
                if neighbor in active_voxels and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(component_voxel_indices)

    component_point_counts: list[int] = []
    for component in components:
        component_mask = np.isin(inverse, component)
        component_point_counts.append(int(component_mask.sum()))

    largest_component_points = max(component_point_counts, default=0)
    min_component_keep_points = max(min_component_points, int(math.ceil(largest_component_points * component_keep_ratio)))

    keep_voxel_indices: set[int] = set()
    for component, point_count in zip(components, component_point_counts):
        if point_count >= min_component_keep_points:
            keep_voxel_indices.update(component)

    clean_candidate_mask = np.isin(inverse, list(keep_voxel_indices)) if keep_voxel_indices else np.zeros_like(inverse, dtype=bool)
    final_mask = np.zeros_like(candidate_mask, dtype=bool)
    final_mask[candidate_indices[clean_candidate_mask]] = True

    summary = {
        "candidate_points": int(len(candidate_indices)),
        "dense_candidate_points": int(len(dense_indices)),
        "voxel_size": float(voxel_size),
        "occupied_voxels": int(len(unique_voxels)),
        "dense_voxels": int(dense_voxel_mask.sum()),
        "neighbor_threshold": int(neighbor_threshold),
        "largest_component_points": int(largest_component_points),
        "min_component_keep_points": int(min_component_keep_points),
        "kept_component_count": int(
            sum(1 for point_count in component_point_counts if point_count >= min_component_keep_points)
        ),
        "component_point_counts_top10": sorted(component_point_counts, reverse=True)[:10],
    }
    return final_mask, summary


def run_sparse_prune(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir).resolve()
    input_ply = Path(args.input_ply).resolve()
    output_ply = Path(args.output_ply).resolve()
    summary_path = Path(args.summary_path).resolve()

    transforms = load_transforms(dataset_dir)
    frames = build_frame_records(dataset_dir, transforms, args.mask_factor)
    header, vertices = load_vertex_ply(input_ply)
    points_xyz = np.stack([vertices["x"], vertices["y"], vertices["z"]], axis=1).astype(np.float32)

    print(
        f"sparse_prune_start input={input_ply} points={len(vertices)} frames={len(frames)} "
        f"mask_factor={args.mask_factor}",
        flush=True,
    )
    visible_counts, inside_counts = accumulate_mask_votes(
        points_xyz,
        frames,
        chunk_size=args.chunk_size,
        label="sparse_prune",
    )
    inside_ratio = ratio_array(inside_counts, visible_counts)
    keep_mask = (
        (visible_counts >= args.min_visible_views)
        & (inside_counts >= args.min_inside_views)
        & (inside_ratio >= args.min_inside_ratio)
    )
    kept_vertices = vertices[keep_mask]
    ensure_min_points(len(kept_vertices), args.min_points, "sparse pruning")
    write_vertex_ply(output_ply, kept_vertices, header)

    kept_xyz = np.stack([kept_vertices["x"], kept_vertices["y"], kept_vertices["z"]], axis=1).astype(np.float32)
    summary = {
        "mode": "sparse",
        "dataset_dir": to_serializable_path(dataset_dir),
        "input_ply": to_serializable_path(input_ply),
        "output_ply": to_serializable_path(output_ply),
        "mask_factor": args.mask_factor,
        "frame_count": len(frames),
        "input_points": int(len(vertices)),
        "kept_points": int(len(kept_vertices)),
        "removed_points": int(len(vertices) - len(kept_vertices)),
        "keep_ratio": float(len(kept_vertices) / max(len(vertices), 1)),
        "min_visible_views": args.min_visible_views,
        "min_inside_views": args.min_inside_views,
        "min_inside_ratio": args.min_inside_ratio,
        "mean_visible_views": float(visible_counts.mean()),
        "mean_inside_ratio_all": float(inside_ratio.mean()),
        "mean_inside_ratio_kept": float(inside_ratio[keep_mask].mean()),
        "bounds_min": kept_xyz.min(axis=0).tolist(),
        "bounds_max": kept_xyz.max(axis=0).tolist(),
    }
    write_summary(summary_path, summary)
    print(
        f"sparse_prune_done kept={summary['kept_points']}/{summary['input_points']} "
        f"ratio={summary['keep_ratio']:.4f} summary={summary_path}",
        flush=True,
    )


def run_gaussian_prune(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir).resolve()
    input_ply = Path(args.input_ply).resolve()
    output_ply = Path(args.output_ply).resolve()
    raw_output_ply = Path(args.raw_output_ply).resolve() if args.raw_output_ply else None
    summary_path = Path(args.summary_path).resolve()
    dataparser_path = Path(args.dataparser_transforms).resolve()

    transforms = load_transforms(dataset_dir)
    frames = build_frame_records(dataset_dir, transforms, args.mask_factor)
    dataparser = json.loads(dataparser_path.read_text(encoding="utf-8"))
    header, vertices = load_vertex_ply(input_ply)
    points_train = np.stack([vertices["x"], vertices["y"], vertices["z"]], axis=1).astype(np.float32)
    points_saved = transform_points_training_to_saved(points_train, transforms, dataparser)
    points_saved_radii = gaussian_world_radius(vertices) / float(dataparser["scale"])

    print(
        f"gaussian_extract_start input={input_ply} gaussians={len(vertices)} frames={len(frames)} "
        f"mask_factor={args.mask_factor} raw_output={raw_output_ply}",
        flush=True,
    )
    visible_counts, inside_counts = accumulate_mask_votes(
        points_saved,
        frames,
        chunk_size=args.chunk_size,
        label="gaussian_extract_projection",
    )
    front_visible_counts, front_inside_counts = accumulate_front_mask_votes(
        points_saved,
        points_saved_radii,
        frames,
        chunk_size=args.chunk_size,
        label="gaussian_extract_front",
        depth_margin_scale=args.depth_margin_scale,
        depth_margin_min=args.depth_margin_min,
    )

    inside_ratio = ratio_array(inside_counts, visible_counts)
    front_inside_ratio = ratio_array(front_inside_counts, front_visible_counts)

    raw_keep_mask = (
        (front_visible_counts >= args.min_front_visible_views)
        & (front_inside_counts >= args.min_front_inside_views)
        & (front_inside_ratio >= args.min_front_inside_ratio)
    )
    ensure_min_points(int(raw_keep_mask.sum()), args.min_points, "gaussian object extraction (raw stage)")

    raw_vertices = vertices[raw_keep_mask]
    if raw_output_ply is not None:
        write_vertex_ply(raw_output_ply, raw_vertices, header, output_format="binary_little_endian")

    clean_keep_mask, spatial_summary = spatial_cleanup_mask(
        points_train,
        raw_keep_mask,
        voxel_ratio=args.spatial_voxel_ratio,
        voxel_min=args.spatial_voxel_min,
        neighbor_threshold=args.spatial_neighbor_threshold,
        min_component_points=args.spatial_min_component_points,
        component_keep_ratio=args.spatial_component_keep_ratio,
    )
    ensure_min_points(int(clean_keep_mask.sum()), args.min_points, "gaussian object extraction (clean stage)")

    kept_vertices = vertices[clean_keep_mask]
    write_vertex_ply(output_ply, kept_vertices, header, output_format="binary_little_endian")

    opacity_summary: dict[str, float] | None = None
    if "opacity" in vertices.dtype.names:
        alpha = sigmoid(vertices["opacity"].astype(np.float64))
        opacity_summary = {
            "mean_alpha_all": float(alpha.mean()),
            "mean_alpha_raw": float(alpha[raw_keep_mask].mean()),
            "mean_alpha_clean": float(alpha[clean_keep_mask].mean()),
            "min_alpha_all": float(alpha.min()),
            "max_alpha_all": float(alpha.max()),
        }

    summary = {
        "mode": "gaussian_object_extraction",
        "dataset_dir": to_serializable_path(dataset_dir),
        "input_ply": to_serializable_path(input_ply),
        "raw_output_ply": to_serializable_path(raw_output_ply) if raw_output_ply is not None else None,
        "output_ply": to_serializable_path(output_ply),
        "dataparser_transforms": to_serializable_path(dataparser_path),
        "mask_factor": args.mask_factor,
        "frame_count": len(frames),
        "input_gaussians": int(len(vertices)),
        "raw_gaussians": int(raw_keep_mask.sum()),
        "clean_gaussians": int(len(kept_vertices)),
        "removed_gaussians": int(len(vertices) - len(kept_vertices)),
        "raw_keep_ratio": float(raw_keep_mask.sum() / max(len(vertices), 1)),
        "clean_keep_ratio": float(len(kept_vertices) / max(len(vertices), 1)),
        "front_visibility_thresholds": {
            "min_front_visible_views": args.min_front_visible_views,
            "min_front_inside_views": args.min_front_inside_views,
            "min_front_inside_ratio": args.min_front_inside_ratio,
            "depth_margin_scale": args.depth_margin_scale,
            "depth_margin_min": args.depth_margin_min,
        },
        "mean_visible_views": float(visible_counts.mean()),
        "mean_inside_ratio_all": float(inside_ratio.mean()),
        "mean_front_visible_views": float(front_visible_counts.mean()),
        "mean_front_inside_ratio_all": float(front_inside_ratio.mean()),
        "mean_front_inside_ratio_raw": float(front_inside_ratio[raw_keep_mask].mean()),
        "mean_front_inside_ratio_clean": float(front_inside_ratio[clean_keep_mask].mean()),
        "spatial_cleanup": spatial_summary,
        "opacity": opacity_summary,
    }
    write_summary(summary_path, summary)
    print(
        f"gaussian_extract_done raw={summary['raw_gaussians']}/{summary['input_gaussians']} "
        f"clean={summary['clean_gaussians']}/{summary['input_gaussians']} summary={summary_path}",
        flush=True,
    )


def main() -> int:
    args = parse_args()
    if args.command == "sparse":
        run_sparse_prune(args)
        return 0
    if args.command == "gaussian":
        run_gaussian_prune(args)
        return 0
    raise RuntimeError(f"Unsupported command '{args.command}'")


if __name__ == "__main__":
    raise SystemExit(main())
