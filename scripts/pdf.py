"""In-memory work-package PDFs; no TeX installation is needed by the app."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from scripts.data import LIST_FIELDS, LABELS, ROOT, items


def work_package_pdf(row):
    fonts = Path(reportlab.__file__).parent / "fonts"
    if "WorkBody" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("WorkBody", str(fonts / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("WorkBold", str(fonts / "VeraBd.ttf")))
    body = ParagraphStyle("WorkBody", fontName="WorkBody", fontSize=10, leading=15, spaceAfter=7, wordWrap="CJK")
    title = ParagraphStyle("WorkTitle", parent=body, fontName="WorkBold", fontSize=20, leading=26,
                           textColor=colors.HexColor("#287F9E"), spaceAfter=10)
    heading = ParagraphStyle("WorkHeading", parent=body, fontName="WorkBold", spaceBefore=12, spaceAfter=5, keepWithNext=True)
    bullet = ParagraphStyle("WorkBullet", parent=body, leftIndent=13, firstLineIndent=0, bulletIndent=2, spaceAfter=4)
    def text(value):
        return escape(str(value)).replace("\n", "<br/>")
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40,
        topMargin=102, bottomMargin=42, title=f"Work package {row['id']}: {row['title']}", author="DeltaLAB")
    story = [Paragraph(text(row["title"]), title), Paragraph("<b>ID:</b> " + text(row["id"]), body),
             Spacer(1, 5), Paragraph(text(row["description"]), body)]
    for field in LIST_FIELDS:
        entries = items(row.get(field, ""))
        if entries:
            story.append(Paragraph(LABELS[field], heading))
            story.extend(Paragraph(text(item), bullet, bulletText="-") for item in entries)
    for field in ("payment", "supervisor", "professor"):
        if row.get(field, "").strip():
            story.extend([Paragraph(LABELS[field], heading), Paragraph(text(row[field]), body)])
    def page(canvas, doc):
        width, height = letter
        canvas.saveState()
        canvas.setFont("WorkBold", 14)
        canvas.drawString(40, height - 39, "DeltaLAB: work packages")
        canvas.setFont("WorkBody", 8)
        canvas.drawString(40, height - 55, "Electromechanical Engineering School")
        canvas.drawString(40, height - 68, "Tecnológico de Costa Rica")
        canvas.drawImage(str(ROOT / "assets/images/logo_pdf.png"), width-94, height-78, width=52, height=52,
                         preserveAspectRatio=True, mask="auto")
        canvas.setStrokeColor(colors.HexColor("#70BDD9"))
        canvas.line(40, height-88, width-40, height-88)
        canvas.setFont("WorkBody", 8)
        canvas.drawString(40, 24, f"Work package {row['id']}")
        canvas.drawRightString(width-40, 24, f"Page {doc.page}")
        canvas.restoreState()
    document.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
