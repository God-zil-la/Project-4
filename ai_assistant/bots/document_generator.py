from io import BytesIO, StringIO
import csv

from docx import Document
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from xml.sax.saxutils import escape


SUPPORTED_FORMATS = {"pdf", "docx", "xlsx", "csv"}


def generate_document(title, content, file_format):
    """Generate a document in memory and return its bytes."""

    file_format = str(file_format).lower().strip()

    if file_format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported document format.")

    title = str(title).strip() or "Document"
    content = str(content)

    if file_format == "docx":
        document = Document()
        document.add_heading(title, 0)

        for paragraph in content.split("\n"):
            document.add_paragraph(paragraph)

        buffer = BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    if file_format == "pdf":
        buffer = BytesIO()
        pdf = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        elements = [
            Paragraph(escape(title), styles["Title"]),
            Spacer(1, 16),
        ]

        import re
        from reportlab.platypus import HRFlowable
        from reportlab.lib.styles import ParagraphStyle

        heading_style = ParagraphStyle(
            "DocumentHeading",
            parent=styles["Heading2"],
            spaceBefore=12,
            spaceAfter=6,
        )

        def format_inline(text):
            parts = []
            last = 0
            for match in re.finditer(r"\*\*(.+?)\*\*", text):
                parts.append(escape(text[last:match.start()]))
                parts.append("<b>" + escape(match.group(1)) + "</b>")
                last = match.end()
            parts.append(escape(text[last:]))
            return "".join(parts)

        for line in content.splitlines():
            stripped = line.strip()

            if not stripped:
                elements.append(Spacer(1, 8))
                continue

            if re.fullmatch(r"[-*_]{3,}", stripped):
                elements.append(HRFlowable(width="100%", thickness=0.5))
                continue

            heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
            if heading:
                elements.append(
                    Paragraph(format_inline(heading.group(1)), heading_style)
                )
                continue

            bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
            if bullet:
                elements.append(
                    Paragraph("&#8226; " + format_inline(bullet.group(1)), styles["Normal"])
                )
                continue

            elements.append(Paragraph(format_inline(stripped), styles["Normal"]))
            elements.append(Spacer(1, 6))

        pdf.build(elements)
        return buffer.getvalue()

    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Document"

        sheet.append([title])

        for line in content.split("\n"):
            sheet.append([line])

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([title])

    for line in content.split("\n"):
        writer.writerow([line])

    return output.getvalue().encode("utf-8-sig")
