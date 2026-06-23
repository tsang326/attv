from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.config import settings

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
TIKTOK_VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_UPLOAD_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
TIKTOK_PUBLISH_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def is_tiktok_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


def get_auth_url(state: str) -> str:
    params = {
        "client_key": settings.tiktok_client_key,
        "scope": "user.info.basic,video.upload,video.publish",
        "response_type": "code",
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
    }
    return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict[str, Any]:
    data = {
        "client_key": settings.tiktok_client_key,
        "client_secret": settings.tiktok_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.tiktok_redirect_uri,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            TIKTOK_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )
        response.raise_for_status()
        return response.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    data = {
        "client_key": settings.tiktok_client_key,
        "client_secret": settings.tiktok_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            TIKTOK_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )
        response.raise_for_status()
        return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }


def get_creator_info(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(TIKTOK_CREATOR_INFO_URL, headers=_auth_headers(access_token), json={})
        response.raise_for_status()
        return response.json()


def upload_video_file(
    access_token: str,
    video_path: Path,
    title: str,
    privacy_level: str = "SELF_ONLY",
    mode: str = "inbox",
) -> dict[str, Any]:
    """Upload video to TikTok inbox (draft) or direct private post."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    video_size = video_path.stat().st_size
    init_url = TIKTOK_UPLOAD_INIT_URL if mode == "inbox" else TIKTOK_VIDEO_INIT_URL

    init_body: dict[str, Any] = {
        "post_info": {
            "title": title[:150],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1,
        },
    }

    with httpx.Client(timeout=120.0) as client:
        init_resp = client.post(init_url, headers=_auth_headers(access_token), json=init_body)
        init_resp.raise_for_status()
        init_data = init_resp.json()

        upload_url = init_data.get("data", {}).get("upload_url")
        publish_id = init_data.get("data", {}).get("publish_id")
        if not upload_url:
            raise RuntimeError(f"TikTok init failed: {init_data}")

        with video_path.open("rb") as f:
            upload_resp = client.put(
                upload_url,
                content=f.read(),
                headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{video_size - 1}/{video_size}"},
            )
            upload_resp.raise_for_status()

        status_resp = client.post(
            TIKTOK_PUBLISH_STATUS_URL,
            headers=_auth_headers(access_token),
            json={"publish_id": publish_id},
        )
        status_data = status_resp.json()

    return {
        "publish_id": publish_id,
        "mode": mode,
        "privacy_level": privacy_level,
        "status": status_data,
    }


def publish_to_tiktok(
    access_token: str,
    job_dir: Path,
    caption: str,
    privacy_level: str = "SELF_ONLY",
    mode: str = "inbox",
) -> dict[str, Any]:
    video_path = job_dir / "output.mp4"
    result = upload_video_file(
        access_token=access_token,
        video_path=video_path,
        title=caption,
        privacy_level=privacy_level,
        mode=mode,
    )
    publish_path = job_dir / "publish_result.json"
    publish_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
