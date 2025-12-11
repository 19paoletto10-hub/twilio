"""
Manual smoke test for FAISSService + ScraperService integration.
Run with:
    python scripts/test_faiss.py
Optionally set SECOND_OPENAI for real embeddings and chat:
    export SECOND_OPENAI="sk-..."
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.faiss_service import FAISSService
from app.scraper_service import ScraperService


def main() -> None:
    # 1) Tiny synthetic dataset to avoid hitting the network.
    synthetic = {
        "Gospodarka": "Wzrost PKB w trzecim kwartale. Inflacja spada, rynek pracy stabilny.",
        "Technologie": "Nowa firma AI otrzymala finansowanie na rozwijanie modeli językowych.",
    }

    faiss_service = FAISSService()
    ok = faiss_service.build_index_from_scraped_content(synthetic)
    print(f"Index build (synthetic) ok={ok}")

    # 2) Local search
    search_res = faiss_service.search("Co nowego w gospodarce?", top_k=3)
    print("Search count:", search_res.get("count"))
    for r in search_res.get("results", []):
        print("-", r.get("category"), r.get("content")[:120])

    # 3) Optional on-demand scrape of one category (network). Comment out if offline.
    # scraper = ScraperService(max_links_per_category=2)
    # scraped = scraper.fetch_all_categories(build_faiss=False)
    # faiss_service.build_index_from_scraped_content(scraped)

    # 4) LLM answer (uses SECOND_OPENAI if set; otherwise fallback extractive answer)
    answer = faiss_service.answer_query("Co nowego w gospodarce?", top_k=3)
    print("\nAnswer:\n", answer.get("answer"))
    print("LLM used:", answer.get("llm_used"))


if __name__ == "__main__":
    main()
