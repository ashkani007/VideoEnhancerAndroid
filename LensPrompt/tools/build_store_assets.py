"""Build store branding from LensPrompt's existing vector icon (requires Pillow).

These are branding assets, never represented as app screenshots.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "store/graphics"
OUT.mkdir(parents=True, exist_ok=True)
FONTS = Path("/usr/share/fonts/truetype/dejavu")


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


# The circle and three bars match ic_launcher_foreground.xml's 108-unit viewport.
scale = 4
icon = Image.new("RGBA", (512 * scale, 512 * scale), "black")
d = ImageDraw.Draw(icon)
u = 512 * scale / 108
d.ellipse(tuple(round(x * u) for x in (30, 30, 78, 78)), outline="white", width=round(5 * u))
for box, color in [((42, 46, 66, 50), "#ffc83d"), ((40, 53, 68, 57), "white"), ((44, 60, 64, 64), "white")]:
    d.rectangle(tuple(round(x * u) for x in box), fill=color)
icon.resize((512, 512), Image.Resampling.LANCZOS).save(OUT / "lensprompt-icon-512.png")

# A restrained typographic feature graphic, with abstract script lines.
graphic = Image.new("RGB", (2048, 1000), "#ffc83d")
d = ImageDraw.Draw(graphic)
def text(x, y, value, size, bold=False, fill="#17191f"):
    d.text((x * 2, y * 2), value, font=font(size * 2, bold), fill=fill)
text(74, 70, "LensPrompt", 25, True)
text(70, 161, "Stay on script.", 61, True)
text(74, 255, "Speak at your own pace.", 27)
text(74, 367, "Floating teleprompter", 20, True)
text(74, 400, "Speech-assisted scrolling", 18)
for y, width, fill in [(150, 142, "#a2760f"), (193, 180, "#17191f"), (236, 156, "#a2760f"), (279, 168, "#a2760f")]:
    d.rounded_rectangle((790 * 2, y * 2, (790 + width) * 2, (y + 12) * 2), radius=8, fill=fill)
d.polygon([(754 * 2, 189 * 2), (771 * 2, 199 * 2), (754 * 2, 209 * 2)], fill="#17191f")
graphic.resize((1024, 500), Image.Resampling.LANCZOS).save(OUT / "lensprompt-feature-1024x500.png")

(OUT / "ALT_TEXT.txt").write_text(
    "Icon: LensPrompt lens ring with three script lines, one highlighted in gold.\n"
    "Feature graphic: LensPrompt. Stay on script. Speak at your own pace. Floating teleprompter and speech-assisted scrolling.\n"
    "These are branding graphics, not screenshots.\n"
)
print(OUT)
