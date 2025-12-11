from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

import faiss

from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    import openai
except Exception:  # pragma: no cover
    openai = None  # type: ignore


# =============================================================================
# Paths
# =============================================================================
# File lives in /app, so BASE_DIR points to repository root (e.g. /twilio)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "X1_data")
SCRAPED_DIR = os.path.join(DATA_DIR, "business_insider_scrapes")

FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_openai_index")
DOCS_JSON_PATH = os.path.join(DATA_DIR, "documents.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCRAPED_DIR, exist_ok=True)
os.makedirs(FAISS_INDEX_PATH, exist_ok=True)


# =============================================================================
# Defaults - synced with config.py OpenAISettings
# =============================================================================
def _get_embedding_model() -> str:
    """Get embedding model from env or use default."""
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-large").strip()


def _get_chat_model() -> str:
    """Get chat model from env or use default."""
    return os.getenv("SECOND_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")).strip()


EMBEDDING_MODEL_NAME = _get_embedding_model()
FALLBACK_DIM = 3072
DEFAULT_CHAT_MODEL = _get_chat_model()


# =============================================================================
# OpenAI key resolution - integrated with config.py
# =============================================================================
def _get_openai_key() -> Optional[str]:
    """
    Resolve OpenAI API key.

    Priority:
    1) SECOND_OPENAI env var (News/FAISS/RAG - main key for this service)
    2) OPENAI_API_KEY env var (fallback)
    3) app.config.OpenAISettings if available
    """
    # Primary: SECOND_OPENAI for News/FAISS/RAG
    key = os.getenv("SECOND_OPENAI", "").strip()
    if key:
        return key

    # Fallback: OPENAI_API_KEY
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key

    # Last resort: try to get from app config
    try:
        from app.config import OpenAISettings
        settings = OpenAISettings.from_env()
        if settings.api_key:
            return settings.api_key
    except Exception:
        pass

    return None


OPENAI_API_KEY = _get_openai_key()
if not OPENAI_API_KEY:
    logging.warning(
        "❌ Brak klucza OpenAI (SECOND_OPENAI / OPENAI_API_KEY). "
        "FAISS/embeddings nie będą działały, dopóki nie ustawisz klucza."
    )


