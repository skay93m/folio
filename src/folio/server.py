"""Loopback HTTP server helper for previewing and verifying Folio prototypes (#243)."""

from __future__ import annotations

import functools
import http.server
import posixpath
import socketserver
import threading
import urllib.parse
from pathlib import Path

DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / "static" / "folio"


class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _PrototypeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve a prototype directory at `/` and SK Design System assets at `/assets/`."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }

    def __init__(
        self,
        *args: object,
        prototype_dir: Path,
        assets_dir: Path | None = None,
        **kwargs: object,
    ) -> None:
        self._prototype_dir = prototype_dir.resolve()
        self._explicit_assets_dir = assets_dir.resolve() if assets_dir is not None else None
        self._default_assets_dir = DEFAULT_ASSETS_DIR.resolve()
        super().__init__(*args, directory=str(self._prototype_dir), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:  # pragma: no cover
        return

    def list_directory(self, path: str):  # pragma: no cover
        self.send_error(404, "Directory listing not permitted")
        return None

    def _safe_resolve(self, root: Path, rel_path: str) -> Path | None:
        cleaned = posixpath.normpath("/" + rel_path).lstrip("/")
        if not cleaned or cleaned == ".":
            candidate = root
        else:
            candidate = (root / cleaned).resolve()
        if not candidate.is_relative_to(root):
            return None
        return candidate

    def translate_path(self, path: str) -> str:
        raw_path = urllib.parse.unquote(urllib.parse.urlparse(path).path)
        nonexistent = str(self._prototype_dir / "__folio_nonexistent__")

        if raw_path == "/assets" or raw_path.startswith("/assets/"):
            rel = raw_path[len("/assets/") :] if raw_path.startswith("/assets/") else ""
            if ".." in Path(rel).parts:
                return nonexistent
            if self._explicit_assets_dir is not None:
                resolved = self._safe_resolve(self._explicit_assets_dir, rel)
                return str(resolved) if resolved is not None else nonexistent
            local_candidate = self._safe_resolve(self._prototype_dir, f"assets/{rel}" if rel else "assets")
            if local_candidate is not None and local_candidate.is_file():
                return str(local_candidate)
            fallback = self._safe_resolve(self._default_assets_dir, rel)
            return str(fallback) if fallback is not None else nonexistent

        rel = raw_path.lstrip("/")
        if ".." in Path(rel).parts:
            return nonexistent
        resolved = self._safe_resolve(self._prototype_dir, rel)
        return str(resolved) if resolved is not None else nonexistent


def start_prototype_server(
    prototype_dir: Path | str,
    assets_dir: Path | str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[_ThreadingServer, str]:
    """Start a loopback HTTP server serving *prototype_dir* at `/` and SK assets at `/assets/`."""
    proto_path = Path(prototype_dir).expanduser().resolve()
    if not proto_path.is_dir():
        raise FileNotFoundError(f"Prototype directory does not exist: {proto_path}")
    resolved_assets = Path(assets_dir).expanduser().resolve() if assets_dir is not None else None
    if resolved_assets is not None and not resolved_assets.is_dir():
        raise FileNotFoundError(f"Assets directory does not exist: {resolved_assets}")

    handler = functools.partial(
        _PrototypeRequestHandler,
        prototype_dir=proto_path,
        assets_dir=resolved_assets,
    )
    server = _ThreadingServer((host, port), handler)
    selected_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://{host}:{selected_port}"


def _serve_directory(directory: Path | str) -> tuple[_ThreadingServer, str]:
    """Adapter seam used by `folio.verifier` and `noem folio preview`."""
    return start_prototype_server(directory)
