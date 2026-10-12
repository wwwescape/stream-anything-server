"""Configuration: which folders to share, on which port, and the access key.

Read from a small TOML file (see config.example.toml). The access key isn't in that file: it's
generated on first run and kept next to it in `access_key.txt`, so the config can be shared or
copied without leaking it.
"""

from __future__ import annotations

import re
import secrets
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PORT = 8090
KEY_FILE_NAME = "access_key.txt"

# Library names appear in URLs, so keep them simple and unambiguous.
_LIBRARY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")


class ConfigError(Exception):
    """The config file is missing something or has a value that can't work."""


@dataclass(frozen=True)
class Library:
    """One shared folder, reachable under /media/<name>/…"""

    name: str
    root: Path


@dataclass(frozen=True)
class Config:
    name: str
    port: int
    libraries: tuple[Library, ...]
    access_key: str
    # Off only for tests: production refuses clients outside private/home-network ranges.
    local_only: bool = True
    extra_video_extensions: frozenset[str] = field(default_factory=frozenset)

    def library(self, name: str) -> Library | None:
        return next((lib for lib in self.libraries if lib.name.lower() == name.lower()), None)


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}. Copy config.example.toml to {path.name} to start.")
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        hint = ""
        if "'\\'" in str(exc):
            # The usual mistake: a Windows path pasted as "D:\Movies", where TOML reads \ as an escape.
            hint = " Write paths as \"D:/Movies\" (forward slashes) or in single quotes: 'D:\\Movies'."
        raise ConfigError(f"{path.name} isn't valid TOML: {exc}.{hint}") from None

    server = data.get("server", {})
    port = int(server.get("port", DEFAULT_PORT))
    if not 1 <= port <= 65535:
        raise ConfigError(f"server.port must be 1–65535, got {port}")
    name = str(server.get("name") or socket.gethostname())

    libraries = []
    for entry in data.get("libraries", []):
        lib_name = str(entry.get("name", "")).strip()
        if not _LIBRARY_NAME.match(lib_name):
            raise ConfigError(
                f"Library name {lib_name!r} must start with a letter or digit and use only letters, digits, "
                "spaces, '.', '_' or '-' (max 64)."
            )
        root = Path(str(entry.get("path", ""))).expanduser()
        if not root.is_dir():
            raise ConfigError(f"Library {lib_name!r}: folder not found: {root}")
        if any(existing.name.lower() == lib_name.lower() for existing in libraries):
            raise ConfigError(f"Library name {lib_name!r} is used twice.")
        libraries.append(Library(lib_name, root.resolve()))
    if not libraries:
        raise ConfigError("Add at least one [[libraries]] entry with a name and a path.")

    extra = frozenset(
        ext.lower().lstrip(".") for ext in data.get("media", {}).get("extra_video_extensions", [])
    )
    return Config(
        name=name,
        port=port,
        libraries=tuple(libraries),
        access_key=load_or_create_key(path.parent / KEY_FILE_NAME),
        extra_video_extensions=extra,
    )


def load_or_create_key(path: Path) -> str:
    """The access key every request must carry. Generated once (~128 bits, URL-safe)."""
    if path.is_file():
        key = path.read_text(encoding="utf-8").strip()
        if len(key) >= 16:
            return key
    key = secrets.token_urlsafe(16)
    path.write_text(key + "\n", encoding="utf-8")
    return key
