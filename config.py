# ============================================================
# config.py – Centralised configuration loader
# ============================================================
# All secrets are read from a .env file at runtime.
# Copy .env.example → .env and fill in your real values.
# NEVER commit .env to version control.

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Load .env file ───────────────────────────────────────────
# Looks for .env in the same directory as this script.
_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
    logger.info(f"Loaded environment from {_ENV_PATH}")
else:
    logger.warning(
        f".env file not found at {_ENV_PATH}. "
        "Copy .env.example → .env and fill in your credentials."
    )

# ── Companies House API ───────────────────────────────────────
COMPANIES_HOUSE_API_KEY: str = os.getenv("COMPANIES_HOUSE_API_KEY", "")
COMPANIES_HOUSE_BASE_URL: str = "https://api.company-information.service.gov.uk"

# Rate-limit budget: 600 requests per 5 minutes (Companies House policy).
# We stay well under by waiting RATE_LIMIT_DELAY seconds between calls.
RATE_LIMIT_REQUESTS: int = 600
RATE_LIMIT_WINDOW_SECONDS: int = 300          # 5 minutes
RATE_LIMIT_DELAY: float = 0.6                 # ~100 req/min → safe headroom

# ── Neo4j / AuraDB connection ─────────────────────────────────
NEO4J_URI: str      = os.getenv("NEO4J_URI", "neo4j+s://xxxxxxxx.databases.neo4j.io")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

# ── Data storage ──────────────────────────────────────────────
# Raw JSON files are written here before import.
DATA_DIR: Path = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)          # create /data/ if it doesn't exist

# ── Validation helper ─────────────────────────────────────────
def validate_config() -> bool:
    """
    Check that all required environment variables are set.
    Returns True if everything looks good, False otherwise.
    """
    errors = []
    if not COMPANIES_HOUSE_API_KEY:
        errors.append("COMPANIES_HOUSE_API_KEY is missing")
    if not NEO4J_PASSWORD:
        errors.append("NEO4J_PASSWORD is missing")
    if NEO4J_URI == "neo4j+s://xxxxxxxx.databases.neo4j.io":
        errors.append("NEO4J_URI still set to placeholder value")

    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        return False

    logger.info("Configuration validated successfully OK")
    return True


def main():
    """Quick sanity-check – run this file directly to test your .env."""
    ok = validate_config()
    if ok:
        print("\n[OK] Config loaded successfully!")
        print(f"   API key  : {'*' * (len(COMPANIES_HOUSE_API_KEY) - 4)}{COMPANIES_HOUSE_API_KEY[-4:]}")
        print(f"   Neo4j URI: {NEO4J_URI}")
        print(f"   Username : {NEO4J_USERNAME}")
    else:
        print("\n[ERROR] Config validation failed – check the errors above.")


if __name__ == "__main__":
    main()
