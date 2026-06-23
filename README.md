# ATTV — Article/Text To Video

Tool tự động tạo video ngắn (9:16) từ nội dung trang web: trích xuất → tóm tắt tiếng Việt → giọng đọc → slideshow + phụ đề → đăng TikTok.

## Yêu cầu

- Python 3.11+
- FFmpeg (`brew install ffmpeg` trên macOS)
- (Tuỳ chọn) Playwright browsers: `playwright install chromium`

## Cài đặt

```bash
cd attv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
playwright install chromium  # optional, cho site JS-heavy
cp .env.example .env
```

Thêm API key (tuỳ chọn, không có vẫn chạy được với tóm tắt đơn giản):

```env
GEMINI_API_KEY=your_key
# hoặc
GROQ_API_KEY=your_key
```

## CLI — Phase 1

```bash
python -m attv run "https://example.com/article"
python -m attv batch url1 url2 url3
python -m attv batch --csv urls.csv
```

Output lưu tại `data/jobs/{job_id}/output.mp4`.

## API + UI — Phase 2

Terminal 1 — API:

```bash
uvicorn backend.main:app --reload --port 8000
```

Terminal 2 — Dashboard:

```bash
streamlit run ui/app.py
```

Mở http://localhost:8501, paste URL, bấm **Chạy pipeline**.

## TikTok — Phase 3

1. Tạo app tại [TikTok for Developers](https://developers.tiktok.com/)
2. Bật **Content Posting API**, scope `video.upload` + `video.publish`
3. Điền `.env`:

```env
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
TIKTOK_REDIRECT_URI=http://localhost:8000/auth/tiktok/callback
```

4. Trong UI tab **Cài đặt** → Kết nối TikTok
5. Sau khi video **ready** → **Đăng TikTok** (mặc định inbox draft hoặc private)

**Lưu ý:** App chưa audit chỉ đăng được `SELF_ONLY` (private). Sau khi test ổn, apply audit để public.

## Cấu trúc

```
backend/
  main.py          # FastAPI
  worker.py        # Job queue
  pipeline/        # extract, summarize, script, tts, render, publish
ui/app.py          # Streamlit dashboard
attv/__main__.py   # CLI
```

## Chi phí

| Thành phần | Chi phí |
|---|---|
| edge-tts | Miễn phí |
| Gemini/Groq free tier | Miễn phí (có giới hạn) |
| TikTok API | Miễn phí |
| Chạy local | 0đ |

## TikTok Developer — URLs cho form đăng ký app

**Bước 1:** Bật GitHub Pages: repo → Settings → Pages → Branch `main` → folder `/docs` → Save.

**Bước 2:** Verify URL trên TikTok (URL prefix): `https://tsang326.github.io/attv/`

**Bước 3:** Điền vào form TikTok:

- **Terms of Service:** https://tsang326.github.io/attv/terms.html
- **Privacy Policy:** https://tsang326.github.io/attv/privacy.html

## Batch & Schedule — Phase 4

- **Batch:** UI tab Cài đặt hoặc `POST /jobs/batch`
- **Schedule:** tick "Lên lịch chạy" khi tạo job hoặc gửi `scheduled_at` trong API
