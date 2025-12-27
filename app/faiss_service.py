from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import faiss

from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    import openai
except Exception:  # pragma: no cover
    openai = None  # type: ignore


logger = logging.getLogger(__name__)


# =============================================================================
# Paths
# =============================================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "X1_data")
SCRAPED_DIR = os.path.join(DATA_DIR, "business_insider_scrapes")

FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_openai_index")

# Canonical input (recommended)
ARTICLES_JSONL_PATH = os.path.join(DATA_DIR, "articles.jsonl")

# Chunk snapshot used to build the index
DOCS_JSONL_PATH = os.path.join(DATA_DIR, "documents.jsonl")
DOCS_JSON_PATH = os.path.join(DATA_DIR, "documents.json")  # legacy/debug

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCRAPED_DIR, exist_ok=True)
os.makedirs(FAISS_INDEX_PATH, exist_ok=True)


# =============================================================================
# Defaults (env-tunable)
# =============================================================================
def _get_embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-large").strip()


def _get_chat_model() -> str:
    # Prefer runtime override stored in app_settings (when running inside Flask).
    db_override = _get_chat_model_from_db()
    if db_override:
        return db_override
    return os.getenv("SECOND_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")).strip()


def _get_chat_model_from_db() -> Optional[str]:
    try:
        from flask import current_app  # type: ignore
        from .database import get_app_setting  # type: ignore

        if not current_app:
            return None
        value = get_app_setting("rag_chat_model")
        return value.strip() if value else None
    except Exception:
        return None


def _get_embed_batch_size() -> int:
    try:
        return int(os.getenv("EMBED_BATCH_SIZE", "128"))
    except Exception:
        return 128


def _get_chunk_params() -> Tuple[int, int]:
    try:
        chunk_size = int(os.getenv("CHUNK_SIZE", "900"))
    except Exception:
        chunk_size = 900
    try:
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
    except Exception:
        chunk_overlap = 120
    return chunk_size, chunk_overlap


def _get_context_max_chars() -> int:
    # dla "all categories" ustaw większy limit, bo kontekst rośnie liniowo z liczbą kategorii
    try:
        return int(os.getenv("RAG_CONTEXT_MAX_CHARS", "18000"))
    except Exception:
        return 18000


# =============================================================================
# OpenAI key resolution (matches your conventions)
# =============================================================================
def _get_openai_key() -> Optional[str]:
    # 1) primary key for this module
    key = os.getenv("SECOND_OPENAI", "").strip()
    if key:
        return key

    # 2) fallback
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key

    # 3) app config fallback
    try:
        from app.config import OpenAISettings  # type: ignore

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
# Embedding Cache (LRU with TTL)
# =============================================================================
class EmbeddingCache:
    """
    Thread-safe LRU cache for embeddings with TTL.
    
    Reduces API calls for frequently queried texts.
    Cache key is hash of text + model to handle model changes.
    """
    
    __slots__ = ("_cache", "_lock", "_max_size", "_ttl")
    
    def __init__(self, max_size: int = 10000, ttl_seconds: float = 3600.0):
        self._cache: Dict[str, Tuple[List[float], float]] = {}
        self._lock = __import__("threading").RLock()
        self._max_size = max_size
        self._ttl = ttl_seconds
    
    def _make_key(self, text: str, model: str) -> str:
        import hashlib
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:32]
    
    def get(self, text: str, model: str) -> Optional[List[float]]:
        key = self._make_key(text, model)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            embedding, expires_at = entry
            if __import__("time").time() > expires_at:
                del self._cache[key]
                return None
            return embedding
    
    def set(self, text: str, model: str, embedding: List[float]) -> None:
        key = self._make_key(text, model)
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entries (simple FIFO for now)
                keys_to_remove = list(self._cache.keys())[:self._max_size // 10]
                for k in keys_to_remove:
                    del self._cache[k]
            self._cache[key] = (embedding, __import__("time").time() + self._ttl)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
    
    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)


# Global embedding cache
_embedding_cache = EmbeddingCache()


