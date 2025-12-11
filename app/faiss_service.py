from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore

from dataclasses import dataclass


@dataclass
class Document:
    page_content: str
    metadata: dict


class Embeddings:
    def embed_query(self, text: str) -> List[float]:
        raise NotImplementedError()



try:
    import openai
except Exception:  # pragma: no cover
    openai = None  # type: ignore


logger = logging.getLogger(__name__)


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
# Defaults
# =============================================================================
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
FALLBACK_DIM = 3072

DEFAULT_CHAT_MODEL = os.getenv("SECOND_MODEL", "gpt-4o-mini")


# =============================================================================
# OpenAI key resolution
# =============================================================================
def _get_openai_key() -> Optional[str]:
    """
    Resolve OpenAI API key for embeddings/chat.

    Priority:
    1) Flask current_app.config['OPENAI_SETTINGS'] (if in app context)
    2) environment variable SECOND_OPENAI
    """
    try:
        from flask import current_app
        if current_app:
            openai_cfg = current_app.config.get("OPENAI_SETTINGS")
            if openai_cfg and openai_cfg.api_key:
                return openai_cfg.api_key
    except (ImportError, RuntimeError):
        # Not in Flask context or current_app unavailable
        pass
    return os.getenv("SECOND_OPENAI")


OPENAI_API_KEY = _get_openai_key()
if not OPENAI_API_KEY:
    logging.warning(
        "❌ Brak klucza API OpenAI. "
        "Embeddings użyją fallbacku, a odpowiedzi LLM przejdą w tryb bez-LLM."
    )


# =============================================================================
# Embeddings adapter
# =============================================================================
class OpenAIEmbeddings(Embeddings):
    """
    Minimal implementation compatible with LangChain's Embeddings interface.

    - With API key: uses OpenAI embeddings.
    - Without key: deterministic hashing fallback (dev-only).
    """

    def __init__(self, model: str = EMBEDDING_MODEL_NAME):
        self.model = model
        self.api_key = _get_openai_key()
        self._cache: Dict[str, List[float]] = {}  # simple memory cache

        if openai and self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.debug("OpenAIEmbeddings initialized | Model: %s | Key: ...%s", 
                           self.model, self.api_key[-4:] if len(self.api_key) > 4 else "****")
            except Exception as exc:  # pragma: no cover
                logger.warning("OpenAI client init failed: %s", exc)
                self.client = None
        else:
            self.client = None
            if not self.api_key:
                logger.debug("OpenAIEmbeddings using fallback mode (no API key)")

    def embed_query(self, text: str) -> List[float]:
    Mirrors the style of the reference OpenAIService but focused on short, factual
    answers for Business Insider PL content.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or _get_openai_key()
        self.model = (model or DEFAULT_CHAT_MODEL).strip()
        if openai and self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.debug("NewsOpenAIService init | model=%s | key=...%s", self.model, self.api_key[-4:])
            except Exception as exc:  # pragma: no cover
                logger.warning("NewsOpenAIService client init failed: %s", exc)
                self.client = None
        else:
            self.client = None
            if not self.api_key:
                logger.debug("NewsOpenAIService running without API key (LLM disabled)")

    def _build_context(self, found_texts: List[str]) -> str:
        """Prepare compact context by trimming and labeling fragments."""
        parts: List[str] = []
        for i, text in enumerate(found_texts[:8], 1):
            content = (text or "").strip()
            if not content:
                continue
            if len(content) > 800:
                content = content[:800].rstrip() + "..."
            parts.append(f"[Fragment {i}]\n{content}")
        return "\n\n".join(parts)

    def analyze(self, user_query: str, found_texts: List[str]) -> str:
        """Generate an answer using context; falls back to plain join."""
        if not user_query:
            return "Brak pytania użytkownika."

        context = self._build_context(found_texts)
        if not self.client or not context:
            # Fallback: concatenate and return a minimal statement
            preview = "\n".join(found_texts[:3])
            return (
                "Brak dostępu do LLM lub kontekstu. "
                "Oto zebrane fragmenty:\n" + preview[:1200]
            ).strip()

        system_message = (
            "Jesteś ekspertem w analizie polskich mediów biznesowych. "
            "Odpowiadasz krótko, precyzyjnie i obiektywnie. "
            "Używasz tylko dostarczonych fragmentów."
        )

        user_message = (
            "Na podstawie poniższych fragmentów artykułów odpowiedz na pytanie użytkownika.\n\n"
            f"PYTANIE: {user_query}\n\n"
            f"FRAGMENTY:\n{context}\n\n"
            "Instrukcje:\n"
            "1) Połącz informacje z wielu fragmentów,\n"
            "2) Cytuj lub nawiązuj do fragmentów,\n"
            "3) Jeśli danych brakuje, powiedz to wprost."
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=900,
                timeout=60,
            )
            content = resp.choices[0].message.content if resp.choices else None
            return (content or "Brak odpowiedzi od modelu.").strip()
        except Exception as exc:  # noqa: BLE001
            logger.error("NewsOpenAIService analyze error: %s", exc)
            return f"Błąd podczas zapytania do LLM: {exc}"



