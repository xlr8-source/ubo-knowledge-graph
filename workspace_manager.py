# ============================================================
# workspace_manager.py – Local Workspace & Evidence Exporter
# ============================================================
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """
    Manages active cases, bookmarks, search history, comparisons, 
    and exports them to a local JSON file for GitHub sharing.
    """
    def __init__(self, storage_path: str = "workspace_cases.json"):
        self.storage_path = Path(__file__).resolve().parent / storage_path
        self.data = {
            "bookmarked_companies": [],
            "bookmarked_people": [],
            "search_history": [],
            "cases": {}
        }
        self.load()

    def load(self):
        """Load cases and bookmarks from disk if existing."""
        if self.storage_path.exists():
            try:
                content = self.storage_path.read_text(encoding="utf-8")
                self.data = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load workspace storage file: {e}")

    def save(self):
        """Save workspace cases and bookmarks to disk."""
        try:
            self.storage_path.write_text(
                json.dumps(self.data, indent=4),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save workspace file: {e}")

    def toggle_bookmark_company(self, company_number: str, name: str):
        """Add or remove a company bookmark."""
        for item in self.data["bookmarked_companies"]:
            if item["company_number"] == company_number:
                self.data["bookmarked_companies"].remove(item)
                self.save()
                return False # Removed
                
        self.data["bookmarked_companies"].append({
            "company_number": company_number,
            "name": name
        })
        self.save()
        return True # Added

    def toggle_bookmark_person(self, person_name: str):
        """Add or remove a person bookmark."""
        if person_name in self.data["bookmarked_people"]:
            self.data["bookmarked_people"].remove(person_name)
            self.save()
            return False
        else:
            self.data["bookmarked_people"].append(person_name)
            self.save()
            return True

    def is_company_bookmarked(self, company_number: str) -> bool:
        return any(item["company_number"] == company_number for item in self.data["bookmarked_companies"])

    def is_person_bookmarked(self, person_name: str) -> bool:
        return person_name in self.data["bookmarked_people"]

    def log_search(self, query: str, search_type: str = "Company"):
        """Save a search string to history, keeping it clean and distinct."""
        history = self.data.get("search_history", [])
        # Remove old if matches to move it to the top
        for item in list(history):
            if item["query"] == query and item["type"] == search_type:
                history.remove(item)
        
        history.insert(0, {"query": query, "type": search_type})
        self.data["search_history"] = history[:15] # Keep last 15
        self.save()

    def clear_search_history(self):
        self.data["search_history"] = []
        self.save()

    def generate_evidence_package(self, company_details: dict, officers: list, pscs: list, risks: dict) -> str:
        """
        Generate a structured, human-readable text package summarizing 
        beneficial ownership structure and risk signals for exports.
        """
        report_lines = []
        report_lines.append("="*80)
        report_lines.append("              CORPORATE BENEFICIAL OWNERSHIP EVIDENCE BRIEF")
        report_lines.append("="*80)
        report_lines.append(f"Company Name:        {company_details.get('name', 'N/A')}")
        report_lines.append(f"Company Number:      {company_details.get('company_number', 'N/A')}")
        report_lines.append(f"Registration Status: {company_details.get('status', 'N/A')}")
        report_lines.append(f"SIC Classifications: {', '.join(company_details.get('sic_codes', []))}")
        report_lines.append(f"Registered Address:  {company_details.get('address', 'N/A')}")
        report_lines.append(f"Risk Intelligence Score: {risks.get('risk_score', 0)}% ({risks.get('risk_tier', 'LOW')})")
        report_lines.append("-"*80)
        
        report_lines.append("\nACTIVE RISK ALERTS:")
        if not risks.get("flags_triggered"):
            report_lines.append("  [✓] No critical structural compliance risks flagged.")
        else:
            for idx, flag in enumerate(risks["flags_triggered"]):
                report_lines.append(f"  [{idx+1}] [{flag['severity']}] {flag['title']}")
                report_lines.append(f"      Details: {flag['description']}")
        
        report_lines.append("\nOFFICIAL CORPORATE APPOINTMENTS:")
        if not officers:
            report_lines.append("  No active officers found on record.")
        else:
            for o in officers:
                status = "Resigned" if o.get('resigned_date') else "Active"
                report_lines.append(f"  - {o.get('name')} | Role: {o.get('role')} ({status})")
                
        report_lines.append("\nBENEFICIAL OWNERSHIP DETAILS (PSCs):")
        if not pscs:
            report_lines.append("  No Persons of Significant Control (PSCs) registered.")
        else:
            for p in pscs:
                report_lines.append(f"  - {p.get('name')} | Nationality: {p.get('nationality') or 'N/A'}")
                report_lines.append(f"    Basis of Control: {p.get('nature_of_control')}")
                
        report_lines.append("\n"+"="*80)
        report_lines.append("END OF EVIDENCE PACKAGE")
        report_lines.append("="*80)
        return "\n".join(report_lines)
