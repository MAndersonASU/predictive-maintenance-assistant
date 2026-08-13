"""Static professional demonstration interface for the bounded local application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

DEMO_ASSET_ROOT = Path(__file__).with_name("demo_assets")
DEMO_ASSETS = {
    "app.js": "application/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
}
DEMO_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def register_demo_routes(app: FastAPI) -> None:
    """Register fixed local UI assets without exposing arbitrary filesystem paths."""

    @app.get("/", include_in_schema=False)
    def demonstration_interface() -> FileResponse:
        return FileResponse(
            DEMO_ASSET_ROOT / "index.html",
            media_type="text/html; charset=utf-8",
            headers=DEMO_HEADERS,
        )

    @app.get("/demo/{asset_name}", include_in_schema=False)
    def demonstration_asset(asset_name: str) -> FileResponse:
        media_type = DEMO_ASSETS.get(asset_name)
        if media_type is None:
            raise HTTPException(status_code=404, detail="Demonstration asset not found.")
        return FileResponse(
            DEMO_ASSET_ROOT / asset_name,
            media_type=media_type,
            headers=DEMO_HEADERS,
        )
