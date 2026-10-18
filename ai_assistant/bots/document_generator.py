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
        # DOCUMENT_WORKBOOK_V1: Build real structured spreadsheets.
        import json
        import re

        specification = json.loads(content)

        if not isinstance(specification, dict):
            raise ValueError("Invalid workbook specification.")

        sheets = specification.get("sheets")

        if not isinstance(sheets, list) or not 1 <= len(sheets) <= 12:
            raise ValueError("Invalid worksheet collection.")

        workbook = Workbook()
        workbook.remove(workbook.active)

        used_names = set()

        for definition in sheets:
            if not isinstance(definition, dict):
                raise ValueError("Invalid worksheet.")

            name = definition.get("name")
            rows = definition.get("rows")

            if (
                not isinstance(name, str)
                or not 1 <= len(name) <= 31
                or any(char in name for char in "[]:*?/\\")
                or name.startswith("'")
                or name.endswith("'")
                or name.casefold() in used_names
            ):
                raise ValueError("Invalid worksheet name.")

            if not isinstance(rows, list) or not 1 <= len(rows) <= 250:
                raise ValueError("Invalid worksheet rows.")

            used_names.add(name.casefold())
            sheet = workbook.create_sheet(name)

            for row in rows:
                if not isinstance(row, list) or len(row) > 30:
                    raise ValueError("Invalid worksheet row.")

                for value in row:
                    if value is not None and not isinstance(
                        value, (str, int, float, bool)
                    ):
                        raise ValueError("Invalid cell value.")

                    if isinstance(value, str):
                        if len(value) > 10000:
                            raise ValueError("Cell value too large.")

                        if value.startswith("="):
                            if re.search(
                                r"(?i)HYPERLINK|WEBSERVICE|DDE|RTD|https?://",
                                value,
                            ):
                                raise ValueError("Unsafe spreadsheet formula.")

                sheet.append(row)

            sheet.freeze_panes = "A2"

            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter

            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(
                    fill_type="solid", fgColor="243B53"
                )

            for column in sheet.columns:
                cells = list(column)
                width = max(
                    len(str(cell.value or "")) for cell in cells[:100]
                )
                letter = get_column_letter(cells[0].column)
                sheet.column_dimensions[letter].width = min(
                    max(width + 3, 12), 45
                )

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([title])

    for line in content.split("\n"):
        writer.writerow([line])

    return output.getvalue().encode("utf-8-sig")
