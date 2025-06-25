import numpy as np
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_text_from_pdf(file_path):
    import fitz  # PyMuPDF
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
    except Exception as e:
        print(f"[ERROR] Failed to extract PDF text: {e}")
    return text


def extract_text_from_docx(file_path):
    from docx import Document
    text = ""
    try:
        doc = Document(file_path)
        text = "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        print(f"[ERROR] Failed to extract DOCX text: {e}")
    return text


def extract_text_from_txt(file_path):
    text = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read TXT file: {e}")
    return text


def extract_text(file_path, filename):
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif filename.endswith(".txt"):
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def chunk_text(text, max_length=500):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + max_length])
        start += max_length
    return chunks


def generate_embedding(text):
    try:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        return embedding
    except Exception as e:
        print(f"[ERROR] Embedding generation failed: {e}")
        return None


def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return np.dot(vec1, vec2) / (norm1 * norm2)


def search_relevant_chunks(bot, query_embedding, top_k=5):
    from .models import KnowledgeChunk
    if query_embedding is None:
        return []
    chunks = KnowledgeChunk.objects.filter(knowledge_file__bot=bot, embedding__isnull=False)
    similarities = []
    for chunk in chunks:
        sim = cosine_similarity(query_embedding, chunk.embedding)
        similarities.append((sim, chunk))
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in similarities[:top_k]]
