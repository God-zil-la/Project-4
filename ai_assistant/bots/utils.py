import os
import re
import numpy as np
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")


#######################
# TEXT EXTRACTION
#######################

def extract_text_from_pdf(file_path):
    """
    Extracts text from a PDF file using PyMuPDF.
    """
    import fitz  # PyMuPDF
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


def extract_text_from_txt(file_path):
    """
    Reads text from a plain TXT file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read TXT file: {e}")
        return ""


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


#######################
# CHUNKING
#######################

def chunk_text(text, max_length=500, overlap=100):
    """
    Splits text into chunks of up to max_length characters,
    with optional overlap and sentence-aware boundaries.
    """
    # Split on sentence-like boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # Start new chunk with overlap from previous
            if overlap > 0 and chunks:
                overlap_text = chunks[-1][-overlap:]
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


#######################
# EMBEDDING
#######################

def generate_embedding(text):
    """
    Calls OpenAI to generate an embedding for a text chunk.
    """
    try:
        response = openai.Embedding.create(
            input=text,
            model="text-embedding-ada-002"  # Updated model name
        )
        return response['data'][0]['embedding']
    except Exception as e:
        print(f"[ERROR] Embedding generation failed: {e}")
        return None


#######################
# SIMILARITY
#######################

def cosine_similarity(vec1, vec2):
    """
    Computes cosine similarity between two vectors.
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return np.dot(vec1, vec2) / (norm1 * norm2)


#######################
# RETRIEVAL
#######################

def search_relevant_chunks(bot, query_embedding, top_k=5):
    """
    Retrieves the top_k most relevant KnowledgeChunks for a bot
    given a query embedding.
    """
    from .models import KnowledgeChunk

    if query_embedding is None:
        return []

    # Fetch all chunks with embeddings for this bot
    chunks = KnowledgeChunk.objects.filter(
        knowledge_file__bot=bot,
        embedding__isnull=False
    )

    similarities = []
    for chunk in chunks:
        sim = cosine_similarity(query_embedding, chunk.embedding)
        similarities.append((sim, chunk))

    # Sort by similarity descending
    similarities.sort(key=lambda x: x[0], reverse=True)

    return [chunk for _, chunk in similarities[:top_k]]
