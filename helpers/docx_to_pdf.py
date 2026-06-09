from pathlib import Path

import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from resources.values import FONT_URL_FOR_PDF, LOCAL_DOWNLOAD_PATH

STYLES = getSampleStyleSheet()


def _prepare_cyrillic_font() -> str:
    if LOCAL_DOWNLOAD_PATH.exists():
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(LOCAL_DOWNLOAD_PATH)))
            return "DejaVuSans"
        except Exception as e:
            print(f"Failed to register existing local font: {e}")
            return "Helvetica"

    try:
        response = requests.get(FONT_URL_FOR_PDF, timeout=10)
        response.raise_for_status()

        LOCAL_DOWNLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DOWNLOAD_PATH.write_bytes(response.content)

        pdfmetrics.registerFont(TTFont("DejaVuSans", str(LOCAL_DOWNLOAD_PATH)))
        return "DejaVuSans"
    except Exception as e:
        print(f"Request failed to download or register font: {e}")
        return "Helvetica"


def build_resume_pdf(text: str, output_pdf: Path) -> str:
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    font_name = _prepare_cyrillic_font()

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    resume_style = ParagraphStyle(
        'ResumeText',
        parent=STYLES['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=4
    )

    story = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue

        safe_line = (
            line
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        story.append(Paragraph(safe_line, resume_style))

    doc.build(story)

    return str(output_pdf.resolve())
