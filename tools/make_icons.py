"""
Make the component icons of psychopy-radboudbox: a button box with a badge
per component, as PNG for each Builder theme (`<theme>/<stem>.png` 48 px and
`<theme>/<stem>@2x.png` 96 px, next to the components module). Builder
reads `<folder of iconFile>/<theme>/<stem>*.png`; without these folders the
Builder window does not open (IndexError in psychopy_app's ComponentIcon).

Run from the repository root: python tools/make_icons.py

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from PIL import Image, ImageDraw

COMPONENTS = (Path(__file__).resolve().parent.parent / 'psychopy_radboudbox'
              / 'components')

# icon stem: badge
ICONS = {
    'radboudboxTrigger': 'pulse',
    'radboudboxControl': 'sliders',
}

# Color of the box per theme; the buttons and badges have their own colors
THEMES = {
    'light': (60, 60, 60),
    'classic': (40, 70, 120),
    'dark': (230, 230, 230),
}
BUTTONS = [(200, 30, 30), (0, 140, 70), (37, 97, 163)]
BADGE = (230, 140, 0)
SCALE = 4  # draw larger, then shrink: smooth edges


def draw(size, theme_color, badge):
    s = size * SCALE
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 48  # one unit of the 48 px grid
    # The box
    d.rounded_rectangle([4 * u, 14 * u, 44 * u, 40 * u], radius=5 * u,
                        outline=theme_color, width=round(3 * u))
    # Three buttons
    for i, color in enumerate(BUTTONS):
        cx = (14 + 10 * i) * u
        d.ellipse([cx - 4 * u, 23 * u, cx + 4 * u, 31 * u], fill=color)
    # The badge, top right
    d.ellipse([30 * u, 0, 48 * u, 18 * u], fill=BADGE)
    w = round(2 * u)
    white = (255, 255, 255)
    if badge == 'pulse':
        d.line([(33 * u, 12 * u), (36 * u, 12 * u), (36 * u, 5 * u),
                (42 * u, 5 * u), (42 * u, 12 * u), (45 * u, 12 * u)],
               fill=white, width=w, joint='curve')
    else:
        for x, y in ((35, 9), (39, 6), (43, 11)):
            d.line([(x * u, 4 * u), (x * u, 14 * u)], fill=white, width=w)
            d.ellipse([(x - 1.8) * u, (y - 1.8) * u, (x + 1.8) * u,
                       (y + 1.8) * u], fill=white)
    return img.resize((size, size), Image.LANCZOS)


def main():
    for stem, badge in ICONS.items():
        for theme, color in THEMES.items():
            folder = COMPONENTS / theme
            folder.mkdir(exist_ok=True)
            draw(48, color, badge).save(folder / f'{stem}.png')
            draw(96, color, badge).save(folder / f'{stem}@2x.png')
            print(f'{theme}/{stem}.png, {theme}/{stem}@2x.png')


if __name__ == '__main__':
    main()
