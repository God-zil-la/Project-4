import re

from dotenv import load_dotenv
from django.template.loader import render_to_string


load_dotenv()


def extract_text_from_pdf(file_obj):
    """
    Extracts text from a PDF file using PyMuPDF.
    Supports both file paths and Django uploaded files.
    """
    import fitz

    text = ""

    try:
        if hasattr(file_obj, "read"):
            file_obj.seek(0)
            pdf_bytes = file_obj.read()
            file_obj.seek(0)

            with fitz.open(
                stream=pdf_bytes,
                filetype="pdf",
            ) as doc:
                for page in doc:
                    text += page.get_text()

        else:
            with fitz.open(file_obj) as doc:
                for page in doc:
                    text += page.get_text()

    except Exception as e:
        print(f"[ERROR] Failed to extract PDF text: {e}")

    return text


def extract_text_from_docx(file_obj):
    """
    Extracts text from a DOCX file using python-docx.
    Supports both file paths and Django uploaded files.
    """
    from docx import Document

    text = ""

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        doc = Document(file_obj)
        text = "\n".join(
            para.text for para in doc.paragraphs
        )

        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

    except Exception as e:
        print(f"[ERROR] Failed to extract DOCX text: {e}")

    return text


def extract_text_from_txt(file_obj):
    """
    Reads text from a plain TXT file.
    Supports file paths and Django uploaded files.
    """
    try:
        if hasattr(file_obj, "read"):
            file_obj.seek(0)
            content = file_obj.read()
            file_obj.seek(0)

            if isinstance(content, bytes):
                return content.decode("utf-8")

            return content

        with open(
            file_obj,
            "r",
            encoding="utf-8",
        ) as file_handle:
            return file_handle.read()

    except Exception as e:
        print(f"[ERROR] Failed to read TXT file: {e}")
        return ""


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