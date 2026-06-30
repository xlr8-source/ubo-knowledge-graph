# ============================================================
# risk_engine.py – Corporate Risk Intelligence Engine
# ============================================================
import logging
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class RiskIntelligenceEngine:
    """
    Evaluates corporate structures for compliance and financial crime risks,
    including repeated PSCs/officers, shell indicators, and address hotspots.
    """
    def __init__(self, driver):
        self.driver = driver

    def analyze_company_risks(self, company_number: str) -> dict:
        """
        Runs specific risk rules on a single company and returns a detailed risk report.
        """
        flags = []
        score = 0.0
        
        try:
            with self.driver.session() as session:
                # Rule 1: Active company with 0 active officers
                officers = list(session.run(
                    "MATCH (c:Company {company_number: $cn})-[r:HAS_OFFICER]->(o:Officer) "
                    "WHERE r.resigned_date IS NULL OR r.resigned_date = '' "
                    "RETURN count(o) AS active_officers",
                    {"cn": company_number}
                ))
                active_officers_count = officers[0]["active_officers"] if officers else 0
                
                # Retrieve company details for check
                profile_res = list(session.run(
                    "MATCH (c:Company {company_number: $cn}) RETURN c.status AS status, c.address AS address",
                    {"cn": company_number}
                ))
                company_status = profile_res[0]["status"] if profile_res else ""
                company_address = profile_res[0]["address"] if profile_res else ""
                
                if company_status.lower() == "active" and active_officers_count == 0:
                    flags.append({
                        "id": "R_SHELL_NO_OFFICERS",
                        "title": "Potential Shell Structure (No Active Officers)",
                        "severity": "CRITICAL",
                        "description": "The company is registered as 'active' but has zero active directors on record.",
                        "weight": 35.0
                    })
                    score += 35.0
                
                # Rule 2: Company with no registered PSC
                psc_count_res = list(session.run(
                    "MATCH (c:Company {company_number: $cn})-[:HAS_PSC]->(p:PSC) RETURN count(p) AS count",
                    {"cn": company_number}
                ))
                psc_count = psc_count_res[0]["count"] if psc_count_res else 0
                if psc_count == 0:
                    flags.append({
                        "id": "R_NO_PSC",
                        "title": "No Registered Person of Significant Control",
                        "severity": "HIGH",
                        "description": "No beneficial ownership or control filings exist for this entity. Potential transparency risk.",
                        "weight": 30.0
                    })
                    score += 30.0

                # Rule 3: Concentrated ownership (> 75% control by single individual)
                psc_control_res = list(session.run(
                    "MATCH (c:Company {company_number: $cn})-[r:HAS_PSC]->(p:PSC) "
                    "RETURN p.nature_of_control AS noc",
                    {"cn": company_number}
                ))
                for record in psc_control_res:
                    noc = (record["noc"] or "").lower()
                    if "75-to-100" in noc or "significant-influence-or-control" in noc:
                        flags.append({
                            "id": "R_CONCENTRATED_OWNERSHIP",
                            "title": "Highly Concentrated Equity Control",
                            "severity": "MEDIUM",
                            "description": f"Ultimate control resides completely in a single individual or corporate controller.",
                            "weight": 20.0
                        })
                        score += 20.0
                        break

                # Rule 4: Address Hotspot
                if company_address:
                    address_res = list(session.run(
                        "MATCH (c:Company) WHERE c.address = $addr RETURN count(c) AS company_density",
                        {"addr": company_address}
                    ))
                    density = address_res[0]["company_density"] if address_res else 0
                    if density >= 5:
                        flags.append({
                            "id": "R_ADDRESS_HOTSPOT",
                            "title": "Shared Corporate Address Hotspot",
                            "severity": "HIGH",
                            "description": f"This registered office is shared by {density} companies. Often indicator of corporate service provider registration farms.",
                            "weight": 25.0
                        })
                        score += 25.0

                # Rule 5: Suspect status (liquidation, receivership, etc.)
                if any(stat in company_status.lower() for stat in ["liquidation", "receivership", "dissolved"]):
                    flags.append({
                        "id": "R_SUSPECT_STATUS",
                        "title": "Adverse Company Status",
                        "severity": "HIGH",
                        "description": f"The company is in a non-standard operational status: '{company_status.title()}'.",
                        "weight": 30.0
                    })
                    score += 30.0
                    
        except Exception as e:
            logger.error(f"Error running risk rules for company {company_number}: {e}")
            
        final_score = min(max(score, 0.0), 100.0)
        
        return {
            "company_number": company_number,
            "risk_score": final_score,
            "risk_tier": self.get_tier(final_score),
            "flags_triggered": flags
        }

    def analyze_person_risks(self, person_name: str) -> dict:
        """
        Analyze risks associated with an individual (Officer or PSC).
        """
        flags = []
        score = 0.0
        
        try:
            with self.driver.session() as session:
                # Rule 1: Repeated Board seats (> 3 companies)
                boards_res = list(session.run(
                    "MATCH (o:Officer {name: $name})<-[:HAS_OFFICER]-(c:Company) RETURN count(c) AS count",
                    {"name": person_name}
                ))
                boards = boards_res[0]["count"] if boards_res else 0
                if boards > 3:
                    flags.append({
                        "id": "R_SERIAL_DIRECTOR",
                        "title": "Serial Directorship Flag",
                        "severity": "HIGH",
                        "description": f"Individual sits on the board of {boards} different companies. May represent a nominee director.",
                        "weight": 25.0
                    })
                    score += 25.0

                # Rule 2: Repeated PSC roles (> 3 companies)
                pscs_res = list(session.run(
                    "MATCH (p:PSC {name: $name})<-[:HAS_PSC]-(c:Company) RETURN count(c) AS count",
                    {"name": person_name}
                ))
                pscs = pscs_res[0]["count"] if pscs_res else 0
                if pscs > 3:
                    flags.append({
                        "id": "R_REPEAT_PSC",
                        "title": "Repeated Beneficial Ownership",
                        "severity": "CRITICAL",
                        "description": f"Individual registered as Person of Significant Control (PSC) in {pscs} companies.",
                        "weight": 35.0
                    })
                    score += 35.0
                    
        except Exception as e:
            logger.error(f"Error running risk rules for person {person_name}: {e}")

        final_score = min(max(score, 0.0), 100.0)

        return {
            "name": person_name,
            "risk_score": final_score,
            "risk_tier": self.get_tier(final_score),
            "flags_triggered": flags
        }

    def get_tier(self, score: float) -> str:
        if score >= 75.0:
            return "CRITICAL"
        elif score >= 50.0:
            return "HIGH"
        elif score >= 25.0:
            return "MEDIUM"
        return "LOW"

    def get_high_risk_entities(self) -> list[dict]:
        """
        Returns all high-risk or critical-risk companies using batch Cypher queries.

        Replaces the previous N×5 per-company query pattern (251 round trips for 50 companies)
        with 5 aggregate queries that scan all companies at once and return signals in bulk.
        Results are merged in Python, eliminating the primary source of the 30s dashboard load.
        """
        results: dict[str, dict] = {}

        try:
            with self.driver.session() as session:

                # ── Seed: all companies ────────────────────────────────────────
                companies = session.run(
                    "MATCH (c:Company) RETURN c.company_number AS cn, c.name AS name, "
                    "c.status AS status, c.address AS address"
                )
                for record in companies:
                    cn = record["cn"]
                    results[cn] = {
                        "company_number": cn,
                        "name": record["name"] or cn,
                        "_status": (record["status"] or "").lower(),
                        "_address": record["address"] or "",
                        "risk_score": 0.0,
                        "flags": [],
                    }

                # ── Rule 1: Active shell (no active officers) ──────────────────
                active_officers = session.run(
                    "MATCH (c:Company)-[r:HAS_OFFICER]->(o:Officer) "
                    "WHERE (r.resigned_date IS NULL OR r.resigned_date = '') "
                    "RETURN c.company_number AS cn, count(o) AS active_count"
                )
                companies_with_active_officers = {r["cn"] for r in active_officers}

                for cn, data in results.items():
                    if data["_status"] == "active" and cn not in companies_with_active_officers:
                        data["flags"].append({
                            "id": "R_SHELL_NO_OFFICERS",
                            "title": "Potential Shell Structure (No Active Officers)",
                            "severity": "CRITICAL",
                            "description": "The company is registered as 'active' but has zero active directors on record.",
                            "weight": 35.0
                        })
                        data["risk_score"] += 35.0

                # ── Rule 2: No PSC registered ──────────────────────────────────
                has_psc = session.run(
                    "MATCH (c:Company)-[:HAS_PSC]->(p:PSC) RETURN DISTINCT c.company_number AS cn"
                )
                companies_with_psc = {r["cn"] for r in has_psc}

                for cn, data in results.items():
                    if cn not in companies_with_psc:
                        data["flags"].append({
                            "id": "R_NO_PSC",
                            "title": "No Registered Person of Significant Control",
                            "severity": "HIGH",
                            "description": "No beneficial ownership or control filings exist for this entity. Potential transparency risk.",
                            "weight": 30.0
                        })
                        data["risk_score"] += 30.0

                # ── Rule 3: Concentrated ownership (>75%) ──────────────────────
                concentrated = session.run(
                    "MATCH (c:Company)-[:HAS_PSC]->(p:PSC) "
                    "WHERE toLower(p.nature_of_control) CONTAINS '75-to-100' "
                    "   OR toLower(p.nature_of_control) CONTAINS 'significant-influence-or-control' "
                    "RETURN DISTINCT c.company_number AS cn"
                )
                companies_concentrated = {r["cn"] for r in concentrated}

                for cn in companies_concentrated:
                    if cn in results:
                        results[cn]["flags"].append({
                            "id": "R_CONCENTRATED_OWNERSHIP",
                            "title": "Highly Concentrated Equity Control",
                            "severity": "MEDIUM",
                            "description": "Ultimate control resides completely in a single individual or corporate controller.",
                            "weight": 20.0
                        })
                        results[cn]["risk_score"] += 20.0

                # ── Rule 4: Address hotspot (>= 5 companies at same address) ───
                address_counts = session.run(
                    "MATCH (c:Company) WHERE c.address <> '' "
                    "WITH c.address AS addr, count(c) AS density "
                    "WHERE density >= 5 "
                    "RETURN addr, density"
                )
                hotspot_addresses: dict[str, int] = {r["addr"]: r["density"] for r in address_counts}

                for cn, data in results.items():
                    addr = data["_address"]
                    if addr and addr in hotspot_addresses:
                        density = hotspot_addresses[addr]
                        data["flags"].append({
                            "id": "R_ADDRESS_HOTSPOT",
                            "title": "Shared Corporate Address Hotspot",
                            "severity": "HIGH",
                            "description": (
                                f"This registered office is shared by {density} companies. "
                                "Often indicator of corporate service provider registration farms."
                            ),
                            "weight": 25.0
                        })
                        data["risk_score"] += 25.0

                # ── Rule 5: Adverse status ─────────────────────────────────────
                suspect_keywords = ["liquidation", "receivership", "dissolved"]
                for cn, data in results.items():
                    status = data["_status"]
                    if any(kw in status for kw in suspect_keywords):
                        data["flags"].append({
                            "id": "R_SUSPECT_STATUS",
                            "title": "Adverse Company Status",
                            "severity": "HIGH",
                            "description": f"The company is in a non-standard operational status: '{status.title()}'.",
                            "weight": 30.0
                        })
                        data["risk_score"] += 30.0

        except Exception as e:
            logger.error(f"Failed to scan high risk entities: {e}")
            return []

        # Build final output list – only entities with risk signals
        output = []
        for cn, data in results.items():
            score = min(data["risk_score"], 100.0)
            if score > 0.0:
                output.append({
                    "company_number": cn,
                    "name": data["name"],
                    "risk_score": score,
                    "risk_tier": self.get_tier(score),
                    "flags_count": len(data["flags"]),
                    "flags": data["flags"],
                })

        return sorted(output, key=lambda x: x["risk_score"], reverse=True)
