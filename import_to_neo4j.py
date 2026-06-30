# ============================================================
# import_to_neo4j.py – Load collected JSON data into Neo4j AuraDB
# ============================================================
# Reads every company_*.json file in /data/ and creates the graph:
#
#   (:Company)-[:HAS_OFFICER]->(:Officer)
#   (:Company)-[:HAS_PSC]->(:PSC)
#
# Usage:
#   python import_to_neo4j.py              # merge into existing data
#   python import_to_neo4j.py --clear      # wipe database first
#
# Pre-requisites:
#   • Neo4j AuraDB Free instance running
#   • .env file populated with NEO4J_URI / USERNAME / PASSWORD

import json
import logging
import argparse
from pathlib import Path

from neo4j import GraphDatabase, exceptions as neo4j_exc
from tqdm import tqdm

import config

logger = logging.getLogger(__name__)


# ── Cypher templates ──────────────────────────────────────────────────
# MERGE is used throughout so re-running this script is safe.

CYPHER_CREATE_INDEXES = [
    # Unique constraints also create an index automatically.
    "CREATE CONSTRAINT company_number_unique IF NOT EXISTS "
    "FOR (c:Company) REQUIRE c.company_number IS UNIQUE",

    "CREATE INDEX officer_name_idx IF NOT EXISTS "
    "FOR (o:Officer) ON (o.name)",

    "CREATE INDEX psc_name_idx IF NOT EXISTS "
    "FOR (p:PSC) ON (p.name)",
]

CYPHER_MERGE_COMPANY = """
MERGE (c:Company {company_number: $company_number})
SET
  c.name              = $name,
  c.status            = $status,
  c.company_type      = $company_type,
  c.incorporation_date= $incorporation_date,
  c.address           = $address,
  c.sic_codes         = $sic_codes
RETURN c
"""

CYPHER_MERGE_OFFICER = """
MATCH (c:Company {company_number: $company_number})
MERGE (o:Officer {name: $name, role: $role})
SET
  o.appointed_date = $appointed_date,
  o.resigned_date  = $resigned_date,
  o.nationality    = $nationality,
  o.officer_role   = $role
MERGE (c)-[r:HAS_OFFICER]->(o)
SET r.appointed_date = $appointed_date,
    r.resigned_date  = $resigned_date
"""

CYPHER_MERGE_PSC = """
MATCH (c:Company {company_number: $company_number})
MERGE (p:PSC {name: $name})
SET
  p.nature_of_control = $nature_of_control,
  p.notified_on       = $notified_on,
  p.nationality       = $nationality,
  p.country_of_residence = $country_of_residence,
  p.kind              = $kind
MERGE (c)-[r:HAS_PSC]->(p)
SET r.nature_of_control = $nature_of_control,
    r.notified_on       = $notified_on
"""

CYPHER_CLEAR_ALL = "MATCH (n) DETACH DELETE n"


# ── Helper functions ──────────────────────────────────────────────────

def _safe_address(registered_office: dict) -> str:
    """Flatten a registered office address dict into a single string."""
    if not registered_office:
        return ""
    parts = [
        registered_office.get("address_line_1", ""),
        registered_office.get("address_line_2", ""),
        registered_office.get("locality", ""),
        registered_office.get("postal_code", ""),
        registered_office.get("country", ""),
    ]
    return ", ".join(p for p in parts if p)


def _safe_str(value) -> str:
    """Return a string or empty string (never None into Neo4j)."""
    return str(value) if value is not None else ""


def _safe_list(value) -> list:
    """Return a list or empty list."""
    return value if isinstance(value, list) else []


# ── Neo4j importer class ──────────────────────────────────────────────

