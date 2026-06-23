from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

STATUS_ORDER = [
    "queued",
    "extracting",
    "summarizing",
    "scripting",
    "tts_generating",
    "rendering",
    "ready",
    "publishing",
    "published",
    "failed",
    "scheduled",
]

STATUS_LABELS = {
    "queued": "Chờ xử lý",
    "extracting": "Trích xuất",
    "summarizing": "Tóm tắt",
    "scripting": "Viết script",
    "tts_generating": "Tạo giọng đọc",
    "rendering": "Render video",
    "ready": "Sẵn sàng",
    "publishing": "Đang đăng",
    "published": "Đã đăng",
    "failed": "Lỗi",
    "scheduled": "Đã lên lịch",
}


def api_get(path: str):
    with httpx.Client(timeout=30.0) as client:
        return client.get(f"{API_BASE}{path}").json()


def api_post(path: str, json: dict | None = None):
    with httpx.Client(timeout=60.0) as client:
        return client.post(f"{API_BASE}{path}", json=json or {}).json()


def render_stepper(status: str):
    current_idx = STATUS_ORDER.index(status) if status in STATUS_ORDER else 0
    cols = st.columns(6)
    steps = ["extracting", "summarizing", "scripting", "tts_generating", "rendering", "ready"]
    for i, step in enumerate(steps):
        step_idx = STATUS_ORDER.index(step)
        if status == "failed":
            icon = "❌" if i == min(current_idx, len(steps) - 1) else "○"
        elif step_idx < current_idx or status in ("published", "publishing"):
            icon = "✓"
        elif step_idx == current_idx:
            icon = "⟳"
        else:
            icon = "○"
        cols[i].markdown(f"**{icon}** {STATUS_LABELS[step]}")


st.set_page_config(page_title="ATTV", page_icon="🎬", layout="wide")
st.title("ATTV — Web to TikTok")
st.caption("Tự động tạo video ngắn từ nội dung trang web")

tab_create, tab_history, tab_settings = st.tabs(["Tạo video", "Lịch sử", "Cài đặt"])

with tab_create:
    url = st.text_input("URL trang web", placeholder="https://vnexpress.net/...")
    col1, col2 = st.columns(2)
    with col1:
        voice = st.selectbox(
            "Giọng đọc",
            ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"],
        )
    with col2:
        schedule = st.checkbox("Lên lịch chạy")
        scheduled_at = None
        if schedule:
            date = st.date_input("Ngày")
            hour = st.time_input("Giờ")
            scheduled_at = datetime.combine(date, hour).isoformat()

    if st.button("Chạy pipeline", type="primary", disabled=not url):
        payload: dict = {"url": url, "voice": voice}
        if scheduled_at:
            payload["scheduled_at"] = scheduled_at
        try:
            job = api_post("/jobs", payload)
            st.session_state["active_job_id"] = job["id"]
            st.success(f"Job {job['id']} đã tạo")
        except Exception as exc:
            st.error(f"Không tạo được job: {exc}")

    active_id = st.session_state.get("active_job_id")
    if active_id:
        st.subheader(f"Job #{active_id[:8]}")
        placeholder = st.empty()
        progress_bar = st.progress(0)

        for _ in range(120):
            try:
                job = api_get(f"/jobs/{active_id}")
            except Exception:
                st.warning("API không phản hồi. Chạy: `uvicorn backend.main:app --reload`")
                break

            with placeholder.container():
                render_stepper(job["status"])
                st.write(f"Trạng thái: **{STATUS_LABELS.get(job['status'], job['status'])}** — {job['progress']}%")
                if job.get("error"):
                    st.error(job["error"])

            progress_bar.progress(min(job["progress"], 100))

            if job["status"] in ("ready", "published", "failed", "scheduled"):
                if job["status"] == "ready":
                    video_url = f"{API_BASE}/jobs/{active_id}/video"
                    st.video(video_url)
                    meta = job.get("meta", {})
                    if meta.get("caption"):
                        st.text_area("Caption", meta["caption"], height=120)
                    st.download_button(
                        "Tải MP4",
                        data=httpx.get(video_url).content,
                        file_name=f"{active_id}.mp4",
                        mime="video/mp4",
                    )

                    with st.expander("Đăng TikTok"):
                        privacy = st.selectbox("Privacy", ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "PUBLIC_TO_EVERYONE"])
                        mode = st.selectbox("Chế độ", ["inbox", "direct"])
                        caption_override = st.text_input("Caption (tuỳ chọn)")
                        if st.button("Đăng TikTok"):
                            try:
                                result = api_post(
                                    f"/jobs/{active_id}/publish",
                                    {"privacy_level": privacy, "mode": mode, "caption": caption_override or None},
                                )
                                st.success(f"Đã gửi: {result}")
                            except Exception as exc:
                                st.error(str(exc))
                break
            time.sleep(2)

with tab_history:
    try:
        jobs = api_get("/jobs?limit=30")
        for job in jobs:
            with st.expander(f"{job['id'][:8]} — {job['status']} — {job['url'][:60]}"):
                st.json(job)
    except Exception as exc:
        st.info(f"Chưa có dữ liệu hoặc API chưa chạy: {exc}")

with tab_settings:
    st.subheader("TikTok")
    try:
        status = api_get("/auth/tiktok/status")
        if status.get("connected"):
            st.success("Đã kết nối TikTok")
            st.json(status)
        else:
            st.warning("Chưa kết nối TikTok")
            st.markdown(f"[Kết nối TikTok]({API_BASE}/auth/tiktok)")
    except Exception as exc:
        st.error(f"API error: {exc}")

    st.subheader("Batch URL")
    st.markdown("Dán nhiều URL (mỗi dòng một URL):")
    batch_text = st.text_area("URLs", height=150)
    if st.button("Chạy batch"):
        urls = [u.strip() for u in batch_text.splitlines() if u.strip()]
        if urls:
            try:
                jobs = api_post("/jobs/batch", {"urls": urls, "voice": voice})
                st.success(f"Đã tạo {len(jobs)} jobs")
            except Exception as exc:
                st.error(str(exc))
