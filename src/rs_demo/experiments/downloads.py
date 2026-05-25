from __future__ import annotations

import json
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


MMEBV2Profile = Literal["metadata", "image-smoke", "vlm2vec-eval", "full"]


@dataclass(frozen=True)
class MMEBV2DownloadConfig:
    local_dir: Path = Path("data/external/mmeb-v2/hf-repo")
    repo_id: str = "TIGER-Lab/MMEB-V2"
    profile: MMEBV2Profile = "metadata"
    revision: str | None = None


@dataclass(frozen=True)
class MMEBV2DownloadResult:
    repo_id: str
    profile: str
    local_dir: Path
    snapshot_path: Path
    allow_patterns: tuple[str, ...] | None
    revision: str | None


@dataclass(frozen=True)
class MMEBV2Vlm2VecSetupConfig:
    local_dir: Path = Path("data/external/mmeb-v2/vlm2vec_eval")
    repo_id: str = "TIGER-Lab/MMEB-V2"
    revision: str | None = None
    download: bool = True
    unpack: bool = True
    force_unpack: bool = False


@dataclass(frozen=True)
class MMEBV2Vlm2VecSetupResult:
    local_dir: Path
    download: MMEBV2DownloadResult | None
    unpacked: tuple[str, ...]
    skipped: tuple[str, ...]
    manifest_path: Path


def download_mmeb_v2(config: MMEBV2DownloadConfig) -> MMEBV2DownloadResult:
    """Download MMEB-V2 assets with Hugging Face Hub while preserving repo layout."""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "MMEB-V2 download requires huggingface_hub. Install with "
            "pip install -e '.[mmeb]'."
        ) from exc

    allow_patterns = _mmeb_v2_allow_patterns(config.profile)
    config.local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_download(
        repo_id=config.repo_id,
        repo_type="dataset",
        revision=config.revision,
        local_dir=config.local_dir,
        allow_patterns=list(allow_patterns) if allow_patterns is not None else None,
    )
    result = MMEBV2DownloadResult(
        repo_id=config.repo_id,
        profile=config.profile,
        local_dir=config.local_dir,
        snapshot_path=Path(snapshot_path),
        allow_patterns=allow_patterns,
        revision=config.revision,
    )
    _write_mmeb_v2_download_manifest(config.local_dir.parent / "download_manifest.json", result)
    return result


def setup_mmeb_v2_vlm2vec_eval(config: MMEBV2Vlm2VecSetupConfig) -> MMEBV2Vlm2VecSetupResult:
    """Prepare MMEB-V2 assets in the directory layout expected by VLM2Vec eval YAMLs."""

    download_result = None
    if config.download:
        download_result = download_mmeb_v2(
            MMEBV2DownloadConfig(
                local_dir=config.local_dir,
                repo_id=config.repo_id,
                profile="vlm2vec-eval",
                revision=config.revision,
            )
        )
    elif not config.local_dir.exists():
        raise FileNotFoundError(f"MMEB-V2 eval directory does not exist: {config.local_dir}")

    unpacked: list[str] = []
    skipped: list[str] = []
    if config.unpack:
        for spec in _vlm2vec_eval_archives(config.local_dir):
            label, archive_path, output_dir = spec
            if _extract_archive_once(archive_path, output_dir, label, force=config.force_unpack):
                unpacked.append(label)
            else:
                skipped.append(label)
        if _extract_video_qa_archive(config.local_dir, force=config.force_unpack):
            unpacked.append("video_qa")
        else:
            skipped.append("video_qa")
        if _extract_archive_once(
            config.local_dir / "visdoc-tasks" / "visdoc-tasks.images.tar.gz",
            config.local_dir / "visdoc-tasks",
            "visdoc_images",
            force=config.force_unpack,
        ):
            unpacked.append("visdoc_images")
        else:
            skipped.append("visdoc_images")
        _flatten_mmeb_v1_dir(config.local_dir / "image-tasks")

    manifest_path = config.local_dir.parent / "vlm2vec_eval_setup_manifest.json"
    _write_vlm2vec_setup_manifest(
        manifest_path,
        config=config,
        download_result=download_result,
        unpacked=tuple(unpacked),
        skipped=tuple(skipped),
    )
    return MMEBV2Vlm2VecSetupResult(
        local_dir=config.local_dir,
        download=download_result,
        unpacked=tuple(unpacked),
        skipped=tuple(skipped),
        manifest_path=manifest_path,
    )


