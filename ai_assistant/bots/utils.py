import os
import re
from dotenv import load_dotenv
from django.template.loader import render_to_string


load_dotenv()


def extract_text_from_pdf(file_path):
    """
    Extracts text from a PDF file using PyMuPDF.
    """
    import fitz
    text = ""
    try:
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"[ERROR] Failed to extract PDF text: {e}")
    return text


def extract_text_from_docx(file_path):
    """
    Extracts text from a DOCX file using python-docx.
    """
    from docx import Document
    text = ""
    try:
        doc = Document(file_path)
        text = "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        print(f"[ERROR] Failed to extract DOCX text: {e}")
    return text


def extract_text_from_txt(file_obj):
    """
    Reads text from a plain TXT file. Supports file paths and InMemoryUploadedFile.
    """
    try:
        if hasattr(file_obj, 'read'):
            return file_obj.read().decode('utf-8')
        else:
            with open(file_obj, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read TXT file: {e}")
        return ""


def render_system_message(bot, knowledge_text):
    """
    Renders the system message using the bot's personality and relevant knowledge.
    """
    return render_to_string("system_message_template.txt", {
        "bot": bot,
        "knowledge": knowledge_text
    })
    

def extract_text(file_path, filename):
    """
    Dispatches extraction based on file extension.
    """
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif filename.endswith(".txt"):
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def chunk_text(text, max_length=500, overlap=100):
    """
    Splits text into chunks of up to max_length characters,
    with optional overlap and sentence-aware boundaries.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())

            if overlap > 0 and chunks:
                overlap_text = chunks[-1][-overlap:]
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


