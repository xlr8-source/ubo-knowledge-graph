# ============================================================
# companies_house_client.py – Companies House REST API wrapper
# ============================================================
# Authentication: API key used as the HTTP Basic-Auth *username*;
# password must be an empty string (Companies House spec).
# Docs: https://developer.company-information.service.gov.uk/

import time
import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

logger = logging.getLogger(__name__)


class CompaniesHouseClient:
    """
    Thin wrapper around the Companies House REST API.

    Usage:
        client = CompaniesHouseClient()
        results = client.search_companies("Barclays", limit=5)
    """

    def __init__(self):
        self.base_url = config.COMPANIES_HOUSE_BASE_URL
        self.api_key  = config.COMPANIES_HOUSE_API_KEY
        self.delay    = config.RATE_LIMIT_DELAY        # seconds between calls

        if not self.api_key:
            raise ValueError(
                "COMPANIES_HOUSE_API_KEY is not set. "
                "Check your .env file."
            )

        # ── Session with automatic retries on network errors ──────────
        # Retries on connection/read errors but NOT on HTTP 4xx/5xx
        # (those are handled explicitly below).
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)

        # Companies House expects the API key as the HTTP Basic username.
        # The password MUST be an empty string.
        self.session.auth = (self.api_key, "")
        self.session.headers.update({"Accept": "application/json"})

        logger.info("CompaniesHouseClient initialised ✓")

    # ── Private helpers ───────────────────────────────────────────────

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """
        Make a GET request and return the parsed JSON body.
        Returns None if the resource is not found (404) or has no data.
        Raises RuntimeError for unexpected HTTP errors.
        """
        url = f"{self.base_url}{endpoint}"
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"GET {url} params={params} (attempt {attempt}/{max_attempts})")
                response = self.session.get(url, params=params, timeout=15)

                # Respect rate-limit delay *after* every request.
                time.sleep(self.delay)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 404:
                    logger.warning(f"404 Not Found – {url}")
                    return None

                if response.status_code == 401:
                    raise RuntimeError(
                        "401 Unauthorised – check your COMPANIES_HOUSE_API_KEY"
                    )

                if response.status_code == 429:
                    if attempt < max_attempts:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            sleep_seconds = int(retry_after) if retry_after else 60
                        except ValueError:
                            sleep_seconds = 60
                        logger.warning(f"429 Rate Limited on attempt {attempt}/{max_attempts} – sleeping {sleep_seconds} s …")
                        time.sleep(sleep_seconds)
                        continue
                    else:
                        logger.error(f"429 Rate Limited – max retries ({max_attempts}) reached for {url}")
                        return None

                logger.error(
                    f"Unexpected HTTP {response.status_code} for {url}: "
                    f"{response.text[:200]}"
                )
                return None

            except requests.exceptions.Timeout:
                logger.error(f"Request timed out: {url} (attempt {attempt}/{max_attempts})")
                if attempt >= max_attempts:
                    return None
            except requests.exceptions.ConnectionError as exc:
                logger.error(f"Connection error for {url}: {exc} (attempt {attempt}/{max_attempts})")
                if attempt >= max_attempts:
                    return None

    # ── Public API methods ────────────────────────────────────────────

    def search_companies(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search for companies by name keyword.
        Endpoint: GET /search/companies?q={query}&items_per_page={limit}

        Returns a list of company summary dicts (may be empty).
        """
        logger.info(f"Searching companies: '{query}' (limit={limit})")
        data = self._get("/search/companies", params={"q": query, "items_per_page": limit})
        if not data:
            return []
        items = data.get("items", [])
        logger.info(f"  → {len(items)} result(s) found")
        return items

    def get_company_profile(self, company_number: str) -> Optional[dict]:
        """
        Fetch the full company profile.
        Endpoint: GET /company/{company_number}

        Returns the profile dict, or None if not found.
        """
        company_number = company_number.upper().strip()
        logger.info(f"Fetching profile: {company_number}")
        return self._get(f"/company/{company_number}")

    def get_officers(self, company_number: str) -> list[dict]:
        """
        Fetch active and resigned officers for a company.
        Endpoint: GET /company/{company_number}/officers

        Returns a list of officer dicts (may be empty).
        """
        company_number = company_number.upper().strip()
        logger.info(f"Fetching officers: {company_number}")

        # The API paginates at 35 items; loop to get all pages.
        all_officers = []
        start_index  = 0
        page_size    = 35

        while True:
            data = self._get(
                f"/company/{company_number}/officers",
                params={"items_per_page": page_size, "start_index": start_index},
            )
            if not data:
                break

            items = data.get("items", [])
            all_officers.extend(items)

            total = data.get("total_results", 0)
            start_index += page_size
            if start_index >= total:
                break          # fetched every page

        logger.info(f"  → {len(all_officers)} officer(s)")
        return all_officers

    def get_psc(self, company_number: str) -> list[dict]:
        """
        Fetch Persons of Significant Control (PSCs) for a company.
        Endpoint: GET /company/{company_number}/persons-with-significant-control

        A PSC is someone who:
          - Owns >25 % of shares / voting rights, OR
          - Has the right to appoint / remove directors.

        Returns a list of PSC dicts (may be empty).
        """
        company_number = company_number.upper().strip()
        logger.info(f"Fetching PSCs: {company_number}")

        all_pscs   = []
        start_index = 0
        page_size   = 25

        while True:
            data = self._get(
                f"/company/{company_number}/persons-with-significant-control",
                params={"items_per_page": page_size, "start_index": start_index},
            )
            if not data:
                break

            items = data.get("items", [])
            all_pscs.extend(items)

            total = data.get("total_results", 0)
            start_index += page_size
            if start_index >= total:
                break

        logger.info(f"  → {len(all_pscs)} PSC(s)")
        return all_pscs


def main():
    """Quick smoke-test – searches for 'Apple' and prints officer count."""
    client = CompaniesHouseClient()

    # ── Search ────────────────────────────────────────────────
    results = client.search_companies("Apple", limit=3)
    if not results:
        print("No results found – check your API key.")
        return

    # Take the first result and fetch its full data.
    first = results[0]
    company_number = first.get("company_number", "")
    print(f"\nFirst result: {first.get('title')} ({company_number})")

    profile  = client.get_company_profile(company_number)
    officers = client.get_officers(company_number)
    pscs     = client.get_psc(company_number)

    print(f"  Status   : {profile.get('company_status') if profile else 'N/A'}")
    print(f"  Officers : {len(officers)}")
    print(f"  PSCs     : {len(pscs)}")


if __name__ == "__main__":
    main()
