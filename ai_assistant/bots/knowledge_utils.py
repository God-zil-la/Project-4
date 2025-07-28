import numpy as np
import json
from .models import KnowledgeChunk

def generate_embedding(text):
    """
    Fake but consistent 1536-d embedding using hash-based seeding.
    Replace with real OpenAI embeddings in production.
    """
    seed = abs(hash(text.strip().lower())) % (2**32)
    np.random.seed(seed)
    return np.random.rand(1536).tolist()


def cosine_similarity(a, b):
    """
    Cosine similarity between two numeric vectors.
    """
    a, b = np.array(a), np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_relevant_chunks(bot, query, top_k=3):
    """
    Search top_k most relevant chunks for the bot based on cosine similarity.
    """
    query_embedding = generate_embedding(query)
    chunks = KnowledgeChunk.objects.filter(
        knowledge_file__bot=bot
    ).exclude(embedding=None)

    scored_chunks = []
    for chunk in chunks:
        try:
            # Ensure JSON field is interpreted correctly
            embedding = chunk.embedding
            if isinstance(embedding, str):
                embedding = json.loads(embedding)

            score = cosine_similarity(query_embedding, embedding)
            scored_chunks.append((score, chunk))
        except Exception:
            continue  # skip invalid or broken data

    # Sort by score, descending
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Filter top K with optional score threshold
    top_chunks = [chunk.text for score, chunk in scored_chunks[:top_k] if score > 0.1]
    return top_chunks


def render_system_message(bot, knowledge_text):
    return f"""
You are a helpful AI assistant for the bot '{bot.name}'.

Below is verified information uploaded by the user. You must rely on this knowledge when answering. 
If the question is about something mentioned in this knowledge, always prefer it over any other assumptions.

=== START OF KNOWLEDGE ===
{knowledge_text if knowledge_text else '[No relevant knowledge found.]'}
=== END OF KNOWLEDGE ===
""".strip()