# =============================================================================
# Embeddings adapter (batched with caching)
# =============================================================================
class OpenAIEmbeddings(Embeddings):
    """
    OpenAI Embeddings adapter with caching and batching.
    
    Features:
    - LRU cache with TTL for repeated queries
    - Batched API calls for document embedding
    - Automatic retry on rate limits
    """

    def __init__(self, model: Optional[str] = None, use_cache: bool = True):
        self.model = model or _get_embedding_model()
        self.api_key = _get_openai_key()
        self.batch_size = _get_embed_batch_size()
        self.use_cache = use_cache

        if not openai:
            raise RuntimeError("Pakiet openai nie jest zainstalowany – wymagany do embeddings.")
        if not self.api_key:
            raise RuntimeError(
                "Brak klucza OpenAI (SECOND_OPENAI / OPENAI_API_KEY). "
                "Ustaw go w .env zanim zbudujesz indeks FAISS."
            )

        self.client = openai.OpenAI(api_key=self.api_key)

    def embed_query(self, text: str) -> List[float]:
        """Embed single query with cache support."""
        # Check cache first
        if self.use_cache:
            cached = _embedding_cache.get(text, self.model)
            if cached is not None:
                logger.debug("Embedding cache hit for query")
                return cached
        
        resp = self.client.embeddings.create(model=self.model, input=[text])
        embedding = resp.data[0].embedding
        
        # Cache the result
        if self.use_cache:
            _embedding_cache.set(text, self.model, embedding)
        
        return embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents with batching and partial cache lookup."""
        if not texts:
            return []

        out: List[List[float]] = []
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []
        
        # Check cache for each text
        if self.use_cache:
            for i, text in enumerate(texts):
                cached = _embedding_cache.get(text, self.model)
                if cached is not None:
                    out.append(cached)
                else:
                    out.append([])  # Placeholder
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))
            out = [[] for _ in texts]
        
        # Batch embed uncached texts
        if uncached_texts:
            bs = max(1, int(self.batch_size))
            batch_embeddings: List[List[float]] = []

            for i in range(0, len(uncached_texts), bs):
                batch = uncached_texts[i : i + bs]
                resp = self.client.embeddings.create(model=self.model, input=batch)
                batch_embeddings.extend([item.embedding for item in resp.data])
            
            # Fill in uncached results and update cache
            for idx, embedding in zip(uncached_indices, batch_embeddings):
                out[idx] = embedding
                if self.use_cache:
                    _embedding_cache.set(uncached_texts[uncached_indices.index(idx)], self.model, embedding)

        return out


# =============================================================================
# IO helpers
# =============================================================================
def read_articles_jsonl(path: str = ARTICLES_JSONL_PATH) -> List[Dict]:
    """Read canonical articles.jsonl: 1 line = 1 article record."""
    articles: List[Dict] = []
    if not os.path.exists(path):
        return articles

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    continue
                if not rec.get("url") or not rec.get("text"):
                    continue
                articles.append(rec)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Cannot read %s: %s", path, exc)

    return articles


def read_article_json_files(category_dir: str = SCRAPED_DIR) -> List[Dict]:
    """Fallback: read per-category *.json produced by ScraperService (list of articles)."""
    articles: List[Dict] = []
    if not os.path.isdir(category_dir):
        return articles

    for fn in sorted(os.listdir(category_dir)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(category_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    if not item.get("url") or not item.get("text"):
                        continue
                    articles.append(item)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Cannot read %s: %s", path, exc)

    return articles


def read_category_text_files(category_dir: str = SCRAPED_DIR) -> Dict[str, str]:
    """Legacy fallback: read per-category *.txt (slug -> combined text)."""
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


# =============================================================================
# Chunking + IDs
# =============================================================================
def _sha1(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()


def _chunk_id(key: str, chunk_index: int, chunk_text: str) -> str:
    """
    Deterministic ID that changes if the chunk content changes.
    key:
      - url for articles
      - "category:<name>" for legacy category blobs
    """
    ch = _sha1(chunk_text)
    raw = f"{key}|{chunk_index}|{ch}"
    return _sha1(raw)


def _embed_text_for_doc(doc: Document) -> str:
    """
    This is crucial:
    We embed chunk with metadata injected, so category/title become searchable.
    """
    md = doc.metadata or {}
    cat = (md.get("category") or "").strip()
    title = (md.get("title") or "").strip()
    chunk = (doc.page_content or "").strip()
    return f"[{cat}] {title}\n{chunk}".strip()


def chunk_articles_to_documents(
    articles: List[Dict],
    *,
    chunk_size: int,
    chunk_overlap: int,
    source: str,
) -> Tuple[List[Document], List[str]]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Dedup by URL: keep latest scraped_at if present (ISO Z compares lexicographically OK)
    by_url: Dict[str, Dict] = {}
    for art in articles:
        url = str(art.get("url", "")).strip()
        if not url:
            continue
        prev = by_url.get(url)
        if not prev:
            by_url[url] = art
            continue
        if str(art.get("scraped_at", "")) > str(prev.get("scraped_at", "")):
            by_url[url] = art

    docs: List[Document] = []
    ids: List[str] = []

    for art in by_url.values():
        url = str(art.get("url", "")).strip()
        title = str(art.get("title", "")).strip()
        text = str(art.get("text", "")).strip()
        category = str(art.get("category", "")).strip() or "unknown"
        scraped_at = str(art.get("scraped_at", "")).strip()
        content_hash = str(art.get("content_hash", "")).strip()

        if not url or not text:
            continue

        chunks = splitter.split_text(text)
        for idx, chunk in enumerate(chunks):
            meta = {
                "source": source,
                "url": url,
                "title": title,
                "category": category,
                "scraped_at": scraped_at,
                "content_hash": content_hash,
                "chunk_index": idx,
                "chunk_hash": _sha1(chunk),
                "chunk_len": len(chunk),
            }
            docs.append(Document(page_content=chunk, metadata=meta))
            ids.append(_chunk_id(url, idx, chunk))

    return docs, ids


# =============================================================================
# Snapshot writers
# =============================================================================
def _write_documents_snapshot(documents: List[Document], ids: List[str]) -> None:
    """
    documents.jsonl (1 line = 1 chunk) with required fields:
      id, url, title, text, chunk_index
    """
    try:
        with open(DOCS_JSONL_PATH, "w", encoding="utf-8") as f:
            for _id, doc in zip(ids, documents):
                md = doc.metadata or {}
                rec = {
                    # required:
                    "id": _id,
                    "url": md.get("url", ""),
                    "title": md.get("title", ""),
                    "text": doc.page_content,
                    "chunk_index": md.get("chunk_index", 0),
                    # extra:
                    "category": md.get("category", ""),
                    "scraped_at": md.get("scraped_at", ""),
                    "source": md.get("source", ""),
                    "content_hash": md.get("content_hash", ""),
                    "chunk_hash": md.get("chunk_hash", ""),
                    "chunk_len": md.get("chunk_len", 0),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        legacy = [{"id": _id, "page_content": d.page_content, "metadata": d.metadata} for _id, d in zip(ids, documents)]
        with open(DOCS_JSON_PATH, "w", encoding="utf-8") as f2:
            json.dump(legacy, f2, ensure_ascii=False, indent=2)

    except Exception as exc:  # noqa: BLE001
        logging.warning("Cannot write documents snapshot: %s", exc)


# =============================================================================
# FAISS build/save/load
# =============================================================================
def build_faiss_store_from_documents(
    documents: List[Document],
    embeddings: OpenAIEmbeddings,
) -> Optional[FAISS]:
    if not documents:
        return None

    # Compute embeddings on injected-metadata text
    embed_texts: List[str] = [_embed_text_for_doc(d) for d in documents]
    if not embed_texts:
        return None

    # infer dim from real embedding
    dim = len(embeddings.embed_query(embed_texts[0]))
    index = faiss.IndexFlatL2(dim)

    store = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

    # Deterministic IDs aligned with documents
    ids: List[str] = []
    for d in documents:
        md = d.metadata or {}
        url = str(md.get("url", "")).strip()
        ci = int(md.get("chunk_index", 0))
        key = url or f"category:{md.get('category', '')}"
        ids.append(_chunk_id(key, ci, (d.page_content or "").strip()))

    # Preferred path: add_documents with explicit vectors (keeps doc.page_content == raw chunk)
    vectors = embeddings.embed_documents(embed_texts)

    try:
        store.add_documents(documents=documents, embeddings=vectors, ids=ids)  # type: ignore[arg-type]
    except TypeError:
        # Fallback for older langchain versions: use add_texts().
        # In this fallback, docstore will store embed_texts as page_content;
        # to keep raw chunk accessible, we store it in metadata["raw_text"].
        metadatas = []
        for d in documents:
            md = dict(d.metadata or {})
            md["raw_text"] = d.page_content
            metadatas.append(md)
        store.add_texts(texts=embed_texts, metadatas=metadatas, ids=ids)

    _write_documents_snapshot(documents, ids)
    return store


def save_faiss_index(store: Optional[FAISS], path: str) -> None:
    if not store:
        return
    os.makedirs(path, exist_ok=True)
    store.save_local(path)
    logging.info("💾 FAISS index saved -> %s", path)


def load_faiss_index(path: str) -> Optional[FAISS]:
    try:
        index_file = os.path.join(path, "index.faiss")
        pkl_file = os.path.join(path, "index.pkl")
        if not (os.path.exists(index_file) and os.path.exists(pkl_file)):
            return None

        embeddings = OpenAIEmbeddings()
        return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    except Exception as exc:  # noqa: BLE001
        logging.error("FAISS load error: %s", exc)
        return None


def search_similar_text(store: FAISS, query: str, k: int = 5):
    try:
        return store.similarity_search(query, k=k)
    except Exception as exc:  # noqa: BLE001
        logging.error("FAISS search error: %s", exc)
        return []


# =============================================================================
# Formatting/context
# =============================================================================
def _doc_effective_text(doc: Document) -> str:
    """
    If we had to fallback to add_texts(), the stored page_content can be embed_text.
    Prefer raw_text in metadata if present.
    """
    md = doc.metadata or {}
    raw = md.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    text = (doc.page_content or "").strip()
    # If it starts with "[cat]" prefix, try stripping it safely
    if text.startswith("[") and "]" in text:
        after = text.split("]", 1)[1].strip()
        if after:
            return after
    return text


def _format_results(docs) -> List[Dict]:
    formatted: List[Dict] = []
    for doc in docs:
        md = doc.metadata or {}
        formatted.append(
            {
                "category": md.get("category", "Fragment"),
                "title": md.get("title", ""),
                "url": md.get("url", ""),
                "chunk_index": md.get("chunk_index", 0),
                "content": _doc_effective_text(doc),
                "metadata": md,
            }
        )
    return formatted


def _build_context(docs, max_chars: int) -> str:
    blocks: List[str] = []
    total = 0

    for i, doc in enumerate(docs, 1):
        text = _doc_effective_text(doc)
        if not text:
            continue

        md = doc.metadata or {}
        title = md.get("title", "") or "bez tytułu"
        url = md.get("url", "")
        cat = md.get("category", "")
        ci = md.get("chunk_index", 0)

        header = f"Fragment {i} (cat={cat}, chunk={ci})\nTytuł: {title}\nURL: {url}\n"
        chunk = header + text

        if total + len(chunk) > max_chars:
            break

        blocks.append(chunk)
        total += len(chunk)

    return "\n\n".join(blocks).strip()


def _build_category_contexts(docs: List[Document], max_chars_total: int) -> Dict[str, str]:
    """
    Build per-category contexts so the LLM can reason about each category separately.

    The available character budget is split across categories to keep the final prompt bounded.
    """
    by_cat: Dict[str, List[Document]] = {}
    for doc in docs:
        md = doc.metadata or {}
        cat = (md.get("category") or "Fragment").strip() or "Fragment"
        by_cat.setdefault(cat, []).append(doc)

    if not by_cat:
        return {}

    cat_count = max(1, len(by_cat))
    max_per_cat = max_chars_total // cat_count if max_chars_total else 0
    # Provide a sensible floor to avoid starving categories with very small budgets
    max_per_cat = max(max_per_cat, 600)
    contexts: Dict[str, str] = {}

    for cat in sorted(by_cat):
        cat_docs = by_cat[cat]
        contexts[cat] = _build_context(cat_docs, max_chars=min(max_chars_total, max_per_cat))

    return contexts


# =============================================================================
# Service
# =============================================================================
class FAISSService:
    """
    FAISS + OpenAI Embeddings + optional RAG answers.

    - build_index_from_articles_jsonl(): canonical (recommended)
    - build_index_from_article_json_files(): fallback
    - build_index_from_scraped_content(): legacy fallback

    New capabilities:
    - list_categories()
    - search_all_categories() -> retrieval with category coverage
    - answer_query_all_categories() -> RAG summary across all categories
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
        index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
        pkl_file = os.path.join(FAISS_INDEX_PATH, "index.pkl")
        exists = os.path.exists(index_file) and os.path.exists(pkl_file)
        size_bytes = os.path.getsize(index_file) if os.path.exists(index_file) else 0

        return {
            "exists": exists,
            "index_path": FAISS_INDEX_PATH,
            "index_file": index_file,
            "pkl_file": pkl_file,
            "size_bytes": size_bytes,
            "articles_jsonl_exists": os.path.exists(ARTICLES_JSONL_PATH),
            "articles_jsonl_path": ARTICLES_JSONL_PATH,
            "docs_jsonl_exists": os.path.exists(DOCS_JSONL_PATH),
            "docs_jsonl_path": DOCS_JSONL_PATH,
        }

    # ---------------------------------------------------------------------
    # Build
    # ---------------------------------------------------------------------
    def build_index_from_articles_jsonl(self, path: str = ARTICLES_JSONL_PATH) -> bool:
        try:
            articles = read_articles_jsonl(path)
            if not articles:
                logging.warning("No articles found in %s", path)
                return False

            chunk_size, chunk_overlap = _get_chunk_params()
            docs, _ = chunk_articles_to_documents(
                articles,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source="business_insider_scraper",
            )
            if not docs:
                logging.warning("No documents after chunking.")
                return False

            store = build_faiss_store_from_documents(docs, embeddings=self.embeddings)
            if not store:
                return False

            self.vector_store = store
            save_faiss_index(self.vector_store, FAISS_INDEX_PATH)
            logging.info("✅ FAISS index built from articles.jsonl (per-article chunks).")
            return True

        except Exception as exc:  # noqa: BLE001
            logging.error("Build index (articles jsonl) error: %s", exc)
            return False

    def build_index_from_article_json_files(self, category_dir: str = SCRAPED_DIR) -> bool:
        try:
            articles = read_article_json_files(category_dir)
            if not articles:
                logging.warning("No article JSON files found in %s", category_dir)
                return False

            chunk_size, chunk_overlap = _get_chunk_params()
            docs, _ = chunk_articles_to_documents(
                articles,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source="business_insider_scraper",
            )
            if not docs:
                logging.warning("No documents after chunking.")
                return False

            store = build_faiss_store_from_documents(docs, embeddings=self.embeddings)
            if not store:
                return False

            self.vector_store = store
            save_faiss_index(self.vector_store, FAISS_INDEX_PATH)
            logging.info("✅ FAISS index built from article JSON files (per-article chunks).")
            return True

        except Exception as exc:  # noqa: BLE001
            logging.error("Build index (article json) error: %s", exc)
            return False

    def build_index_from_scraped_content(self, scraped_content: Dict[str, str]) -> bool:
        """
        Legacy fallback: {category: combined_text}
        """
        try:
            texts: List[str] = []
            metas: List[Dict] = []

            for category, content in scraped_content.items():
                if not content:
                    continue
                if str(content).startswith("❌"):
                    continue

                texts.append(str(content))
                metas.append(
                    {
                        "source": "business_insider_scraper",
                        "url": "",
                        "title": "",
                        "category": category,
                        "scraped_at": "",
                        "content_hash": "",
                        "chunk_index": 0,
                    }
                )

            if not texts:
                logging.warning("No valid content to index.")
                return False

            chunk_size, chunk_overlap = _get_chunk_params()
            splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            docs: List[Document] = []
            ids: List[str] = []

            for meta, t in zip(metas, texts):
                parts = splitter.split_text(t)
                for idx, p in enumerate(parts):
                    m = dict(meta)
                    m["chunk_index"] = idx
                    docs.append(Document(page_content=p, metadata=m))
                    ids.append(_chunk_id(f"category:{m['category']}", idx, p))

            store = build_faiss_store_from_documents(docs, embeddings=self.embeddings)
            if not store:
                return False

            self.vector_store = store
            save_faiss_index(self.vector_store, FAISS_INDEX_PATH)
            logging.info("✅ FAISS index built from scraped content (legacy fallback).")
            return True

        except Exception as exc:  # noqa: BLE001
            logging.error("Build index error: %s", exc)
            return False

    def build_index_from_category_files(self, category_dir: str = SCRAPED_DIR) -> bool:
        """
        Convenience:
        1) articles.jsonl
        2) per-category *.json
        3) per-category *.txt (legacy)
        """
        if os.path.exists(ARTICLES_JSONL_PATH):
            if self.build_index_from_articles_jsonl(ARTICLES_JSONL_PATH):
                return True

        if self.build_index_from_article_json_files(category_dir):
            return True

        contents = read_category_text_files(category_dir)
        if contents:
            return self.build_index_from_scraped_content(contents)

        logging.warning("No category files found in %s", category_dir)
        return False

    # ---------------------------------------------------------------------
    # Categories (for coverage retrieval)
    # ---------------------------------------------------------------------
    def list_categories(self) -> List[str]:
        """
        Prefer canonical articles.jsonl; fallback to scanning loaded vectorstore docstore.
        """
        cats = set()

        if os.path.exists(ARTICLES_JSONL_PATH):
            try:
                for rec in read_articles_jsonl(ARTICLES_JSONL_PATH):
                    c = str(rec.get("category", "")).strip()
                    if c:
                        cats.add(c)
            except Exception:
                pass

        if cats:
            return sorted(cats)

        # Fallback: scan docstore if index loaded
        if not self.vector_store:
            self.load_index()

        vs = self.vector_store
        if not vs:
            return []

        try:
            ds = getattr(vs, "docstore", None)
            dsdict = getattr(ds, "_dict", None)
            if isinstance(dsdict, dict):
                for d in dsdict.values():
                    md = getattr(d, "metadata", {}) or {}
                    c = str(md.get("category", "")).strip()
                    if c:
                        cats.add(c)
        except Exception:
            pass

        return sorted(cats)

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
                "chunks_snapshot_jsonl": DOCS_JSONL_PATH,
            },
        }

    def search_all_categories(
        self,
        query: str,
        *,
        per_category_k: int = 2,
        fetch_k: int = 50,
        mmr_lambda: float = 0.5,
    ) -> List[Document]:
        """
        Category-coverage retrieval:
        For each category, retrieve top chunks for that category.
        This makes "all categories overview" reliable.

        per_category_k: how many chunks per category
        fetch_k: internal candidate pool for MMR (if available)
        
        GWARANCJA: Dla każdej kategorii zwraca dokumenty TYLKO z tej kategorii.
        """
        if not query or not query.strip():
            return []

        if not self.vector_store:
            self.load_index()
        if not self.vector_store:
            return []

        cats = self.list_categories()
        if not cats:
            # fallback: just regular search
            return search_similar_text(self.vector_store, query, k=max(5, per_category_k))

        out: List[Document] = []
        
        # Pobierz wszystkie dokumenty z docstore żeby móc filtrować per kategoria
        all_docs_by_category: Dict[str, List[Document]] = {}
        try:
            ds = getattr(self.vector_store, "docstore", None)
            dsdict = getattr(ds, "_dict", None)
            if isinstance(dsdict, dict):
                for doc in dsdict.values():
                    md = getattr(doc, "metadata", {}) or {}
                    cat = str(md.get("category", "")).strip()
                    if cat:
                        all_docs_by_category.setdefault(cat, []).append(doc)
        except Exception as exc:
            logging.warning("search_all_categories: Błąd podczas skanowania docstore: %s", exc)
        
        for cat in cats:
            # Strategia 1: Jeśli mamy dokumenty z docstore dla tej kategorii, użyj ich
            cat_docs = all_docs_by_category.get(cat, [])
            
            if cat_docs:
                # Mamy dokumenty dla tej kategorii - wybierz najlepsze per_category_k
                # Używamy prostego podobieństwa tekstowego (query w content)
                query_lower = query.lower()
                scored_docs = []
                for doc in cat_docs:
                    content = (doc.page_content or "").lower()
                    # Prosta heurystyka: ile słów z query występuje w dokumencie
                    score = sum(1 for word in query_lower.split() if len(word) > 3 and word in content)
                    scored_docs.append((score, doc))
                
                # Sortuj malejąco po score
                scored_docs.sort(key=lambda x: x[0], reverse=True)
                best_docs = [doc for _, doc in scored_docs[:per_category_k]]
                out.extend(best_docs)
                continue
            
            # Strategia 2: Fallback - użyj similarity search z filtrem
            q = f"{query}\nKategoria: {cat}"

            # Prefer MMR when available to reduce duplicates within a category
            docs_cat: List[Document]
            try:
                docs_cat = self.vector_store.max_marginal_relevance_search(  # type: ignore[attr-defined]
                    q,
                    k=per_category_k * 3,  # Pobierz więcej, żeby móc filtrować
                    fetch_k=max(fetch_k, per_category_k * 10),
                    lambda_mult=mmr_lambda,
                )
            except Exception:
                docs_cat = self.vector_store.similarity_search(q, k=per_category_k * 3)

            # Filtruj TYLKO dokumenty z tej kategorii
            filtered = [d for d in docs_cat if (d.metadata or {}).get("category") == cat]
            if filtered:
                out.extend(filtered[:per_category_k])
            else:
                # Ostateczność - brak dokumentów dla tej kategorii w wynikach
                logging.warning("search_all_categories: Brak dokumentów dla kategorii '%s' po MMR", cat)

        return out

    # ---------------------------------------------------------------------
    # RAG answers
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
        Standard RAG: uses top_k most similar chunks globally.
        """
        model_to_use = chat_model or self.chat_model

        search_payload = self.search(query, top_k=top_k)
        if not search_payload.get("success"):
            return {**search_payload, "answer": search_payload.get("error", "Brak danych"), "llm_used": False}

        if not self.vector_store:
            self.load_index()

        docs: List[Document] = []
        if self.vector_store:
            docs = search_similar_text(self.vector_store, query, k=top_k)

        context = _build_context(docs, max_chars=_get_context_max_chars())
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

    def answer_query_all_categories(
        self,
        query: str,
        *,
        per_category_k: int = 2,
        chat_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict:
        """
        Category-coverage RAG: Profesjonalne streszczenie newsów jak reporter.
        
        Dla każdej kategorii tworzy koherentne, płynne podsumowanie najważniejszych
        informacji. Styl: dziennikarski, konkretny, z liczbami i faktami.
        
        GWARANCJA: Każda dostępna kategoria zostanie uwzględniona w odpowiedzi.
        """
        model_to_use = chat_model or self.chat_model
        
        # 1. Pobierz WSZYSTKIE dostępne kategorie
        all_categories = self.list_categories()
        if not all_categories:
            logging.warning("answer_query_all_categories: Brak kategorii w bazie")
            return {
                "success": False,
                "error": "Brak kategorii w bazie FAISS. Zeskrapuj newsy i zbuduj indeks.",
                "query": query,
                "count": 0,
                "results": [],
                "answer": "❌ Baza wiedzy jest pusta. Najpierw pobierz newsy i zbuduj indeks FAISS.",
                "llm_used": False,
            }
        
        logging.info("answer_query_all_categories: Znaleziono %d kategorii: %s", len(all_categories), all_categories)

        # 2. Wyszukaj dokumenty dla wszystkich kategorii
        docs = self.search_all_categories(query, per_category_k=per_category_k)
        results = _format_results(docs)
        context_budget = _get_context_max_chars()
        
        # 3. Buduj konteksty per kategoria z dokumentów
        contexts_by_cat = _build_category_contexts(docs, max_chars_total=context_budget)
        
        # 4. GWARANCJA: Upewnij się, że KAŻDA kategoria ma wpis (nawet pusty)
        for cat in all_categories:
            if cat not in contexts_by_cat:
                contexts_by_cat[cat] = ""
                logging.warning("answer_query_all_categories: Brak dokumentów dla kategorii '%s'", cat)
        
        # Sortuj alfabetycznie
        contexts_by_cat = dict(sorted(contexts_by_cat.items()))
        
        context = "\n\n".join(
            [
                f"=== {cat} ===\n{ctx}" if ctx else f"=== {cat} ===\n(brak danych)"
                for cat, ctx in contexts_by_cat.items()
            ]
        ).strip()
        
        payload = {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results,
            "categories_found": list(contexts_by_cat.keys()),
            "categories_with_data": [cat for cat, ctx in contexts_by_cat.items() if ctx],
            "categories_empty": [cat for cat, ctx in contexts_by_cat.items() if not ctx],
            "search_info": {
                "mode": "category_coverage",
                "per_category_k": per_category_k,
                "embedding_model": self.embeddings.model,
                "chunks_snapshot_jsonl": DOCS_JSONL_PATH,
            },
            "context_preview": context[:2000] + "..." if len(context) > 2000 else context,
        }

        if not self.client:
            logging.error("answer_query_all_categories: Brak klienta OpenAI")
            return {
                **payload,
                "answer": self._fallback_human_answer(query, results),
                "llm_used": False,
                "error": "Brak skonfigurowanego klienta OpenAI",
            }

        if not context or all(not ctx for ctx in contexts_by_cat.values()):
            logging.warning("answer_query_all_categories: Brak kontekstu dla żadnej kategorii")
            return {
                **payload,
                "answer": "❌ Brak danych w bazie wiedzy dla żadnej kategorii. Zeskrapuj newsy i zbuduj indeks.",
                "llm_used": False,
            }

        # System prompt - styl profesjonalnego reportera
        sys_msg = system_prompt or (
            "Jesteś doświadczonym dziennikarzem biznesowym przygotowującym poranny briefing dla kadry zarządzającej. "
            "Twój styl: profesjonalny, zwięzły, konkretny. Używasz liczb, dat, nazw firm i osób gdy są dostępne. "
            "Piszesz płynną, koherentną prozę - NIE używasz wypunktowań ani list. "
            "Każda kategoria to osobny, spójny akapit 2-4 zdań. "
            "MUSISZ uwzględnić KAŻDĄ kategorię z listy - nawet jeśli napiszesz że brak informacji. "
            "Odpowiadasz TYLKO po polsku. Korzystasz WYŁĄCZNIE z podanego kontekstu."
        )
        
        # Buduj sekcje kontekstu z jawnym oznaczeniem pustych
        context_sections_list = []
        for cat in sorted(contexts_by_cat.keys()):
            ctx = contexts_by_cat[cat]
            if ctx and ctx.strip():
                context_sections_list.append(f"### {cat.upper()} ###\n{ctx}")
            else:
                context_sections_list.append(f"### {cat.upper()} ###\n(BRAK DANYCH - napisz że brak informacji)")
        
        context_sections = "\n\n".join(context_sections_list)
        
        # Jawna lista kategorii do uwzględnienia
        categories_list = ", ".join(sorted(contexts_by_cat.keys()))

        user_msg = (
            f"Przygotuj profesjonalne streszczenie newsów. MUSISZ uwzględnić WSZYSTKIE kategorie.\n\n"
            f"KATEGORIE DO UWZGLĘDNIENIA ({len(contexts_by_cat)}): {categories_list}\n\n"
            f"ŹRÓDŁA (per kategoria):\n{context_sections}\n\n"
            "INSTRUKCJE:\n"
            f"1. Napisz streszczenie dla KAŻDEJ z {len(contexts_by_cat)} kategorii wymienionych powyżej\n"
            "2. Każda sekcja zaczyna się od emoji i nazwy (np. 📊 BIZNES)\n"
            "3. Dla każdej kategorii napisz 2-4 zdania płynną prozą (BEZ wypunktowań)\n"
            "4. Jeśli przy kategorii jest '(BRAK DANYCH)', napisz: 'Brak nowych informacji w tej kategorii.'\n"
            "5. Uwzględnij liczby, daty, nazwy firm jeśli są dostępne\n\n"
            "WAŻNE: Odpowiedź MUSI zawierać sekcje dla WSZYSTKICH kategorii!"
        )

        try:
            logging.info("answer_query_all_categories: Wywołanie OpenAI (model=%s)", model_to_use)
            resp = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=2000,  # Zapewnij wystarczająco dużo tokenów na wszystkie kategorie
            )
            answer = (resp.choices[0].message.content or "").strip()
            
            if not answer:
                logging.error("answer_query_all_categories: OpenAI zwróciło pustą odpowiedź")
                answer = self._fallback_human_answer(query, results)
                return {**payload, "answer": answer, "llm_used": False, "error": "OpenAI zwróciło pustą odpowiedź"}
                
            logging.info("answer_query_all_categories: Sukces, odpowiedź ma %d znaków", len(answer))
            
        except Exception as exc:
            logging.exception("answer_query_all_categories: Błąd OpenAI: %s", exc)
            return {
                **payload,
                "answer": f"❌ Błąd połączenia z OpenAI: {str(exc)}\n\n{self._fallback_human_answer(query, results)}",
                "llm_used": False,
                "error": str(exc),
            }

        return {
            **payload,
            "answer": answer,
            "llm_used": True,
            "chat_model": model_to_use,
        }

    def _fallback_human_answer(self, query: str, results: List[Dict]) -> str:
        top = results[:8]
        lines: List[str] = []
        lines.append(f"Znalazłem {len(results)} fragmentów (tryb: kategoria/coverage).")
        lines.append(f"Pytanie: {query}")
        lines.append("")

        for r in top:
            content = (r.get("content") or "").strip()
            title = r.get("title", "") or "bez tytułu"
            url = r.get("url", "")
            cat = r.get("category", "Fragment")
            ci = r.get("chunk_index", 0)

            if len(content) > 220:
                content = content[:220].rstrip() + "…"

            lines.append(f"- ({cat}, chunk={ci}) {title} | {url}\n  {content}")

        if len(results) > len(top):
            lines.append("")
            lines.append(f"... +{len(results) - len(top)} kolejnych fragmentów")

        return "\n".join(lines).strip()
