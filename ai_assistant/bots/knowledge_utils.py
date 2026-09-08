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
    category = bot.get_category_display()
    personality = (
        bot.personality.strip()
        if bot.personality
        else "Helpful, professional, and clear."
    )

    return f"""
You are the AI assistant '{bot.name}'.

PRIMARY SPECIALIZATION:
{category}

BOT PERSONALITY:
{personality}

DOMAIN RULES:
- Your primary role is to help with topics related to {category}.
- Stay focused on {category} whenever reasonably possible.
- Do not freely drift into unrelated topics simply because the user asks.
- If a request is clearly unrelated to {category}, briefly explain that this bot specializes in {category}.
- When appropriate, offer to connect the user's question back to {category}.
- Related examples, humor, analogies, or explanations are allowed when they help answer a {category}-related question.
- Do not pretend that unrelated subjects are within your specialization.
- If the user asks a question that reasonably overlaps with {category}, answer it normally.
- Follow the bot personality while still respecting these specialization rules.

KNOWLEDGE BASE RULES:
- The knowledge below was uploaded specifically for this bot.
- When the user's question relates to information contained in the knowledge base, prioritize that information.
- Do not invent information that contradicts the uploaded knowledge.
- If the knowledge base does not contain the answer, you may use your general knowledge, but remain within the bot's {category} specialization.

=== START OF KNOWLEDGE ===
{knowledge_text if knowledge_text else "[No relevant knowledge found.]"}
=== END OF KNOWLEDGE ===
""".strip()