class Neo4jImporter:
    """
    Connects to Neo4j AuraDB and imports company data from JSON files.
    """

    def __init__(self):
        logger.info(f"Connecting to Neo4j at {config.NEO4J_URI} …")
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
            )
            self.driver.verify_connectivity()
            logger.info("Neo4j connection established OK")
        except neo4j_exc.AuthError:
            raise RuntimeError(
                "Neo4j authentication failed – check NEO4J_USERNAME and NEO4J_PASSWORD in .env"
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Neo4j: {exc}")

    def close(self):
        self.driver.close()
        logger.info("Neo4j connection closed.")

    # ── Schema setup ──────────────────────────────────────────────────

    def create_indexes(self):
        """Create uniqueness constraints and indexes for fast lookups."""
        with self.driver.session() as session:
            for cypher in CYPHER_CREATE_INDEXES:
                session.run(cypher)
        logger.info("Indexes and constraints created OK")

    # ── Data wipe ─────────────────────────────────────────────────────

    def clear_database(self):
        """Delete all nodes and relationships (use with care!)."""
        print("\n[WARNING] Clearing all existing data ...")
        with self.driver.session() as session:
            session.run(CYPHER_CLEAR_ALL)
        print("   Database cleared.\n")

    # ── Per-entity importers ──────────────────────────────────────────

    def import_company(self, session, company_number: str, profile: dict) -> None:
        """MERGE a Company node from its profile dict."""
        ro = profile.get("registered_office_address", {})
        session.run(
            CYPHER_MERGE_COMPANY,
            company_number=company_number,
            name=_safe_str(profile.get("company_name")),
            status=_safe_str(profile.get("company_status")),
            company_type=_safe_str(profile.get("type")),
            incorporation_date=_safe_str(profile.get("date_of_creation")),
            address=_safe_address(ro),
            sic_codes=_safe_list(profile.get("sic_codes")),
        )

    def import_officer(self, session, company_number: str, officer: dict) -> None:
        """MERGE an Officer node and attach it to the Company."""
        name = _safe_str(
            officer.get("name") or
            f"{officer.get('forename', '')} {officer.get('surname', '')}".strip()
        )
        if not name:
            return   # skip malformed entries

        session.run(
            CYPHER_MERGE_OFFICER,
            company_number=company_number,
            name=name,
            role=_safe_str(officer.get("officer_role")),
            appointed_date=_safe_str(officer.get("appointed_on")),
            resigned_date=_safe_str(officer.get("resigned_on")),
            nationality=_safe_str(officer.get("nationality")),
        )

    def import_psc(self, session, company_number: str, psc: dict) -> None:
        """MERGE a PSC node and attach it to the Company."""
        name = _safe_str(psc.get("name"))
        if not name:
            return   # skip entries with no usable name

        # nature_of_control is a list of strings in the API response.
        noc = psc.get("natures_of_control", [])
        noc_str = "; ".join(noc) if isinstance(noc, list) else _safe_str(noc)

        session.run(
            CYPHER_MERGE_PSC,
            company_number=company_number,
            name=name,
            nature_of_control=noc_str,
            notified_on=_safe_str(psc.get("notified_on")),
            nationality=_safe_str(psc.get("nationality")),
            country_of_residence=_safe_str(psc.get("country_of_residence")),
            kind=_safe_str(psc.get("kind")),
        )

    # ── Main import pipeline ──────────────────────────────────────────

    def import_all(self, data_dir: Path, limit: int = 100) -> None:
        """
        Read company_*.json files in data_dir and import into Neo4j.
        Uses a single session per file (auto-committed transactions).
        """
        json_files = sorted(data_dir.glob("company_*.json"))
        if not json_files:
            print(f"\n[WARNING] No data files found in {data_dir}")
            print("    Run data_collector.py first.\n")
            return

        total_files = len(json_files)
        if limit > 0:
            json_files = json_files[:limit]
            print(f"\n[IMPORT] Importing {len(json_files)} out of {total_files} company file(s) (limit={limit}) ...\n")
        else:
            print(f"\n[IMPORT] Importing all {total_files} company file(s) ...\n")

        stats = {"companies": 0, "officers": 0, "pscs": 0, "errors": 0}

        with tqdm(json_files, desc="Importing", unit="file") as pbar:
            for json_path in pbar:
                try:
                    raw = json.loads(json_path.read_text(encoding="utf-8"))
                    company_number = raw.get("company_number", "")
                    profile        = raw.get("profile", {})
                    officers       = raw.get("officers", [])
                    pscs           = raw.get("pscs", [])

                    with self.driver.session() as session:
                        # Company node
                        self.import_company(session, company_number, profile)
                        stats["companies"] += 1

                        # Officer nodes + relationships
                        for officer in officers:
                            self.import_officer(session, company_number, officer)
                            stats["officers"] += 1

                        # PSC nodes + relationships
                        for psc in pscs:
                            self.import_psc(session, company_number, psc)
                            stats["pscs"] += 1

                    pbar.set_postfix(
                        co=stats["companies"],
                        off=stats["officers"],
                        psc=stats["pscs"],
                    )

                except Exception as exc:
                    logger.error(f"Error importing {json_path.name}: {exc}", exc_info=True)
                    stats["errors"] += 1

        # ── Summary ────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Import Complete!")
        print("=" * 60)
        print(f"  Companies imported : {stats['companies']}")
        print(f"  Officers imported  : {stats['officers']}")
        print(f"  PSCs imported      : {stats['pscs']}")
        print(f"  Errors             : {stats['errors']}")
        print("=" * 60)
        print("\nNext step -> open Neo4j Bloom and explore your graph!\n")


def main():
    parser = argparse.ArgumentParser(
        description="Import UBO data into Neo4j AuraDB"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Wipe the database before importing (use carefully!).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Limit the number of companies to import (default: 100). Pass 0 or a negative number to import all.",
    )
    args = parser.parse_args()

    # Validate config before touching Neo4j
    if not config.validate_config():
        print("\n❌  Fix the config errors above before running the import.")
        return

    importer = Neo4jImporter()
    try:
        if args.clear:
            importer.clear_database()

        importer.create_indexes()
        importer.import_all(config.DATA_DIR, limit=args.limit)

    finally:
        importer.close()


if __name__ == "__main__":
    main()
