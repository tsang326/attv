from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ExtractedContent:
    url: str
    title: str
    main_text: str
    images: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_image_url(base_url: str, src: str) -> str | None:
    if not src or src.startswith("data:"):
        return None
    absolute = urljoin(base_url, src.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute


def _is_likely_content_image(url: str, width: int | None, height: int | None) -> bool:
    lower = url.lower()
    skip_patterns = ("logo", "icon", "avatar", "sprite", "pixel", "tracking", "badge", "emoji")
    if any(p in lower for p in skip_patterns):
        return False
    if width and height and (width < 400 or height < 400):
        return False
    return True


def _collect_images(soup: BeautifulSoup, base_url: str) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()

    for prop in ("og:image", "twitter:image"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            url = _normalize_image_url(base_url, tag["content"])
            if url and url not in seen:
                seen.add(url)
                images.append(url)

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        url = _normalize_image_url(base_url, src or "")
        if not url or url in seen:
            continue
        width = _parse_int(img.get("width"))
        height = _parse_int(img.get("height"))
        if _is_likely_content_image(url, width, height):
            seen.add(url)
            images.append(url)

    return images[:8]


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(value)))
    except ValueError:
        return None


def _fetch_html(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _fetch_html_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()
        return html


def extract_content(url: str, use_playwright: bool = False) -> ExtractedContent:
    html = _fetch_html_playwright(url) if use_playwright else _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    main_text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or ""
    main_text = re.sub(r"\n{3,}", "\n\n", main_text.strip())

    if len(main_text) < 200 and not use_playwright:
        return extract_content(url, use_playwright=True)

    images = _collect_images(soup, url)
    if not images:
        images = ["https://picsum.photos/1080/1920"]

    return ExtractedContent(url=url, title=title or "Không có tiêu đề", main_text=main_text, images=images)


def save_extracted(job_dir: Path, content: ExtractedContent) -> Path:
    path = job_dir / "extracted.json"
    path.write_text(json.dumps(content.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_extracted(job_dir: Path) -> ExtractedContent:
    data = json.loads((job_dir / "extracted.json").read_text(encoding="utf-8"))
    return ExtractedContent(**data)
