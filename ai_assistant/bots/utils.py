import re

from dotenv import load_dotenv
from django.template.loader import render_to_string


load_dotenv()


def validate_extracted_text(text):
    from django.conf import settings
    from .knowledge_errors import KnowledgeProcessingError
    if len(text) > settings.KNOWLEDGE_MAX_TEXT_CHARS:
        raise KnowledgeProcessingError(
            "Document contains too much text to process.", "processing_limit", 413
        )
    if not text.strip():
        raise KnowledgeProcessingError(
            "No readable text found. Scanned PDFs need a text layer; OCR is not supported.",
            "empty_content",
        )
    return text


def _bounded_parts(parts):
    from django.conf import settings
    from .knowledge_errors import KnowledgeProcessingError
    result, length = [], 0
    for part in parts:
        length += len(part) + (1 if result else 0)
        if length > settings.KNOWLEDGE_MAX_TEXT_CHARS:
            raise KnowledgeProcessingError(
                "Document contains too much text to process.", "processing_limit", 413
            )
        result.append(part)
    return validate_extracted_text("\n".join(result))


def extract_text_from_pdf(file_obj):
    import fitz
    from django.conf import settings
    from .knowledge_errors import KnowledgeProcessingError
    try:
        if hasattr(file_obj, "read"):
            file_obj.seek(0)
            doc = fitz.open(stream=file_obj.read(), filetype="pdf")
        else:
            doc = fitz.open(file_obj)
        with doc:
            if doc.needs_pass:
                raise KnowledgeProcessingError(
                    "Password-protected PDFs cannot be processed.", "encrypted_document"
                )
            if len(doc) > settings.KNOWLEDGE_MAX_PDF_PAGES:
                raise KnowledgeProcessingError(
                    "PDF has too many pages to process.", "processing_limit", 413
                )
            return _bounded_parts(page.get_text() for page in doc)
    except KnowledgeProcessingError:
        raise
    except Exception as error:
        raise KnowledgeProcessingError(
            "Could not read PDF. Check that the file is a valid PDF.", "extraction_failed"
        ) from error
    finally:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)


def extract_text_from_docx(file_obj):
    from zipfile import ZipFile
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from django.conf import settings
    from .knowledge_errors import KnowledgeProcessingError

    def blocks(parent, element):
        for child in element:
            if child.tag.endswith("}p"):
                yield Paragraph(child, parent).text
            elif child.tag.endswith("}tbl"):
                for row in Table(child, parent).rows:
                    cells, seen = [], set()
                    for cell in row.cells:
                        if cell._tc in seen:
                            continue
                        seen.add(cell._tc)
                        cells.append(" ".join(blocks(cell, cell._tc)))
                    yield " | ".join(cells)

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        with ZipFile(file_obj) as archive:
            entries = archive.infolist()
            if (len(entries) > 10_000 or
                    sum(item.file_size for item in entries) > settings.KNOWLEDGE_MAX_DOCX_EXPANDED_BYTES):
                raise KnowledgeProcessingError(
                    "DOCX expands beyond the processing limit.", "processing_limit", 413
                )
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        doc = Document(file_obj)
        return _bounded_parts(blocks(doc, doc.element.body))
    except KnowledgeProcessingError:
        raise
    except Exception as error:
        raise KnowledgeProcessingError(
            "Could not read DOCX. Check that the file is a valid Word document.",
            "extraction_failed",
        ) from error
    finally:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)


def extract_text_from_txt(file_obj):
    from .knowledge_errors import KnowledgeProcessingError
    try:
        if hasattr(file_obj, "read"):
            file_obj.seek(0)
            content = file_obj.read()
            text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        else:
            with open(file_obj, encoding="utf-8-sig") as handle:
                text = handle.read()
        return validate_extracted_text(text)
    except KnowledgeProcessingError:
        raise
    except Exception as error:
        raise KnowledgeProcessingError(
            "Could not read TXT. Save the file as UTF-8 text.", "extraction_failed"
        ) from error
    finally:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)


def render_system_message(bot, knowledge_text):
    """
    Renders the system message using the bot's personality
    and relevant knowledge.
    """
    return render_to_string(
        "system_message_template.txt",
        {
            "bot": bot,
            "knowledge": knowledge_text,
        },
    )


def extract_text(file_obj, filename):
    """
    Dispatches extraction based on file extension.
    """
    filename = filename.lower()

    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_obj)

    if filename.endswith(".docx"):
        return extract_text_from_docx(file_obj)

    if filename.endswith(".txt"):
        return extract_text_from_txt(file_obj)

    raise ValueError(
        f"Unsupported file type: {filename}"
    )


def chunk_text(
    text,
    max_length=500,
    overlap=100,
):
    """
    Split text into bounded chunks with overlap.

    Chunks prefer natural boundaries such as paragraphs,
    sentences, and spaces, but will hard-split long content
    when necessary.

    Every returned chunk is guaranteed to be no longer than
    max_length characters.
    """
    if not text:
        return []

    if max_length <= 0:
        raise ValueError(
            "max_length must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= max_length:
        raise ValueError(
            "overlap must be smaller than max_length."
        )

    text = str(text).replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).strip()

    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        hard_end = min(
            start + max_length,
            text_length,
        )

        end = hard_end

        if hard_end < text_length:
            window = text[
                start:hard_end
            ]

            minimum_boundary = int(
                max_length * 0.6
            )

            boundary_positions = []

            paragraph_position = (
                window.rfind("\n\n")
            )

            if paragraph_position >= minimum_boundary:
                boundary_positions.append(
                    paragraph_position + 2
                )

            newline_position = (
                window.rfind("\n")
            )

            if newline_position >= minimum_boundary:
                boundary_positions.append(
                    newline_position + 1
                )

            sentence_matches = list(
                re.finditer(
                    r"[.!?](?:\s|$)",
                    window,
                )
            )

            for match in sentence_matches:
                position = match.end()

                if position >= minimum_boundary:
                    boundary_positions.append(
                        position
                    )

            space_position = (
                window.rfind(" ")
            )

            if space_position >= minimum_boundary:
                boundary_positions.append(
                    space_position + 1
                )

            if boundary_positions:
                end = start + max(
                    boundary_positions
                )

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        next_start = max(
            end - overlap,
            start + 1,
        )

        while (
            next_start < text_length
            and text[next_start].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks
