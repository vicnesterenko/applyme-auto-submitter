import re
from pathlib import Path

from docx import Document
import requests
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from resources.values import FONT_URL_FOR_PDF, LOCAL_DOWNLOAD_PATH, PROFILE_DOCX

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
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    # Styles for a clean, professional resume template.
    name_style = ParagraphStyle(
        'ResumeName',
        fontName=font_name,
        fontSize=22,
        leading=26,
        textColor=HexColor('#111111'),
        spaceAfter=4
    )

    contact_style = ParagraphStyle(
        'ResumeContact',
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=HexColor('#555555'),
        spaceAfter=12
    )

    section_heading = ParagraphStyle(
        'ResumeHeading',
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=HexColor('#1A365D'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'ResumeBody',
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=HexColor('#222222'),
        spaceAfter=4
    )

    story = []
    is_first_line = True
    is_second_line = False

    if PROFILE_DOCX.exists():
        try:
            doc_obj = Document(str(PROFILE_DOCX))
            full_profile_text = "\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()])
            match = re.search(r'"linkedin_url":\s*"([^"]+)"', full_profile_text)
            if match:
                linkedin_url = match.group(1)
                if linkedin_url and linkedin_url not in text:
                    story.append(Paragraph(f"LinkedIn: {linkedin_url}", contact_style))
        except Exception as err:
            print(f"Fallback profile parsing skipped inside PDF build engine: {err}")

    for line in text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue

        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if is_first_line:
            story.append(Paragraph(f"<b>{safe_line}</b>", name_style))
            is_first_line = False
            is_second_line = True
            continue

        if is_second_line:
            story.append(Paragraph(safe_line, contact_style))
            is_second_line = False
            continue


        if safe_line.upper() in ["EXPERIENCE", "EDUCATION", "CERTIFICATIONS", "SKILLS", "SUMMARY"]:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>{safe_line}</b>", section_heading))
            continue

        if "–" in safe_line or "—" in safe_line or "Project Manager" in safe_line or "Contract" in safe_line:
            story.append(Paragraph(f"<b>{safe_line}</b>", body_style))
        else:
            story.append(Paragraph(safe_line, body_style))

    doc.build(story)
    return str(output_pdf.resolve())
