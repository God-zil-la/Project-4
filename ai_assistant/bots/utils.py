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
    Splits text into chunks of up to max_length characters,
    with optional overlap and sentence-aware boundaries.
    """
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if (
            len(current_chunk)
            + len(sentence)
            + 1
            <= max_length
        ):
            current_chunk += " " + sentence

        else:
            if current_chunk:
                chunks.append(
                    current_chunk.strip()
                )

            if overlap > 0 and chunks:
                overlap_text = (
                    chunks[-1][-overlap:]
                )

                current_chunk = (
                    overlap_text
                    + " "
                    + sentence
                )

            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(
            current_chunk.strip()
        )

    return chunks