# =============================================================================
# Embeddings adapter - dynamically uses config values
# =============================================================================
class OpenAIEmbeddings(Embeddings):
    """Embeddings *tylko* przez OpenAI API.

    Jeżeli brakuje klucza lub zapytanie się nie powiedzie,
    rzucamy wyjątek zamiast robić sztuczny fallback.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or _get_embedding_model()
        self.api_key = _get_openai_key()

        if not openai:
            raise RuntimeError("Pakiet openai nie jest zainstalowany – wymagany do embeddings.")
        if not self.api_key:
            raise RuntimeError(
                "Brak klucza OpenAI (SECOND_OPENAI / OPENAI_API_KEY). "
                "Ustaw go w .env zanim zbudujesz indeks FAISS."
            )

        self.client = openai.OpenAI(api_key=self.api_key)

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(model=self.model, input=[text])
        return resp.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in resp.data]


# =============================================================================
# Low-level helpers
# =============================================================================
def chunk_texts(texts: List[str], chunk_size: int = 800, chunk_overlap: int = 100) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    out: List[str] = []
    for t in texts:
        docs = splitter.create_documents([t])
        out.extend([d.page_content for d in docs])
    return out


def build_faiss_from_texts(
    texts: List[str],
    embeddings: OpenAIEmbeddings,
    metadata_source: str,
) -> Optional[FAISS]:
    if not texts:
        return None

    # infer dimension na podstawie prawdziwych embeddingów OpenAI
    sample_vec = embeddings.embed_query(texts[0])
    dim = len(sample_vec)

    index = faiss.IndexFlatL2(dim)

    store = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

    vectors = embeddings.embed_documents(texts)
    documents = [Document(page_content=t, metadata={"source": metadata_source}) for t in texts]
    ids = [os.urandom(16).hex() for _ in documents]

    store.add_documents(documents=documents, embeddings=vectors, ids=ids)

    snapshot = [{"id": _id, "page_content": doc.page_content, "metadata": doc.metadata}
                for _id, doc in zip(ids, documents)]
    with open(DOCS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return store


def save_faiss_index(store: Optional[FAISS], path: str = FAISS_INDEX_PATH) -> None:
    if not store:
        return
    os.makedirs(path, exist_ok=True)
    store.save_local(path)
    logging.info("💾 FAISS index saved -> %s", path)


def load_faiss_index(path: str = FAISS_INDEX_PATH) -> Optional[FAISS]:
    try:
        index_file = os.path.join(path, "index.faiss")
        pkl_file = os.path.join(path, "index.pkl")
        if not (os.path.exists(index_file) and os.path.exists(pkl_file)):
            return None

        embeddings = OpenAIEmbeddings()
        store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
        return store
    except Exception as exc:  # noqa: BLE001
        logging.error("FAISS load error: %s", exc)
        return None


def search_similar_text(store: FAISS, query: str, k: int = 5):
    try:
        return store.similarity_search(query, k=k)
    except Exception as exc:  # noqa: BLE001
        logging.error("FAISS search error: %s", exc)
        return []


def read_category_text_files(category_dir: str = SCRAPED_DIR) -> Dict[str, str]:
    results: Dict[str, str] = {}
    if not os.path.isdir(category_dir):
        return results

    for fn in sorted(os.listdir(category_dir)):
        if not fn.endswith(".txt"):
            continue
        slug = os.path.splitext(fn)[0]
        path = os.path.join(category_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                results[slug] = f.read().strip()
        except Exception as exc:  # noqa: BLE001
            logging.warning("Cannot read %s: %s", path, exc)

    return results


def _format_results(docs) -> List[Dict]:
    formatted: List[Dict] = []
    for doc in docs:
        content = (doc.page_content or "").strip()
        category = "Fragment"

        if content.startswith("[") and "]" in content:
            category = content.split("]")[0][1:]
            content = content.split("]", 1)[1].strip()

        formatted.append(
            {
                "category": category,
                "content": content,
                "metadata": doc.metadata,
            }
        )
    return formatted


def _build_context(docs, max_chars: int = 6000) -> str:
    blocks: List[str] = []
    total = 0

    for i, doc in enumerate(docs, 1):
        text = (doc.page_content or "").strip()
        if not text:
            continue

        if text.startswith("[") and "]" in text:
            text = text.split("]", 1)[1].strip()

        chunk = f"Fragment {i}:\n{text}"
        if total + len(chunk) > max_chars:
            break

        blocks.append(chunk)
        total += len(chunk)

    return "\n\n".join(blocks).strip()


# =============================================================================
# Service - integrated with app.config.py
# =============================================================================
class FAISSService:
    """
    FAISS + OpenAI Embeddings + optional RAG answers.

    Designed to integrate with app.scraper_service outputs.
    Uses config from app.config.OpenAISettings when available.

    Key capabilities:
    - build_index_from_scraped_content({category: text})
    - build_index_from_category_files()
    - load_index()
    - search()
    - answer_query() -> "po ludzku" with OpenAI Chat
    """

    def __init__(self, chat_model: Optional[str] = None) -> None:
        self.embeddings = OpenAIEmbeddings()
        self.vector_store: Optional[FAISS] = None
        self.chat_model = chat_model or _get_chat_model()

        self.api_key = _get_openai_key()
        if openai and self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception:  # pragma: no cover
                self.client = None
        else:
            self.client = None

    # ---------------------------------------------------------------------
    # Index lifecycle
    # ---------------------------------------------------------------------
    def load_index(self, path: str = FAISS_INDEX_PATH) -> bool:
        self.vector_store = load_faiss_index(path)
        if self.vector_store:
            logging.info("📂 FAISS index loaded from %s", path)
            return True
        logging.info("ℹ️ No FAISS index found in %s", path)
        return False

    def get_index_status(self) -> Dict:
        """Zwraca metadane o indeksie FAISS i plikach na dysku."""
        index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
        pkl_file = os.path.join(FAISS_INDEX_PATH, "index.pkl")

        exists = os.path.exists(index_file) and os.path.exists(pkl_file)
        size_bytes = os.path.getsize(index_file) if os.path.exists(index_file) else 0

        docs_snapshot_exists = os.path.exists(DOCS_JSON_PATH)

        return {
            "exists": exists,
            "index_path": FAISS_INDEX_PATH,
            "index_file": index_file,
            "pkl_file": pkl_file,
            "size_bytes": size_bytes,
            "docs_snapshot_exists": docs_snapshot_exists,
        }

    def build_index_from_scraped_content(self, scraped_content: Dict[str, str]) -> bool:
        """
        Build index from {category_name: combined_text}.

        We prefix each category in text to preserve traceability.
        """
        try:
            texts: List[str] = []
            for category, content in scraped_content.items():
                if not content:
                    continue
                if str(content).startswith("❌"):
                    continue
                texts.append(f"[{category}] {content}")

            if not texts:
                logging.warning("No valid content to index.")
                return False

            chunked = chunk_texts(texts)

            store = build_faiss_from_texts(
                chunked,
                embeddings=self.embeddings,
                metadata_source="business_insider_scraper",
            )
            if not store:
                return False

            self.vector_store = store
            save_faiss_index(self.vector_store)
            logging.info("✅ FAISS index built from scraped content.")
            return True

        except Exception as exc:  # noqa: BLE001
            logging.error("Build index error: %s", exc)
            return False

    def build_index_from_category_files(self, category_dir: str = SCRAPED_DIR) -> bool:
        contents = read_category_text_files(category_dir)
        if not contents:
            logging.warning("No category files found in %s", category_dir)
            return False

        return self.build_index_from_scraped_content(contents)

    # ---------------------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------------------
    def search(self, query: str, top_k: int = 5) -> Dict:
        if not query or not query.strip():
            return {"success": False, "error": "Brak zapytania", "results": []}

        if not self.vector_store:
            self.load_index()

        if not self.vector_store:
            return {
                "success": False,
                "error": "Brak FAISS index. Najpierw zbuduj bazę embeddings.",
                "results": [],
            }

        docs = search_similar_text(self.vector_store, query, k=top_k)
        results = _format_results(docs)

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results,
            "search_info": {
                "algorithm": "FAISS + OpenAI embeddings",
                "embedding_model": self.embeddings.model,
            },
        }

    # ---------------------------------------------------------------------
    # RAG answer
    # ---------------------------------------------------------------------
    def answer_query(
        self,
        query: str,
        *,
        top_k: int = 5,
        chat_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict:
        """
        Retrieve top-k fragments and generate a short human-friendly answer.

        If OpenAI Chat is unavailable, uses an extractive fallback.
        Uses self.chat_model (from config) if chat_model not specified.
        """
        # Use instance chat_model if not overridden
        model_to_use = chat_model or self.chat_model
        
        search_payload = self.search(query, top_k=top_k)
        if not search_payload.get("success"):
            return {**search_payload, "answer": search_payload.get("error", "Brak danych"), "llm_used": False}

        if not self.vector_store:
            self.load_index()

        docs = []
        if self.vector_store:
            docs = search_similar_text(self.vector_store, query, k=top_k)

        context = _build_context(docs)
        search_payload["context_preview"] = context

        if not self.client or not context:
            return {
                **search_payload,
                "answer": self._fallback_human_answer(query, search_payload.get("results", [])),
                "llm_used": False,
            }

        sys_msg = system_prompt or (
            "Jesteś analitykiem newsów. Odpowiadasz po polsku, krótko i jasno. "
            "Korzystasz wyłącznie z podanych fragmentów. "
            "Jeśli dane są niepełne, powiedz czego brakuje."
        )

        user_msg = (
            f"Pytanie użytkownika:\n{query}\n\n"
            f"Fragmenty z bazy:\n{context}\n\n"
            "Napisz odpowiedź 'po ludzku' w 4-8 zdaniach. "
            "Jeżeli pasuje, dodaj 3 krótkie wypunktowania z najważniejszymi faktami."
        )

        try:
            resp = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
            )
            answer = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logging.warning("OpenAI chat error: %s", exc)
            answer = self._fallback_human_answer(query, search_payload.get("results", []))

        return {
            **search_payload,
            "answer": answer,
            "llm_used": True,
            "chat_model": model_to_use,
        }

    def _fallback_human_answer(self, query: str, results: List[Dict]) -> str:
        top = results[:3]
        lines: List[str] = []
        lines.append(f"Znalazłem {len(results)} pasujących fragmentów w bazie.")
        lines.append(f"Pytanie: {query}")
        lines.append("")

        for r in top:
            content = (r.get("content") or "").strip()
            category = r.get("category", "Fragment")

            if len(content) > 280:
                content = content[:280].rstrip() + "…"

            lines.append(f"- ({category}) {content}")

        lines.append("")
        lines.append("Jeśli chcesz bardziej precyzyjnej odpowiedzi, zaktualizuj scrapowanie i przebuduj indeks.")
        return "\n".join(lines).strip()
