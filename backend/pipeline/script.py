from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from backend.pipeline.extract import ExtractedContent
from backend.pipeline.summarize import SummaryResult


@dataclass
class Slide:
    text: str
    image_url: str
    duration_hint: float = 5.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScriptResult:
    slides: list[Slide]
    full_narration: str

    def to_dict(self) -> dict:
        return {
            "slides": [s.to_dict() for s in self.slides],
            "full_narration": self.full_narration,
        }


def build_script(content: ExtractedContent, summary: SummaryResult) -> ScriptResult:
    points = summary.bullet_points or [summary.summary]
    images = content.images or ["https://picsum.photos/1080/1920"]

    slides: list[Slide] = []
    slides.append(Slide(text=summary.hook, image_url=images[0], duration_hint=4.0))

    for i, point in enumerate(points[:4]):
        image = images[min(i + 1, len(images) - 1)]
        slides.append(Slide(text=point, image_url=image, duration_hint=6.0))

    if len(slides) < 3:
        slides.append(
            Slide(
                text=f"Theo dõi để cập nhật thêm về {content.title}",
                image_url=images[-1],
                duration_hint=4.0,
            )
        )

    narration_parts = [s.text for s in slides]
    full_narration = " ".join(narration_parts)
    return ScriptResult(slides=slides, full_narration=full_narration)


def save_script(job_dir, script: ScriptResult):
    path = job_dir / "script.json"
    path.write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_script(job_dir) -> ScriptResult:
    data = json.loads((job_dir / "script.json").read_text(encoding="utf-8"))
    slides = [Slide(**s) for s in data["slides"]]
    return ScriptResult(slides=slides, full_narration=data["full_narration"])
