# Privacy Policy — ATTV

**Last updated:** June 23, 2026

## 1. Overview

ATTV respects your privacy. This policy describes what data the application handles when you run it locally or on your own server.

## 2. Data We Process

When you use ATTV, the application may process:

| Data | Purpose | Storage |
|------|---------|---------|
| URLs you submit | Fetch and summarize web content | Job database (`data/attv.db`) and job folders |
| Extracted text & images | Generate video scripts and slides | `data/jobs/{id}/` on your machine |
| Generated videos & audio | Preview and publish | `data/jobs/{id}/` on your machine |
| TikTok OAuth tokens | Post videos to your TikTok account | `data/tiktok_tokens.json` on your machine |

## 3. What We Do NOT Do

- We do not sell your data to third parties.
- We do not run a centralized cloud service that stores your content by default — ATTV is designed to run on your device or server.
- We do not access your TikTok account except through scopes you explicitly authorize.

## 4. Third-Party Services

Depending on your configuration, ATTV may send data to:

- **TikTok** — OAuth and Content Posting API (when you connect and publish)
- **Google Gemini / Groq** — optional LLM summarization (if you provide API keys)
- **Microsoft Edge TTS** — text-to-speech via edge-tts (no API key required)
- **Target websites** — to fetch content from URLs you provide

Each third party has its own privacy policy.

## 5. Local Storage & Security

- API keys are stored in your `.env` file — keep this file private and never commit it to version control.
- TikTok tokens are stored locally in `data/tiktok_tokens.json`.
- You are responsible for securing your machine and server.

## 6. Your Choices

- Do not connect TikTok if you only want local video generation.
- Delete `data/tiktok_tokens.json` to remove stored TikTok tokens.
- Revoke ATTV access in TikTok: **Settings → Security → Apps and websites**.
- Delete `data/jobs/` to remove generated content.

## 7. Children's Privacy

ATTV is not intended for users under 13 years of age.

## 8. Changes

We may update this policy. Changes will be posted in this repository.

## 9. Contact

For privacy questions, open an issue at: https://github.com/tsang326/attv/issues
