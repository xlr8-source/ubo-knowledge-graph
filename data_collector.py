# ============================================================
# data_collector.py – Orchestrate data collection from Companies House
# ============================================================
# Fetches company profiles, officers, and PSCs for a list of search
# keywords and saves everything as JSON files in /data/.
#
# Usage with new options:
#   python data_collector.py --limit 500 --results 100
#   (--limit: stop after saving N companies, 0 = no limit)
#   (--results: max results per keyword, up to 100)

import json
import logging
import time
import argparse
from pathlib import Path
from datetime import datetime

from tqdm import tqdm

import config
from companies_house_client import CompaniesHouseClient

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Drives the data-collection pipeline:
      1. Search Companies House for each keyword.
      2. For each company found, fetch profile + officers + PSCs.
      3. Write one JSON file per company into /data/.
    """

    def __init__(self, results_per_keyword: int = 10, limit: int = 0):
        self.client               = CompaniesHouseClient()
        self.data_dir             = config.DATA_DIR
        self.results_per_keyword  = results_per_keyword
        self.limit                = limit   # 0 = no limit

        # Simple run stats printed at the end.
        self._stats = {
            "companies_found":   0,
            "companies_saved":   0,
            "officers_fetched":  0,
            "pscs_fetched":      0,
            "errors":            0,
        }

    # ── Private helpers ───────────────────────────────────────────────

    def _company_file_path(self, company_number: str) -> Path:
        """Return the path where a company's JSON will be saved."""
        return self.data_dir / f"company_{company_number.upper()}.json"

    def _save_json(self, path: Path, data: dict) -> None:
        """Write a dict to a JSON file (pretty-printed, UTF-8)."""
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"Saved: {path.name}")

    def _already_collected(self, company_number: str) -> bool:
        """Skip re-fetching companies we already have on disk."""
        return self._company_file_path(company_number).exists()

    # ── Core collection logic ─────────────────────────────────────────

    def collect_company(self, company_number: str, company_name: str) -> bool:
        """
        Fetch all data for one company and write it to /data/.
        Returns True on success, False on error.
        """
        if self._already_collected(company_number):
            logger.info(f" Already collected - skipping {company_number}")
            return True

        try:
            print(f"\n  [FETCH] Fetching: {company_name} ({company_number})")

            # ── Profile ────────────────────────────────────────
            profile = self.client.get_company_profile(company_number)
            if not profile:
                logger.warning(f"  No profile for {company_number} - skipping")
                self._stats["errors"] += 1
                return False
            print(f"     Profile  - status: {profile.get('company_status', 'unknown')}")

            # ── Officers ───────────────────────────────────────
            officers = self.client.get_officers(company_number)
            self._stats["officers_fetched"] += len(officers)
            print(f"     Officers - {len(officers)} found")

            # ── PSCs ───────────────────────────────────────────
            pscs = self.client.get_psc(company_number)
            self._stats["pscs_fetched"] += len(pscs)
            print(f"     PSCs     - {len(pscs)} found")

            # ── Bundle and save ────────────────────────────────
            bundle = {
                "collected_at":  datetime.utcnow().isoformat() + "Z",
                "company_number": company_number,
                "profile":        profile,
                "officers":       officers,
                "pscs":           pscs,
            }
            self._save_json(self._company_file_path(company_number), bundle)
            self._stats["companies_saved"] += 1
            return True

        except Exception as exc:
            logger.error(f"  Error collecting {company_number}: {exc}", exc_info=True)
            self._stats["errors"] += 1
            return False

    def collect_from_keywords(self, keywords: list[str]) -> None:
        """
        Main pipeline entry point.
        Searches each keyword, deduplicates results, then fetches each company.
        """
        print("\n" + "=" * 60)
        print("  UBO Knowledge Graph - Data Collection")
        print("=" * 60)
        print(f"  Keywords       : {keywords}")
        print(f"  Results/keyword: {self.results_per_keyword}")
        print(f"  Output dir     : {self.data_dir}")
        if self.limit > 0:
            print(f"  Company limit  : {self.limit}")
        else:
            print("  Company limit  : no limit (collect all)")
        print()

        # ── Step 1: gather unique company numbers across all keywords ──
        unique_companies: dict[str, str] = {}   # number → name

        for keyword in keywords:
            print(f"\n[SEARCH] Searching: '{keyword}'")
            results = self.client.search_companies(keyword, limit=self.results_per_keyword)
            self._stats["companies_found"] += len(results)

            for item in results:
                number = item.get("company_number", "")
                name   = item.get("title", "Unknown")
                if number and number not in unique_companies:
                    unique_companies[number] = name

        total_unique = len(unique_companies)
        print(f"\n[STATS] Unique companies found: {total_unique}")

        # Apply limit if set
        if self.limit > 0 and total_unique > self.limit:
            unique_companies = dict(list(unique_companies.items())[:self.limit])
            print(f"[STATS] Truncated to first {self.limit} companies (--limit)")
            total_unique = self.limit

        if total_unique == 0:
            print("[WARNING] No companies found - check your API key and keywords.")
            return

        # ── Step 2: collect each company ───────────────────────────────
        print("\nStarting detailed fetch ...\n")
        with tqdm(
            total=total_unique,
            desc="Companies",
            unit="co",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ) as pbar:
            for company_number, company_name in unique_companies.items():
                self.collect_company(company_number, company_name)
                pbar.update(1)
                # Extra inter-company pause to be kind to the API
                time.sleep(0.2)

        # ── Step 3: summary ────────────────────────────────────────────
        self._print_summary()

    def _print_summary(self) -> None:
        s = self._stats
        print("\n" + "=" * 60)
        print("  Collection Complete!")
        print("=" * 60)
        print(f"  Companies found   : {s['companies_found']}")
        print(f"  Companies saved   : {s['companies_saved']}")
        print(f"  Officers fetched  : {s['officers_fetched']}")
        print(f"  PSCs fetched      : {s['pscs_fetched']}")
        print(f"  Errors            : {s['errors']}")
        print(f"  Data directory    : {config.DATA_DIR}")
        print("=" * 60)
        print("\nNext step -> run:  python import_to_neo4j.py\n")


# ── Keywords to search – edit this list to broaden or narrow scope ──
SEARCH_KEYWORDS = [
    # Financial services
    "investment",
    "capital",
    "finance",
    "holdings",
    "asset management",
    # Technology
    "technology",
    "software",
    "digital",
    # Energy & infrastructure
    "energy",
    "infrastructure",
    "renewables",
    # Real estate
    "property",
    "real estate",
    "development",
    # Industry & services
    "consulting",
    "media",
    "healthcare",
    "logistics",
    "retail",
    "construction",
]

# Default number of results per keyword (max 100).
DEFAULT_RESULTS_PER_KEYWORD = 50


def main():
    parser = argparse.ArgumentParser(
        description="Collect UBO data from Companies House"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after saving N unique companies (0 = no limit)"
    )
    parser.add_argument(
        "--results",
        type=int,
        default=DEFAULT_RESULTS_PER_KEYWORD,
        help=f"Max results per keyword (max 100, default {DEFAULT_RESULTS_PER_KEYWORD})"
    )
    args = parser.parse_args()

    # Cap results per keyword to 100 (API limit)
    results_per = min(args.results, 100)

    collector = DataCollector(
        results_per_keyword=results_per,
        limit=args.limit
    )
    collector.collect_from_keywords(SEARCH_KEYWORDS)


if __name__ == "__main__":
    main()