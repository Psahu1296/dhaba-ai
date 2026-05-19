import asyncio
import chromadb
from openai import OpenAI
from config import EMBED_BASE_URL, EMBED_MODEL, EMBED_API_KEY

_embed_client = OpenAI(base_url=EMBED_BASE_URL, api_key=EMBED_API_KEY)
_chroma = chromadb.PersistentClient(path="./chroma_db")
_collection = _chroma.get_or_create_collection("menu")



def _embed(text: str) -> list[float]:
    return _embed_client.embeddings.create(
        model=EMBED_MODEL, input=text
    ).data[0].embedding


def search_menu(query: str, n_results: int = 4) -> list[str]:
    query_embedding = _embed(query)
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )
    return results["documents"][0]


async def search_dishes(query: str, n_results: int = 4) -> dict:
    results = await asyncio.to_thread(search_menu, query, n_results)
    return {"matches": results}
