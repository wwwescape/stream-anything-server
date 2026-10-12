"""The HTTP API.

- `GET /health`: is the server up (no key needed; reveals nothing but the server's name).
- `GET /api/v1/libraries`, `GET /api/v1/browse/{library}/{path}`: JSON folder listings, for the
  Stream Anything app to browse.
- `GET /media/{library}/{path}`: the video itself, with HTTP range support so players can seek.
- `GET /`, `GET /browse/{library}/{path}`: the same listings as a plain web page, for a phone's
  browser — tap a video to play it, or long-press to copy its link.

Every request must come from the home network, and everything except /health must carry the
access key (`?key=…` or an `X-Access-Key` header). Links the server hands out include the key, so
they work when pasted into Stream Anything as-is.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app import __version__
from app.config import Config, Library
from app.library import is_video, list_folder, resolve_path
from app.security import is_home_network, key_matches, presented_key
from app.web import render_libraries, render_listing

# A few containers the stdlib doesn't know, so players get a sensible Content-Type.
for _ext, _type in {
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".m2ts": "video/mp2t",
    ".ts": "video/mp2t",
    ".flv": "video/x-flv",
    ".ogv": "video/ogg",
}.items():
    mimetypes.add_type(_type, _ext)

_OPEN_PATHS = {"/health"}


def create_app(config: Config) -> FastAPI:
    app = FastAPI(
        title="Stream Anything Server", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if config.local_only and not is_home_network(request.client.host if request.client else None):
            return JSONResponse({"detail": "Only devices on the home network can connect."}, status_code=403)
        if request.url.path not in _OPEN_PATHS and not key_matches(presented_key(request), config.access_key):
            return JSONResponse({"detail": "Missing or wrong access key."}, status_code=401)
        response = await call_next(request)
        # Listings and links contain the key; never let anything cache or leak them.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def library_or_404(name: str) -> Library:
        library = config.library(name)
        if library is None:
            raise HTTPException(404, "No such library.")
        return library

    def folder_or_404(library: Library, path: str) -> Path:
        folder = resolve_path(library, path)
        if folder is None or not folder.is_dir():
            raise HTTPException(404, "No such folder.")
        return folder

    def relative_path(library: Library, path: Path) -> str:
        return path.relative_to(library.root).as_posix() if path != library.root else ""

    def url(request: Request, prefix: str, library: str, relative: str = "") -> str:
        """An absolute link on the address this client used, with the key attached."""
        segments = [quote(library, safe="")] + [quote(p, safe="") for p in relative.split("/") if p]
        base = str(request.base_url).rstrip("/")
        return f"{base}/{prefix}/{'/'.join(segments)}?key={quote(config.access_key)}"

    def listing(request: Request, library: Library, path: str) -> dict:
        folder = folder_or_404(library, path)
        here = relative_path(library, folder)
        parent = here.rsplit("/", 1)[0] if "/" in here else ("" if here else None)
        entries = []
        for entry in list_folder(folder, config.extra_video_extensions):
            child = f"{here}/{entry.name}" if here else entry.name
            item = {
                "name": entry.name,
                "type": "folder" if entry.is_dir else "video",
                "modified": entry.modified,
            }
            if entry.is_dir:
                item["browse_url"] = url(request, "api/v1/browse", library.name, child)
                item["page_url"] = url(request, "browse", library.name, child)
            else:
                item["size"] = entry.size
                item["media_url"] = url(request, "media", library.name, child)
            entries.append(item)
        return {
            "server": config.name,
            "library": library.name,
            "path": here,
            "parent_browse_url": None
            if parent is None
            else url(request, "api/v1/browse", library.name, parent),
            "parent_page_url": None if parent is None else url(request, "browse", library.name, parent),
            "entries": entries,
        }

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "name": config.name, "version": __version__}

    @app.get("/api/v1/libraries")
    def libraries(request: Request) -> dict:
        return {
            "server": config.name,
            "libraries": [
                {"name": lib.name, "browse_url": url(request, "api/v1/browse", lib.name)}
                for lib in config.libraries
            ],
        }

    @app.get("/api/v1/browse/{library}")
    @app.get("/api/v1/browse/{library}/{path:path}")
    def browse(request: Request, library: str, path: str = "") -> dict:
        return listing(request, library_or_404(library), path)

    @app.get("/media/{library}/{path:path}")
    def media(library: str, path: str) -> FileResponse:
        lib = library_or_404(library)
        file = resolve_path(lib, path)
        if file is None or not file.is_file() or not is_video(file, config.extra_video_extensions):
            raise HTTPException(404, "No such video.")
        media_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        # FileResponse answers Range requests with 206 Partial Content, which is what lets the
        # player seek without downloading the whole file first.
        return FileResponse(file, media_type=media_type, filename=None)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> str:
        return render_libraries(
            config.name,
            [(lib.name, url(request, "browse", lib.name)) for lib in config.libraries],
        )

    @app.get("/browse/{library}", response_class=HTMLResponse)
    @app.get("/browse/{library}/{path:path}", response_class=HTMLResponse)
    def browse_page(request: Request, library: str, path: str = "") -> str:
        lib = library_or_404(library)
        data = listing(request, lib, path)
        home_url = f"{str(request.base_url).rstrip('/')}/?key={quote(config.access_key)}"
        return render_listing(data, home_url)

    return app
