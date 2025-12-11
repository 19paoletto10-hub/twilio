from __future__ import annotations

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

try:
    import trafilatura
except Exception:  # pragma: no cover
    trafilatura = None  # type: ignore

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Paths
# =============================================================================
# File lives in /app, so BASE_DIR points to repository root (e.g. /twilio)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "X1_data")
SCRAPED_DIR = os.path.join(DATA_DIR, "business_insider_scrapes")

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
# Text cleaning (lightweight, practical)
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
    if not text:
        return ""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    out: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
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


# =============================================================================
# Scraper Service
# =============================================================================
class ScraperService:
    """
    Business Insider PL category scraper.

    Responsibilities:
    1) Fetch category page HTML.
    2) Extract likely article links.
    3) Scrape each article (polite delay + robots check).
    4) Clean text.
    5) Save:
         - /X1_data/business_insider_scrapes/<category>.txt
         - /X1_data/business_insider_scrapes/<category>.json
    6) Optionally trigger FAISS build in app.faiss_service.

    Notes:
    - Heuristic link extraction.
    - Always respect site rules/robots and your legal constraints.
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

    # -------------------------------------------------------------------------
    # Network + Robots
    # -------------------------------------------------------------------------
    def _sleep(self) -> None:
        time.sleep(self.request_delay_sec)

    def _get(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, headers=self.http_headers, timeout=self.timeout_sec)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("HTTP error for %s: %s", url, exc)
            return None

    def can_scrape(self, url: str) -> bool:
        """
        Best-effort robots.txt check.
        If robots is unreachable, we default to 'allowed' to avoid false negatives.
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            resp = requests.get(robots_url, headers=self.http_headers, timeout=10)
            if resp.status_code != 200:
                logger.debug("Robots status=%s for %s, assuming allowed.", resp.status_code, robots_url)
                return True

            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())

            allowed = rp.can_fetch("*", url)
            if not allowed:
                logger.warning("Robots.txt disallows: %s", url)
            return allowed
        except Exception as exc:  # noqa: BLE001
            logger.debug("Robots check failed for %s: %s, assuming allowed.", url, exc)
            return True

    # -------------------------------------------------------------------------
    # Link Extraction
    # -------------------------------------------------------------------------
    def extract_article_links(self, category_url: str, html: str) -> List[str]:
        """
        Extract likely article links from a category page.

        Heuristics:
        - same domain
        - ignore anchors/mailto/js
        - filter out non-article patterns (author/tag/search/account)
        - stable dedup
        """
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
        """
        Scrape a single article and return (title, cleaned_text).
        Tries trafilatura first, then BeautifulSoup fallback.
        """
        if not self.can_scrape(url):
            return "", ""

        # 1) Trafilatura
        if trafilatura:
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
                    if extracted:
                        title = ""
                        try:
                            soup = BeautifulSoup(downloaded, "html.parser")
                            title = self._extract_title_bs(soup)
                        except Exception:
                            title = ""
                        return title, clean_article_text(extracted)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Trafilatura failed: %s | %s", url, exc)

        # 2) Requests + BS4
        html = self._get(url)
        if not html:
            return "", ""

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "meta", "noscript"]):
            tag.decompose()

        title = self._extract_title_bs(soup)

        paragraphs: List[str] = []
        for tag in soup.find_all(["p", "h2", "h3"]):
            txt = tag.get_text(" ", strip=True)
            if txt and len(txt) > 30:
                paragraphs.append(txt)

        raw_text = "\n".join(paragraphs)
        return title, clean_article_text(raw_text)

    # -------------------------------------------------------------------------
    # Category Scraping + Saving
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

    def _save_category(self, category: str, articles: List[Article]) -> Tuple[str, str]:
        """
        Save:
        - <slug>.txt  (combined cleaned text)
        - <slug>.json (structured)
        """
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

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def fetch_all_categories(self, *, build_faiss: bool = True) -> Dict[str, str]:
        """
        Scrape all configured categories.

        Returns:
            {category_name: combined_text_or_error_string}

        Side effects:
            - saves per-category .txt/.json
            - optionally builds FAISS index via app.faiss_service.FAISSService
        """
        results: Dict[str, str] = {}

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

            except Exception as exc:  # noqa: BLE001
                logger.exception("Error scraping category %s", category)
                results[category] = f"❌ Błąd podczas pobierania: {exc}"
            finally:
                self._sleep()

        if build_faiss:
            self._build_faiss_from_results(results)

        return results

    def _build_faiss_from_results(self, results: Dict[str, str]) -> None:
        """
        Optional integration point:
        Build de/novo FAISS index from freshly scraped category texts.
        """
        try:
            from app.faiss_service import FAISSService

            faiss_service = FAISSService()
            ok = faiss_service.build_index_from_scraped_content(results)
            if ok:
                logger.info("✅ FAISS index created/updated from Business Insider categories.")
            else:
                logger.warning("⚠️ FAISS build skipped (no valid content).")
        except Exception as exc:  # noqa: BLE001
            logger.warning("FAISS auto-build failed/skipped: %s", exc)

    def get_category_full_content(self, category: str) -> Optional[str]:
        """
        Return cached content or scrape on-demand.
        Also saves category files if a fresh scrape is performed.
        """
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
        return combined_text

    # Backward-friendly alias
    def scrape_website(self, url: str) -> str:
        """
        Compatibility method to scrape a single URL and return cleaned text.
        """
        title, text = self.scrape_article(url)
        if text:
            return text

        html = self._get(url)
        if not html:
            return "❌ Nie udało się pobrać treści."

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "meta", "noscript"]):
            tag.decompose()

        paragraphs: List[str] = []
        for tag in soup.find_all(["p", "h1", "h2", "h3"]):
            txt = tag.get_text(" ", strip=True)
            if txt and len(txt) > 30:
                paragraphs.append(txt)

        return clean_article_text("\n".join(paragraphs))
