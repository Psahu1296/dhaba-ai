import json
import asyncio
import chromadb
from openai import OpenAI
from config import EMBED_BASE_URL, EMBED_MODEL, EMBED_API_KEY
from tools.bill_app import login, get_all_dishes

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
    response = _embed_client.embeddings.create(
        model=EMBED_MODEL, input=text
    )
    return response.data[0].embedding


async def embed_menu():
    await login()
    dishes = await get_all_dishes()
    print(f"Fetched {len(dishes)} dishes from Bill-App")

    collection = _chroma.get_or_create_collection("menu")

    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        print(f"Cleared {len(existing['ids'])} old embeddings")

    ids, documents, embeddings, metadatas = [], [], [], []

    for i, dish in enumerate(dishes):
        text = _dish_to_text(dish)
        ids.append(dish.get("name", f"dish_{i}"))
        documents.append(text)
        embeddings.append(_embed(text))
        metadatas.append({
            "name": dish.get("name", ""),
            "category": dish.get("category", ""),
            "type": dish.get("type", ""),
        })
        print(f"  ✓ Embedded: {dish.get('name')}")


    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    print(f"\n✓ Done. {len(dishes)} dishes stored in ChromaDB.")


if __name__ == "__main__":
    asyncio.run(embed_menu())
