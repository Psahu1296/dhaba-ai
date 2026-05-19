import json
import logging
import asyncio
import chromadb
from openai import OpenAI
from config import EMBED_BASE_URL, EMBED_MODEL, EMBED_API_KEY
from tools.bill_app import login, get_all_dishes

logger = logging.getLogger(__name__)

_embed_client = OpenAI(base_url=EMBED_BASE_URL, api_key=EMBED_API_KEY)
_chroma = chromadb.PersistentClient(path="./chroma_db")


def _dish_to_text(dish: dict) -> str:
    name = dish.get("name", "")
    category = dish.get("category", "")
    dish_type = dish.get("type", "")
    description = dish.get("description", "")

    variants_raw = dish.get("variants", "[]")
    if isinstance(variants_raw, str):
        variants = json.loads(variants_raw)
    else:
        variants = variants_raw

    pricing = ", ".join(
        f"{v.get('size', '')}: ₹{v.get('price', '')}" for v in variants
    )

    return f"{name} | {dish_type} | {category} | {pricing} | {description}"


def _embed(text: str) -> list[float]:
    response = _embed_client.embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding


async def embed_menu(force: bool = False):
    await login()
    dishes = await get_all_dishes()

    collection = _chroma.get_or_create_collection("menu")

    # Skip re-embedding if collection already has same number of dishes
    if not force and collection.count() == len(dishes):
        logger.info(f"Menu already embedded ({len(dishes)} dishes) — skipping")
        return

    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        logger.info(f"Cleared {len(existing['ids'])} old menu embeddings")

    ids, documents, metadatas = [], [], []

    for i, dish in enumerate(dishes):
        ids.append(dish.get("name", f"dish_{i}"))
        documents.append(_dish_to_text(dish))
        metadatas.append({
            "name": dish.get("name", ""),
            "category": dish.get("category", ""),
            "type": dish.get("type", ""),
        })

    # Batch all dishes in one API call instead of 48 sequential calls
    response = await asyncio.to_thread(
        lambda: _embed_client.embeddings.create(model=EMBED_MODEL, input=documents)
    )
    embeddings = [item.embedding for item in response.data]

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    logger.info(f"Menu embedded — {len(dishes)} dishes stored in ChromaDB")


if __name__ == "__main__":
    asyncio.run(embed_menu(force=True))
