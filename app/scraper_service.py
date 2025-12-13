from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import trafilatura
except Exception:  # pragma: no cover
    trafilatura = None  # type: ignore


logger = logging.getLogger(__name__)


# =============================================================================
# Paths
# =============================================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "X1_data")
SCRAPED_DIR = os.path.join(DATA_DIR, "business_insider_scrapes")

# Kanoniczne źródło danych dla FAISS/RAG:
ARTICLES_JSONL_PATH = os.path.join(DATA_DIR, "articles.jsonl")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCRAPED_DIR, exist_ok=True)


# =============================================================================
# Models
# =============================================================================
@dataclass
class Article:
    url: str
    title: str
    text: str
    category: str
    scraped_at: str

    @classmethod
    def create(
        cls,
        *,
        url: str,
        title: str,
        text: str,
        category: str,
        scraped_at: Optional[datetime] = None,
    ) -> "Article":
        dt = scraped_at or datetime.now(timezone.utc)
        return cls(
            url=url,
            title=(title or "").strip(),
            text=(text or "").strip(),
            category=category,
            scraped_at=dt.isoformat().replace("+00:00", "Z"),
        )

    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# Text cleaning
# =============================================================================
_BOILERPLATE_PATTERNS = [
    r"Zobacz też:.*",
    r"Czytaj również:.*",
    r"Źródło:.*",
    r"Reklama.*",
    r"Newsletter.*",
]


def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    return text


