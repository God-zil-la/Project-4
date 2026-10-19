"""Optional Unicode PDF renderer using external WeasyPrint CSS."""

import re
from html import escape
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts" / "pdf"

CSS_TEXT = """
@page { size: A4; margin: 20mm; }

@font-face {
  font-family: StudioArabic;
  src: url("NotoSansArabic-Regular.ttf");
}
@font-face {
  font-family: StudioHindi;
  src: url("NotoSansDevanagari-Regular.ttf");
}
@font-face {
  font-family: StudioChinese;
  src: url("NotoSansSC-Test.ttf");
}
@font-face {
  font-family: StudioJapanese;
  src: url("NotoSansJP-Test.ttf");
}

body {
  font-family: StudioArabic, StudioHindi, StudioChinese,
               StudioJapanese, sans-serif;
  font-size: 11pt;
  line-height: 1.55;
  overflow-wrap: break-word;
}
h1 { font-size: 22pt; margin-bottom: 18px; }
h2 { font-size: 16pt; margin-top: 18px; }
h3, h4, h5, h6 { font-size: 13pt; margin-top: 14px; }
p, li { margin-bottom: 8px; }
hr { border: 0; border-top: 1px solid #aaa; }
.ar {
  font-family: StudioArabic;
  direction: rtl;
  text-align: right;
}
.hi { font-family: StudioHindi; }
.zh { font-family: StudioChinese; }
.ja { font-family: StudioJapanese; }
"""


def script_for(character):
    number = ord(character)
    if 0x0600 <= number <= 0x08FF:
        return "ar"
    if 0x0900 <= number <= 0x097F:
        return "hi"
    if 0x3040 <= number <= 0x30FF:
        return "ja"
    if 0x3400 <= number <= 0x9FFF:
        return "zh"
    return ""


def format_text(value):
    """Escape HTML and retain Markdown bold and script-specific fonts."""
    output = []
    for part in re.split(r"(\*\*.*?\*\*)", value):
        bold = part.startswith("**") and part.endswith("**")
        if bold:
            part = part[2:-2]

        groups = []
        current_script = None
        current_text = ""

        for character in part:
            script = script_for(character)
            if not script:
                script = current_script or ""

            if current_text and script != current_script:
                groups.append((current_script, current_text))
                current_text = ""

            current_script = script
            current_text += character

        if current_text:
            groups.append((current_script, current_text))

        rendered = ""
        for script, text in groups:
            safe = escape(text)
            if script:
                language = script
                rendered += (
                    f'<span class="{script}" lang="{language}">'
                    f'{safe}</span>'
                )
            else:
                rendered += safe

        if bold:
            rendered = "<strong>" + rendered + "</strong>"
        output.append(rendered)

    return "".join(output)


def generate_pdf_weasyprint(title, content):
    from weasyprint import HTML, CSS

    expected_fonts = [
        "NotoSansArabic-Regular.ttf",
        "NotoSansDevanagari-Regular.ttf",
        "NotoSansSC-Test.ttf",
        "NotoSansJP-Test.ttf",
    ]
    for filename in expected_fonts:
        if not (FONT_DIR / filename).is_file():
            raise FileNotFoundError(f"PDF font missing: {filename}")

    blocks = [f"<h1>{format_text(title)}</h1>"]

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if re.fullmatch(r"[-*_]{3,}", line):
            blocks.append("<hr>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = min(len(heading.group(1)), 6)
            blocks.append(
                f"<h{level}>{format_text(heading.group(2))}</h{level}>"
            )
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", line)
        if bullet:
            blocks.append("<p>&bull; " + format_text(bullet.group(1)) + "</p>")
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if numbered:
            blocks.append("<p>" + format_text(line) + "</p>")
            continue

        rtl = script_for(line[0]) == "ar"
        css_class = ' class="ar"' if rtl else ""
        blocks.append(f"<p{css_class}>{format_text(line)}</p>")

    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        "</head><body>" + "".join(blocks) + "</body></html>"
    )

    base_url = FONT_DIR.as_uri() + "/"

    return HTML(string=html, base_url=base_url).write_pdf(
        stylesheets=[CSS(string=CSS_TEXT, base_url=base_url)]
    )