# =============================================================================
# Low-level helpers
# =============================================================================
def _slugify_category(name: str) -> str:
    if not name:
        return "category"
    value = unicodedata.normalize("NFKD", name)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "category"


def _split_text_into_chunks(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[Tuple[int, int, str]]:
    text = (text or "").strip()
    if not text:
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks: List[Tuple[int, int, str]] = []
    for start in range(0, len(text), step):
        end = min(len(text), start + chunk_size)
        piece = text[start:end]
        if not piece.strip():
            continue
        chunks.append((start, end, piece))
    return chunks


def _prompt_blueprint(category: str) -> Dict[str, Dict[str, object]]:
    """Return nested prompt metadata stored with every chunk."""
    return {
        "system": {
            "role": "assistant",
            "goal": "Tworzysz precyzyjne streszczenia newsów Business Insider PL.",
            "style": {
                "tone": "biznesowy",
                "language": "pl",
                "format": "3-4 zdania"
            },
        },
        "user": {
            "instruction": "Wypunktuj najważniejsze informacje i wskaż kontekst rynkowy.",
            "category": category,
            "constraints": [
                "Używaj wyłącznie dostarczonych fragmentów",
                "Nie dodawaj własnych opinii",
                "Jeśli brak danych, powiedz to wprost"
            ],
        },
    }


def _build_documents_from_scraped_content(
    scraped_content: Dict[str, str],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[Document]:
    ingest_ts = datetime.utcnow().isoformat() + "Z"
    documents: List[Document] = []

    for category, content in scraped_content.items():
        if not content or str(content).startswith("❌"):
            continue

        chunks = _split_text_into_chunks(
            content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunks:
            continue

        slug = _slugify_category(category)
        chunk_total = len(chunks)
        base_tags = ["news", "business_insider", slug]

        for idx, (char_start, char_end, chunk_text) in enumerate(chunks):
            metadata = {
                "source": "business_insider_scraper",
                "category": category,
                "category_slug": slug,
                "tags": base_tags,
                "ingest": {
                    "pipeline": "faiss_news_build",
                    "ingested_at": ingest_ts,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                },
                "chunk": {
                    "index": idx,
                    "count": chunk_total,
                    "char_start": char_start,
                    "char_end": char_end,
                    "length": len(chunk_text),
                },
                "prompt": _prompt_blueprint(category),
            }
            documents.append(Document(page_content=chunk_text, metadata=metadata))

    return documents


# -----------------------
# Vector store implementations (Faiss-backed and minimal numpy fallback)
# -----------------------
class MinimalVectorStore:
    def __init__(self, embedding_function):
        self.embedding_function = embedding_function
        self.embeddings = None
        self.ids: List[str] = []
        self.docs: List[Document] = []

    def add_documents(self, documents: List[Document], embeddings: Optional[List[List[float]]] = None, ids: Optional[List[str]] = None):
        import numpy as _np

        if embeddings is None:
            embeddings = [self.embedding_function.embed_query(d.page_content) for d in documents]

        arr = _np.array(embeddings, dtype="float32")
        if self.embeddings is None:
            self.embeddings = arr
        else:
            self.embeddings = _np.vstack([self.embeddings, arr])

        self.docs.extend(documents)
        if ids:
            self.ids.extend(ids)
        else:
            self.ids.extend([os.urandom(16).hex() for _ in documents])

    def similarity_search(self, query: str, k: int = 5):
        import numpy as _np

        if self.embeddings is None or len(self.docs) == 0:
            return []

        qv = _np.array(self.embedding_function.embed_query(query), dtype="float32")
        qn = qv / (_np.linalg.norm(qv) + 1e-12)
        en = self.embeddings / (_np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-12)
        sims = en.dot(qn)
        idx = _np.argsort(-sims)[:k]
        return [self.docs[int(i)] for i in idx]

    def save_local(self, path: str):
        import numpy as _np

        os.makedirs(path, exist_ok=True)
        if self.embeddings is None:
            arr = _np.zeros((0, 0), dtype="float32")
        else:
            arr = self.embeddings
        npz_path = os.path.join(path, "index.npz")
        _np.savez_compressed(npz_path, embeddings=arr, ids=_np.array(self.ids, dtype=object))

        docs_snapshot = [
            {"id": _id, "page_content": d.page_content, "metadata": d.metadata}
            for _id, d in zip(self.ids, self.docs)
        ]
        with open(os.path.join(path, "docs.json"), "w", encoding="utf-8") as f:
            json.dump(docs_snapshot, f, ensure_ascii=False, indent=2)

        logger.info("Saved MinimalVectorStore index to %s (docs=%s)", path, len(docs_snapshot))

    @staticmethod
    def load_local(path: str, embeddings_obj, allow_dangerous_deserialization: bool = True):
        try:
            import numpy as _np

            npz_file = os.path.join(path, "index.npz")
            docs_file = os.path.join(path, "docs.json")
            if not os.path.exists(npz_file):
                return None

            data = _np.load(npz_file, allow_pickle=True)
            arr = data["embeddings"]
            ids = list(data["ids"])

            docs = []
            if os.path.exists(docs_file):
                with open(docs_file, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                for item in snap:
                    docs.append(Document(page_content=item.get("page_content", ""), metadata=item.get("metadata", {})))
            else:
                docs = [Document(page_content="", metadata={}) for _ in ids]

            store = MinimalVectorStore(embedding_function=embeddings_obj)
            store.embeddings = arr.astype("float32")
            store.ids = ids
            store.docs = docs
            logger.info("Loaded MinimalVectorStore index from %s (docs=%s)", path, len(docs))
            return store
        except Exception as exc:  # noqa: BLE001
            logger.error("MinimalVectorStore load error: %s", exc)
            return None


class FaissStore:
    def __init__(self, embedding_function, dim: int):
        self.embedding_function = embedding_function
        self.dim = dim
        if faiss is None:
            raise RuntimeError("faiss not available")
        # use inner-product on normalized vectors for cosine similarity
        self.index = faiss.IndexFlatIP(dim)
        self.ids: List[str] = []
        self.docs: List[Document] = []

    def add_documents(self, documents: List[Document], embeddings: Optional[List[List[float]]] = None, ids: Optional[List[str]] = None):
        import numpy as _np

        if embeddings is None:
            embeddings = [self.embedding_function.embed_query(d.page_content) for d in documents]

        arr = _np.array(embeddings, dtype="float32")
        norms = _np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
        arr = arr / norms

        self.index.add(arr)
        self.docs.extend(documents)
        if ids:
            self.ids.extend(ids)
        else:
            self.ids.extend([os.urandom(16).hex() for _ in documents])

    def similarity_search(self, query: str, k: int = 5):
        import numpy as _np

        if len(self.docs) == 0:
            return []

        qv = _np.array(self.embedding_function.embed_query(query), dtype="float32")
        qv = qv / (_np.linalg.norm(qv) + 1e-12)
        qv = qv.reshape(1, -1)
        D, I = self.index.search(qv, k)
        out = []
        for idx in I[0]:
            if idx < 0 or idx >= len(self.docs):
                continue
            out.append(self.docs[int(idx)])
        return out

    def save_local(self, path: str):
        os.makedirs(path, exist_ok=True)
        try:
            faiss.write_index(self.index, os.path.join(path, "index.faiss"))
        except Exception as exc:  # noqa: BLE001
            logger.error("faiss write error: %s", exc)

        docs_snapshot = [
            {"id": _id, "page_content": d.page_content, "metadata": d.metadata}
            for _id, d in zip(self.ids, self.docs)
        ]
        with open(os.path.join(path, "docs.json"), "w", encoding="utf-8") as f:
            json.dump(docs_snapshot, f, ensure_ascii=False, indent=2)

        logger.info("Saved FaissStore index to %s (docs=%s)", path, len(docs_snapshot))

    @staticmethod
    def load_local(path: str, embeddings_obj, allow_dangerous_deserialization: bool = True):
        try:
            if faiss is None:
                return None
            idx_path = os.path.join(path, "index.faiss")
            docs_file = os.path.join(path, "docs.json")
            if not os.path.exists(idx_path):
                return None

            index = faiss.read_index(idx_path)
            dim = int(index.d)
            store = FaissStore(embedding_function=embeddings_obj, dim=dim)
            store.index = index

            if os.path.exists(docs_file):
                with open(docs_file, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                for item in snap:
                    store.docs.append(Document(page_content=item.get("page_content", ""), metadata=item.get("metadata", {})))
                    store.ids.append(item.get("id", os.urandom(16).hex()))

            logger.info("Loaded FaissStore index from %s (docs=%s)", path, len(store.docs))
            return store
        except Exception as exc:  # noqa: BLE001
            logger.error("FaissStore load error: %s", exc)
            return None


def build_faiss_from_documents(
    documents: List[Document],
    embeddings: OpenAIEmbeddings,
) -> Optional[object]:
    if not documents:
        return None

    texts = [doc.page_content for doc in documents]

    # infer dimension from first embedding
    try:
        sample_vec = embeddings.embed_query(texts[0])
        dim = len(sample_vec)
        logger.debug("Inferred embedding dimension: %d", dim)

        if dim < 128 or dim > 4096:
            logger.warning("Embedding dimension %d looks suspicious", dim)
    except Exception as exc:
        logger.error("Failed to infer embedding dimension: %s", exc)
        dim = FALLBACK_DIM

    logger.info("Generating embeddings for %d documents...", len(texts))
    try:
        vectors = embeddings.embed_documents(texts)
        if len(vectors) != len(texts):
            logger.warning(
                "Mismatch between embeddings (%d) and documents (%d)", len(vectors), len(texts)
            )

        for i, vec in enumerate(vectors[:3]):
            if len(vec) != dim:
                logger.warning("Vector %d has dimension %d (expected %d)", i, len(vec), dim)
                break
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        return None

    ids = [os.urandom(16).hex() for _ in documents]

    store = None
    if faiss is not None:
        try:
            store = FaissStore(embedding_function=embeddings, dim=dim)
            store.add_documents(documents=documents, embeddings=vectors, ids=ids)
            logger.info("Built FaissStore with %s docs", len(documents))
        except Exception as exc:
            logger.error("FaissStore build failed (%s), falling back to MinimalVectorStore", exc)

    if store is None:
        store = MinimalVectorStore(embedding_function=embeddings)
        store.add_documents(documents=documents, embeddings=vectors, ids=ids)
        logger.info("Built MinimalVectorStore (no faiss) with %s docs", len(documents))

    snapshot = [
        {"id": _id, "page_content": doc.page_content, "metadata": doc.metadata}
        for _id, doc in zip(ids, documents)
    ]
    with open(DOCS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return store


def save_faiss_index(store: Optional[object], path: str = FAISS_INDEX_PATH) -> None:
    """Zapisz aktualny indeks wektorowy wraz z metadanymi dokumentów.

    Oczekujemy, że implementacja store.save_local(path) utworzy komplet plików
    potrzebnych do późniejszego odtworzenia indeksu (np. index.faiss/index.npz
    + docs.json w katalogu "path").
    """

    if not store:
        return

    os.makedirs(path, exist_ok=True)
    try:
        store.save_local(path)
        logger.info("💾 Vector index saved -> %s", path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save index: %s", exc)


def _rebuild_index_from_docs(docs_path: str, embeddings: OpenAIEmbeddings) -> Optional[object]:
    """Odbuduj indeks wektorowy wyłącznie na podstawie pliku docs.json.

    Używane gdy fizyczne pliki indeksu (index.faiss / index.npz) zniknęły,
    ale zachował się snapshot dokumentów. Dzięki temu wystarczy zbackupować
    katalog z indeksem (.../faiss_openai_index/) oraz X1_data/documents.json,
    aby móc odtworzyć całą bazę FAISS.
    """

    try:
        if not os.path.exists(docs_path):
            logger.warning("Docs snapshot not found for rebuild: %s", docs_path)
            return None

        with open(docs_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list) or not raw:
            logger.warning("Docs snapshot %s is empty or invalid", docs_path)
            return None

        texts: List[str] = []
        docs: List[Document] = []
        ids: List[str] = []

        for item in raw:
            text = (item.get("page_content") or "").strip()
            if not text:
                continue
            texts.append(text)
            docs.append(Document(page_content=text, metadata=item.get("metadata", {})))
            ids.append(item.get("id") or os.urandom(16).hex())

        if not texts:
            logger.warning("No non-empty documents in %s", docs_path)
            return None

        # Ustal wymiar na podstawie pojedynczego embeddingu
        try:
            sample_vec = embeddings.embed_query(texts[0])
            dim = len(sample_vec)
            logger.debug("Rebuild: inferred embedding dimension=%d from snapshot", dim)
        except Exception as exc:  # noqa: BLE001
            logger.error("Rebuild: failed to infer embedding dimension: %s", exc)
            dim = FALLBACK_DIM

        # Wygeneruj embeddingi dla wszystkich tekstów
        try:
            vectors = embeddings.embed_documents(texts)
            if len(vectors) != len(texts):
                logger.error(
                    "Rebuild: embedding count mismatch (got=%d, expected=%d)",
                    len(vectors),
                    len(texts),
                )
                return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Rebuild: embedding generation failed: %s", exc)
            return None

        # Zbuduj indeks FAISS lub fallbackowy MinimalVectorStore
        if faiss is not None:
            try:
                store = FaissStore(embedding_function=embeddings, dim=dim)
                store.add_documents(documents=docs, embeddings=vectors, ids=ids)
                logger.info(
                    "Rebuilt FaissStore from docs snapshot %s (docs=%d)",
                    docs_path,
                    len(docs),
                )
                return store
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Rebuild: FaissStore creation failed, falling back to MinimalVectorStore: %s",
                    exc,
                )

        # Fallback / brak faiss
        store = MinimalVectorStore(embedding_function=embeddings)
        store.add_documents(documents=docs, embeddings=vectors, ids=ids)
        logger.info(
            "Rebuilt MinimalVectorStore from docs snapshot %s (docs=%d)",
            docs_path,
            len(docs),
        )
        return store
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error while rebuilding index from %s: %s", docs_path, exc)
        return None


def load_faiss_index(path: str = FAISS_INDEX_PATH) -> Optional[object]:
    """Załaduj istniejący indeks FAISS lub spróbuj go odbudować z docs.json.

    Ścieżki, które traktujemy jako źródła prawdy:
    - <path>/index.faiss + <path>/docs.json   (FaissStore)
    - <path>/index.npz   + <path>/docs.json   (MinimalVectorStore)
    - <path>/docs.json                      -> rekonstrukcja na podstawie treści
    - X1_data/documents.json                -> globalny snapshot (ostatni build)
    """

    try:
        index_faiss = os.path.join(path, "index.faiss")
        docs_file = os.path.join(path, "docs.json")
        npz_file = os.path.join(path, "index.npz")

        embeddings = OpenAIEmbeddings()

        # 1) Priorytet: pełny faiss index
        if faiss is not None and os.path.exists(index_faiss):
            store = FaissStore.load_local(path, embeddings)
            if store:
                return store

        # 2) Fallback: MinimalVectorStore (index.npz + docs.json)
        if os.path.exists(npz_file):
            store = MinimalVectorStore.load_local(path, embeddings)
            if store:
                return store

        # 3) Mamy tylko docs.json w katalogu indeksu – spróbuj odbudować
        if os.path.exists(docs_file):
            logger.info(
                "Found docs.json without usable index files in %s – attempting rebuild",
                path,
            )
            store = _rebuild_index_from_docs(docs_file, embeddings)
            if store:
                # zapisujemy od razu, żeby kolejne starty były szybkie
                save_faiss_index(store, path)
                return store

        # 4) Ostateczny fallback: globalny snapshot dokumentów
        if path == FAISS_INDEX_PATH and os.path.exists(DOCS_JSON_PATH):
            logger.info(
                "Trying to rebuild vector index from global documents snapshot: %s",
                DOCS_JSON_PATH,
            )
            store = _rebuild_index_from_docs(DOCS_JSON_PATH, embeddings)
            if store:
                save_faiss_index(store, path)
                return store

        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("FAISS load error: %s", exc)
        return None


def search_similar_text(store, query: str, k: int = 5):
    try:
        return store.similarity_search(query, k=k)
    except Exception as exc:  # noqa: BLE001
        logging.error("Vector store search error: %s", exc)
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
# Service
# =============================================================================
class FAISSService:
    """
    FAISS + OpenAI Embeddings + optional RAG answers.

    Designed to integrate with app.scraper_service outputs.

    Key capabilities:
    - build_index_from_scraped_content({category: text})
    - build_index_from_category_files()
    - load_index()
    - search()
    - answer_query() -> "po ludzku" with OpenAI Chat
    """

    def __init__(self) -> None:
        self.embeddings = OpenAIEmbeddings()
        self.vector_store: Optional[object] = None

        self.api_key = _get_openai_key()
        if openai and self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.debug(
                    "FAISSService initialized | OpenAI client ready | Key: ...%s",
                    self.api_key[-4:] if len(self.api_key) > 4 else "****"
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("FAISSService OpenAI client init failed: %s", exc)
                self.client = None
        else:
            self.client = None
            if not self.api_key:
                logger.debug("FAISSService initialized without OpenAI key (fallback embeddings mode)")

    # ---------------------------------------------------------------------
    # Index lifecycle
    # ---------------------------------------------------------------------
    def load_index(self, path: str = FAISS_INDEX_PATH) -> bool:
        try:
            store = load_faiss_index(path)
            if store:
                # Validate loaded store
                if hasattr(store, 'docstore') and hasattr(store.docstore, '_dict'):
                    doc_count = len(store.docstore._dict)
                    logger.info("📂 Vector index loaded from %s: %d documents", path, doc_count)
                    if doc_count == 0:
                        logger.warning("Loaded index is empty")
                else:
                    logger.info("📂 Vector index loaded from %s", path)
                    
                self.vector_store = store
                return True
            logger.info("ℹ️ No vector index found in %s", path)
            return False
        except Exception as exc:
            logger.error("Error loading FAISS index from %s: %s", path, exc, exc_info=True)
            return False

    def build_index_from_scraped_content(self, scraped_content: Dict[str, str]) -> bool:
        """
        Build index from {category_name: combined_text}.

        We prefix each category in text to preserve traceability.
        """
        try:
            documents = _build_documents_from_scraped_content(scraped_content)

            if not documents:
                logger.warning("No valid content to index.")
                return False

            if len(documents) > 10000:
                logger.warning("Large number of chunks (%d), this may take time", len(documents))

            store = build_faiss_from_documents(
                documents,
                embeddings=self.embeddings,
            )
            if not store:
                logger.error("build_faiss_from_documents returned None")
                return False

            self.vector_store = store
            save_faiss_index(self.vector_store)
            logger.info("✅ Vector index built from scraped content (%d chunks)", len(documents))
            return True

        except Exception as exc:  # noqa: BLE001
            logger.error("Build index error: %s", exc, exc_info=True)
            return False

    def build_index_from_category_files(self, category_dir: str = SCRAPED_DIR) -> bool:
        contents = read_category_text_files(category_dir)
        if not contents:
            logger.warning("No category files found in %s", category_dir)
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

        try:
            docs = search_similar_text(self.vector_store, query, k=top_k)
            results = _format_results(docs)
            logger.debug("Search found %d results for query: %.50s...", len(results), query)
        except Exception as exc:
            logger.error("Search error for query '%s': %s", query, exc, exc_info=True)
            return {"success": False, "error": f"Błąd wyszukiwania: {exc}", "results": []}

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results,
            "search_info": {
                "algorithm": "FAISS + OpenAI embeddings",
                "embedding_model": EMBEDDING_MODEL_NAME,
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
        chat_model: str = DEFAULT_CHAT_MODEL,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict:
        """
        Retrieve top-k fragments and generate a short human-friendly answer.

        Uses NewsOpenAIService (SECOND_MODEL/SECOND_OPENAI). Falls back to
        extractive summary when LLM unavailable.
        """
        search_payload = self.search(query, top_k=top_k)
        if not search_payload.get("success"):
            return {**search_payload, "answer": search_payload.get("error", "Brak danych"), "llm_used": False}

        if not self.vector_store:
            self.load_index()

        docs = []
        if self.vector_store:
            docs = search_similar_text(self.vector_store, query, k=top_k)

        # Prepare plain fragments for LLM
        fragments: List[str] = []
        for doc in docs:
            text = (doc.page_content or "").strip()
            fragments.append(text)

        # No LLM client -> fallback
        if not self.client or not fragments:
            return {
                **search_payload,
                "answer": self._fallback_human_answer(query, search_payload.get("results", [])),
                "llm_used": False,
            }

        news_llm = NewsOpenAIService(api_key=self.api_key, model=chat_model)
        answer = news_llm.analyze(query, fragments)

        return {
            **search_payload,
            "answer": answer,
            "llm_used": bool(news_llm.client),
            "chat_model": chat_model,
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
                content = content[:280].rstrip() + "..."

            lines.append(f"- ({category}) {content}")

        lines.append("")
        lines.append("Jeśli chcesz bardziej precyzyjnej odpowiedzi, zaktualizuj scrapowanie i przebuduj indeks.")
        return "\n".join(lines).strip()
