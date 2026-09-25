"""Composite the supplied Stardew Valley farm scene behind the animated intro dialogue."""

from pathlib import Path
from PIL import Image, ImageSequence

SOURCE = Path("assets/dialogue-typewriter-base.gif")
BACKGROUND = Path("assets/sdv-intro-background.png")
OUTPUT = Path("assets/dialogue-typewriter.gif")


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Nearest-neighbor cover crop so the supplied pixel art stays crisp."""
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.NEAREST,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h)).convert("RGBA")


def render() -> None:
    with Image.open(SOURCE) as source:
        src_w, src_h = source.size
        # Preserve the dialogue at native size while giving it a 16:9 Stardew scene.
        canvas_h = max(src_h, round(src_w * 9 / 16))
        background = cover(Image.open(BACKGROUND).convert("RGB"), (src_w, canvas_h))

        frames: list[Image.Image] = []
        durations: list[int] = []
        for frame in ImageSequence.Iterator(source):
            layer = frame.convert("RGBA")
            composed = background.copy()
            composed.alpha_composite(layer, (0, canvas_h - src_h))
            frames.append(composed.convert("RGB"))
            durations.append(frame.info.get("duration", source.info.get("duration", 100)))

        if not frames:
            raise RuntimeError("The source dialogue GIF has no frames")

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            OUTPUT,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=source.info.get("loop", 0),
            disposal=2,
            optimize=True,
        )

        print(
            f"Rendered {len(frames)} frames: source={src_w}x{src_h}, "
            f"output={src_w}x{canvas_h}"
        )


if __name__ == "__main__":
    render()