def _mmeb_v2_allow_patterns(profile: MMEBV2Profile) -> tuple[str, ...] | None:
    if profile == "metadata":
        return ("README.md", "dataset_setup.py", "video-tasks/data/*.jsonl")
    if profile == "image-smoke":
        return ("README.md", "image-tasks/mmeb_v1.tar.gz")
    if profile == "vlm2vec-eval":
        return (
            "README.md",
            "dataset_setup.py",
            "image-tasks/*.tar.gz",
            "visdoc-tasks/*.tar.gz",
            "visdoc-tasks/*.tar.gz-*",
            "video-tasks/data/*.jsonl",
            "video-tasks/frames/*.tar.gz",
            "video-tasks/frames/*.tar.gz-*",
        )
    if profile == "full":
        return None
    raise ValueError(f"unknown MMEB-V2 download profile: {profile}")


def _write_mmeb_v2_download_manifest(path: Path, result: MMEBV2DownloadResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo_id": result.repo_id,
        "profile": result.profile,
        "local_dir": str(result.local_dir),
        "snapshot_path": str(result.snapshot_path),
        "allow_patterns": result.allow_patterns,
        "revision": result.revision,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _vlm2vec_eval_archives(root: Path) -> tuple[tuple[str, Path, Path], ...]:
    frames = root / "video-tasks" / "frames"
    return (
        ("mmeb_v1", root / "image-tasks" / "mmeb_v1.tar.gz", root / "image-tasks"),
        ("video_cls", frames / "video_cls.tar.gz", frames / "video_cls"),
        ("video_mret", frames / "video_mret.tar.gz", frames),
        ("video_ret", frames / "video_ret.tar.gz", frames / "video_ret"),
    )


def _extract_archive_once(archive_path: Path, output_dir: Path, label: str, *, force: bool) -> bool:
    marker = output_dir / f".{label}.unpacked"
    if marker.exists() and not force:
        return False
    if not archive_path.exists():
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(output_dir, filter="data")
    marker.write_text("ok\n", encoding="utf-8")
    return True


def _extract_video_qa_archive(root: Path, *, force: bool) -> bool:
    frames = root / "video-tasks" / "frames"
    marker = frames / ".video_qa.unpacked"
    if marker.exists() and not force:
        return False
    single_archive = frames / "video_qa.tar.gz"
    parts = sorted(frames.glob("video_qa.tar.gz-*"))
    if single_archive.exists():
        _extract_archive_once(single_archive, frames, "video_qa", force=True)
        return True
    if not parts:
        return False
    combined = frames / "video_qa.tar.gz"
    with combined.open("wb") as output:
        for part in parts:
            with part.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
    with tarfile.open(combined, "r:gz") as archive:
        archive.extractall(frames, filter="data")
    marker.write_text("ok\n", encoding="utf-8")
    return True


def _flatten_mmeb_v1_dir(image_tasks_dir: Path) -> None:
    nested = image_tasks_dir / "MMEB"
    if not nested.exists():
        return
    for child in nested.iterdir():
        target = image_tasks_dir / child.name
        if target.exists():
            continue
        shutil.move(str(child), str(target))
    try:
        nested.rmdir()
    except OSError:
        pass


def _write_vlm2vec_setup_manifest(
    path: Path,
    *,
    config: MMEBV2Vlm2VecSetupConfig,
    download_result: MMEBV2DownloadResult | None,
    unpacked: tuple[str, ...],
    skipped: tuple[str, ...],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "local_dir": str(config.local_dir),
        "repo_id": config.repo_id,
        "revision": config.revision,
        "downloaded": download_result is not None,
        "download_profile": download_result.profile if download_result else None,
        "unpacked": list(unpacked),
        "skipped": list(skipped),
        "layout": "vlm2vec_eval",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