def strip_unwanted_chars(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[•·●◆■▶►]+", " ", text)
    text = re.sub(r"[_=]{3,}", " ", text)
    text = re.sub(r"-{3,}", " ", text)
    return text


def remove_boilerplate_lines(text: str, patterns: List[str] = _BOILERPLATE_PATTERNS) -> str:
    """
    Usuń boilerplate, ale zachowaj przerwy między akapitami.
    """
    if not text:
        return ""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    out: List[str] = []

    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append("")  # zachowaj akapit
            continue
        if any(p.search(s) for p in compiled):
            continue
        out.append(s)

    return "\n".join(out).strip()


def collapse_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def clean_article_text(text: str) -> str:
    text = normalize_unicode(text)
    text = strip_unwanted_chars(text)
    text = remove_boilerplate_lines(text)
    text = collapse_whitespace(text)
    return text


def slugify(name: str) -> str:
    if not name:
        return "category"
    x = unicodedata.normalize("NFKD", name)
    x = x.encode("ascii", "ignore").decode("ascii")
    x = x.lower()
    x = re.sub(r"[^a-z0-9]+", "_", x).strip("_")
    return x or "category"


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _article_id(url: str) -> str:
    # stabilny id per URL
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


# =============================================================================
# Scraper Service
# =============================================================================
class ScraperService:
    """
    Business Insider PL category scraper.

    Profesjonalne podejście do zapisu:
    - per-kategoria: <slug>.txt + <slug>.json (debug / czytelne)
    - kanoniczne dane: X1_data/articles.jsonl (dedup po URL, wykrywanie zmian po hash)

    Ekstrakcja:
    - 1 fetch per artykuł (requests Session + retry)
    - trafilatura.extract(html) na tym samym HTML
    - fallback BS4 w obrębie <article>/<main>
    - robots.txt cache per domena
    """

    def __init__(
        self,
        *,
        max_links_per_category: int = 15,
        request_delay_sec: float = 1.0,
        timeout_sec: int = 15,
        user_agent: Optional[str] = None,
    ) -> None:
        self.news_sites: Dict[str, str] = {
            "Premium": "https://businessinsider.com.pl/premium",
            "Gospodarka": "https://businessinsider.com.pl/gospodarka",
            "Giełda": "https://businessinsider.com.pl/gielda",
            "Prawo": "https://businessinsider.com.pl/prawo",
            "Technologie": "https://businessinsider.com.pl/technologie",
            "Biznes": "https://businessinsider.com.pl/biznes",
            "Nieruchomości": "https://businessinsider.com.pl/nieruchomosci",
            "Praca": "https://businessinsider.com.pl/praca",
            "Poradnik Finansowy": "https://businessinsider.com.pl/poradnik-finansowy",
        }

        self.max_links_per_category = max_links_per_category
        self.request_delay_sec = request_delay_sec
        self.timeout_sec = timeout_sec
        self.scraped_cache: Dict[str, str] = {}

        self.http_headers = {
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # requests Session + retry/backoff (bardziej odporne na 429/5xx)
        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # robots cache: netloc -> RobotFileParser or None (None => assume allowed)
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}

    # -------------------------------------------------------------------------
    # Network + Robots
    # -------------------------------------------------------------------------
    def _sleep(self) -> None:
        time.sleep(self.request_delay_sec)

    def _get(self, url: str) -> Optional[str]:
        try:
            resp = self._session.get(url, headers=self.http_headers, timeout=self.timeout_sec)
            if resp.status_code >= 400:
                logger.warning("HTTP %s for %s", resp.status_code, url)
                return None
            return resp.text
        except requests.RequestException as exc:
            logger.warning("HTTP error for %s: %s", url, exc)
            return None

    def _get_robots_parser(self, netloc: str, scheme: str) -> Optional[RobotFileParser]:
        if netloc in self._robots_cache:
            return self._robots_cache[netloc]

        robots_url = f"{scheme}://{netloc}/robots.txt"
        try:
            resp = self._session.get(robots_url, headers=self.http_headers, timeout=10)
            if resp.status_code != 200 or not resp.text:
                logger.debug("Robots status=%s for %s; assuming allowed.", resp.status_code, robots_url)
                self._robots_cache[netloc] = None
                return None

            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())
            self._robots_cache[netloc] = rp
            return rp
        except Exception as exc:  # noqa: BLE001
            logger.debug("Robots fetch failed for %s: %s; assuming allowed.", robots_url, exc)
            self._robots_cache[netloc] = None
            return None

    def can_scrape(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            rp = self._get_robots_parser(parsed.netloc, parsed.scheme)
            if rp is None:
                return True
            allowed = rp.can_fetch("*", url)
            if not allowed:
                logger.warning("Robots.txt disallows: %s", url)
            return allowed
        except Exception as exc:  # noqa: BLE001
            logger.debug("Robots check failed for %s: %s; assuming allowed.", url, exc)
            return True

    # -------------------------------------------------------------------------
    # Link Extraction
    # -------------------------------------------------------------------------
    def extract_article_links(self, category_url: str, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")

        category_parsed = urlparse(category_url)
        domain = category_parsed.netloc
        category_path = category_parsed.path.rstrip("/")

        excluded_markers = (
            "/autor/",
            "/tagi/",
            "/szukaj",
            "/newsletter",
            "/konto",
            "/regulamin",
            "/polityka-prywatnosci",
        )

        links: List[str] = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue

            url = urljoin(category_url, href)
            parsed = urlparse(url)

            if parsed.netloc != domain:
                continue

            path = (parsed.path or "").rstrip("/")
            if not path or path == category_path:
                continue
            if any(marker in path for marker in excluded_markers):
                continue

            # unikaj linków sekcyjnych / menu
            if path.count("/") < 2:
                continue

            norm_url = parsed._replace(fragment="", query="").geturl()
            if norm_url in seen:
                continue

            seen.add(norm_url)
            links.append(norm_url)

            if len(links) >= self.max_links_per_category:
                break

        return links

    # -------------------------------------------------------------------------
    # Article Extraction
    # -------------------------------------------------------------------------
    def _extract_title_bs(self, soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(" ", strip=True)
        if soup.title and soup.title.string:
            return str(soup.title.string).strip()
        return ""

    def scrape_article(self, url: str) -> Tuple[str, str]:
        if not self.can_scrape(url):
            return "", ""

        html = self._get(url)
        if not html:
            return "", ""

        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_title_bs(soup)

        # 1) Trafilatura (extract only; no extra fetch)
        if trafilatura:
            try:
                extracted = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True,
                )
                if extracted and extracted.strip():
                    return title, clean_article_text(extracted)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Trafilatura extract failed: %s | %s", url, exc)

        # 2) BS fallback (same HTML)
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "meta", "noscript"]):
            tag.decompose()

        root = soup.find("article") or soup.find("main") or soup

        parts: List[str] = []
        for tag in root.find_all(["p", "h2", "h3"], recursive=True):
            txt = tag.get_text(" ", strip=True)
            if txt and len(txt) > 30:
                parts.append(txt)

        return title, clean_article_text("\n".join(parts))

    # -------------------------------------------------------------------------
    # Saving
    # -------------------------------------------------------------------------
    def _save_category(self, category: str, articles: List[Article]) -> Tuple[str, str]:
        safe = slugify(category)
        txt_path = os.path.join(SCRAPED_DIR, f"{safe}.txt")
        json_path = os.path.join(SCRAPED_DIR, f"{safe}.json")

        blocks: List[str] = []
        for art in articles:
            header = art.title.strip() or "Bez tytułu"
            blocks.append(f"{header}\n{art.url}\n{art.text}".strip())

        separator = "\n\n" + ("-" * 80) + "\n\n"
        combined = separator.join(blocks)
        combined = collapse_whitespace(combined)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(combined)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in articles], f, ensure_ascii=False, indent=2)

        logger.info("Saved category '%s' -> %s", category, txt_path)
        return txt_path, json_path

    def _load_articles_jsonl(self) -> Dict[str, Dict]:
        """
        Wczytaj istniejący store (url -> record).
        """
        out: Dict[str, Dict] = {}
        if not os.path.exists(ARTICLES_JSONL_PATH):
            return out

        try:
            with open(ARTICLES_JSONL_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    url = str(rec.get("url", "")).strip()
                    if url:
                        out[url] = rec
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot read articles.jsonl: %s", exc)

        return out

    def _write_articles_jsonl(self, by_url: Dict[str, Dict]) -> None:
        """
        Zapisz w sposób deterministyczny (sort po URL).
        """
        tmp_path = ARTICLES_JSONL_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            for url in sorted(by_url.keys()):
                f.write(json.dumps(by_url[url], ensure_ascii=False) + "\n")
        os.replace(tmp_path, ARTICLES_JSONL_PATH)

    def _upsert_articles_store(self, articles: List[Article]) -> None:
        """
        Merge do kanonicznego store:
        - dedup po URL
        - update jeśli zmienił się content_hash
        """
        existing = self._load_articles_jsonl()

        updates = 0
        for art in articles:
            url = art.url.strip()
            if not url or not art.text:
                continue

            content_hash = _sha256(f"{art.title}\n{art.text}")
            new_rec = {
                "schema_version": 1,
                "id": _article_id(url),
                "url": url,
                "title": art.title,
                "category": art.category,
                "scraped_at": art.scraped_at,
                "text": art.text,
                "content_hash": content_hash,
                "text_len": len(art.text),
            }

            prev = existing.get(url)
            if not prev or str(prev.get("content_hash", "")) != content_hash:
                existing[url] = new_rec
                updates += 1

        if updates:
            self._write_articles_jsonl(existing)
            logger.info("✅ Updated articles store: %s changes -> %s", updates, ARTICLES_JSONL_PATH)
        else:
            logger.info("ℹ️ No changes for articles store.")

    # -------------------------------------------------------------------------
    # Category Scraping
    # -------------------------------------------------------------------------
    def scrape_category(self, category: str, url: str) -> List[Article]:
        logger.info("Scraping category: %s | %s", category, url)

        html = self._get(url)
        if not html:
            logger.warning("Failed to fetch category page: %s", url)
            return []

        links = self.extract_article_links(url, html)

        articles: List[Article] = []
        for link in links:
            self._sleep()
            title, text = self.scrape_article(link)
            if not text:
                continue

            articles.append(
                Article.create(
                    url=link,
                    title=title,
                    text=text,
                    category=category,
                )
            )

        return articles

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def fetch_all_categories(self, *, build_faiss: bool = True) -> Dict[str, str]:
        results: Dict[str, str] = {}
        all_articles: List[Article] = []

        for category, url in self.news_sites.items():
            try:
                articles = self.scrape_category(category, url)
                if not articles:
                    msg = f"❌ Brak artykułów dla kategorii {category}"
                    logger.warning(msg)
                    results[category] = msg
                    self._sleep()
                    continue

                combined_text = "\n\n".join(a.text for a in articles).strip()
                if not combined_text:
                    msg = f"❌ Pusta treść po czyszczeniu dla {category}"
                    logger.warning(msg)
                    results[category] = msg
                    self._sleep()
                    continue

                self._save_category(category, articles)
                self.scraped_cache[category] = combined_text
                results[category] = combined_text

                all_articles.extend(articles)

            except Exception as exc:  # noqa: BLE001
                logger.exception("Error scraping category %s", category)
                results[category] = f"❌ Błąd podczas pobierania: {exc}"
            finally:
                self._sleep()

        # Kanoniczny zapis (dedup/merge)
        if all_articles:
            self._upsert_articles_store(all_articles)

        if build_faiss:
            self._build_faiss_from_results(results)

        return results

    def _build_faiss_from_results(self, results: Dict[str, str]) -> None:
        """
        Prefer:
          - build z articles.jsonl (pełne metadane url/title/category)
        Fallback:
          - build z {category: combined_text}
        """
        try:
            from app.faiss_service import FAISSService  # type: ignore

            faiss_service = FAISSService()
            ok = False

            if hasattr(faiss_service, "build_index_from_articles_jsonl"):
                ok = faiss_service.build_index_from_articles_jsonl(ARTICLES_JSONL_PATH)  # type: ignore

            if not ok and hasattr(faiss_service, "build_index_from_article_json_files"):
                ok = faiss_service.build_index_from_article_json_files(SCRAPED_DIR)  # type: ignore

            if not ok:
                ok = faiss_service.build_index_from_scraped_content(results)

            if ok:
                logger.info("✅ FAISS index created/updated (per-article chunks).")
            else:
                logger.warning("⚠️ FAISS build skipped (no valid content).")
        except Exception as exc:  # noqa: BLE001
            logger.warning("FAISS auto-build failed/skipped: %s", exc)

    def get_category_full_content(self, category: str) -> Optional[str]:
        if category in self.scraped_cache:
            return self.scraped_cache[category]

        url = self.news_sites.get(category)
        if not url:
            return None

        articles = self.scrape_category(category, url)
        if not articles:
            return None

        combined_text = "\n\n".join(a.text for a in articles).strip()
        if not combined_text:
            return None

        self._save_category(category, articles)
        self.scraped_cache[category] = combined_text
        self._upsert_articles_store(articles)
        return combined_text

    def scrape_website(self, url: str) -> str:
        _, text = self.scrape_article(url)
        return text or "❌ Nie udało się pobrać treści."
