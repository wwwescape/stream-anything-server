"""Turning URL paths into files inside a shared folder — safely — and listing folders.

Every path from a request is untrusted. `resolve_path` only ever returns something that is
inside the library's folder after resolving `..`, symlinks and Windows junctions, so a request
can never reach a file outside what the user chose to share.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.config import Library

VIDEO_EXTENSIONS = frozenset(
    {"mp4", "m4v", "mkv", "webm", "mov", "avi", "wmv", "ts", "m2ts", "mpg", "mpeg", "3gp", "flv", "ogv"}
)


@dataclass(frozen=True)
class Entry:
    name: str
    is_dir: bool
    size: int | None
    modified: float


def is_video(path: Path, extra_extensions: frozenset[str] = frozenset()) -> bool:
    ext = path.suffix.lower().lstrip(".")
    return ext in VIDEO_EXTENSIONS or ext in extra_extensions


def resolve_path(library: Library, relative: str) -> Path | None:
    """The real path for `relative` inside `library`, or None if it escapes the folder or
    doesn't exist."""
    parts = [p for p in relative.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." or ":" in p for p in parts):
        return None
    try:
        candidate = library.root.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if candidate != library.root and library.root not in candidate.parents:
        return None
    return candidate


def list_folder(folder: Path, extra_extensions: frozenset[str] = frozenset()) -> list[Entry]:
    """Subfolders and video files in `folder`, folders first, each group by name. Hidden and
    system entries (dot-files, Windows hidden/system attributes) are skipped."""
    entries = []
    try:
        scan = list(os.scandir(folder))
    except OSError:
        return []
    for item in scan:
        if item.name.startswith(".") or _is_hidden_on_windows(item):
            continue
        try:
            if item.is_dir():
                entries.append(Entry(item.name, True, None, item.stat().st_mtime))
            elif item.is_file() and is_video(Path(item.name), extra_extensions):
                stat = item.stat()
                entries.append(Entry(item.name, False, stat.st_size, stat.st_mtime))
        except OSError:
            continue
    return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


def _is_hidden_on_windows(item: os.DirEntry) -> bool:
    attrs = getattr(item.stat(follow_symlinks=False), "st_file_attributes", 0)
    hidden_or_system = 0x2 | 0x4  # FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
    return bool(attrs & hidden_or_system)
