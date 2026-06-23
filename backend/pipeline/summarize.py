from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from backend.config import settings
from backend.pipeline.extract import ExtractedContent


@dataclass
class SummaryResult:
    hook: str
    summary: str
    bullet_points: list[str]
    caption: str
    hashtags: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _fallback_summary(content: ExtractedContent) -> SummaryResult:
    sentences = re.split(r"(?<=[.!?])\s+", content.main_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:5]
    if not sentences:
        sentences = [content.main_text[:200] or content.title]

    hook = f"Bạn đã biết về {content.title} chưa?"
    bullet_points = sentences[:4]
    summary = " ".join(bullet_points)
    hashtags = ["#tiktok", "#tinhot", "#tomtat", "#attv"]
    caption = f"{hook}\n\n{' '.join(bullet_points[:2])}\n\nNguồn: {content.url}\n{' '.join(hashtags)}"
    return SummaryResult(
        hook=hook,
        summary=summary,
        bullet_points=bullet_points,
        caption=caption,
        hashtags=hashtags,
    )


def _prompt(content: ExtractedContent) -> str:
    return f"""Bạn là biên tập viên TikTok tiếng Việt. Tóm tắt nội dung sau thành script video ngắn 30-45 giây.

Tiêu đề: {content.title}
URL: {content.url}
Nội dung:
{content.main_text[:6000]}

Trả về JSON thuần (không markdown) với format:
{{
  "hook": "câu mở đầu hấp dẫn 1 câu",
  "bullet_points": ["điểm 1", "điểm 2", "điểm 3", "điểm 4"],
  "caption": "caption TikTok kèm link nguồn",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}}

Yêu cầu: tiếng Việt tự nhiên, tối đa 120 từ đọc, tone gần gũi, không bịa thêm sự kiện."""


def _parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _summarize_gemini(content: ExtractedContent) -> SummaryResult:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(_prompt(content))
    data = _parse_llm_json(response.text)
    bullet_points = data.get("bullet_points", [])
    return SummaryResult(
        hook=data.get("hook", ""),
        summary=" ".join(bullet_points),
        bullet_points=bullet_points,
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", ["#tiktok", "#tomtat"]),
    )


def _summarize_groq(content: ExtractedContent) -> SummaryResult:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": _prompt(content)}],
        temperature=0.4,
    )
    data = _parse_llm_json(response.choices[0].message.content or "{}")
    bullet_points = data.get("bullet_points", [])
    return SummaryResult(
        hook=data.get("hook", ""),
        summary=" ".join(bullet_points),
        bullet_points=bullet_points,
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", ["#tiktok", "#tomtat"]),
    )


def summarize_content(content: ExtractedContent) -> SummaryResult:
    if settings.gemini_api_key:
        try:
            return _summarize_gemini(content)
        except Exception:
            pass
    if settings.groq_api_key:
        try:
            return _summarize_groq(content)
        except Exception:
            pass
    return _fallback_summary(content)


def save_summary(job_dir, summary: SummaryResult):
    path = job_dir / "summary.json"
    path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_summary(job_dir) -> SummaryResult:
    data = json.loads((job_dir / "summary.json").read_text(encoding="utf-8"))
    return SummaryResult(**data)
