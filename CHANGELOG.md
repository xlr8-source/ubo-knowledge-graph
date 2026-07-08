# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Community standards documentation (CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md)
- Issue and pull request templates

### Changed

### Fixed

### Deprecated

### Removed

## [1.0.0] - 2026-07-08

### Added

- Initial release of UBO Knowledge Graph
- Neo4j graph database schema for corporate ownership structures
- Streamlit intelligence workbench ("VEIL") with 6 pages:
  - Overview: Registry-wide triage and network topology
  - Entity Explorer: Company-specific analytics and drilldown
  - People Intelligence: Officer and PSC analysis
  - Risk & Analytics: Compliance queue and graph diagnostics
  - Workspace: Bookmarking and company comparison
  - Query Studio: Live Cypher editor with AML reference templates
- Companies House API integration with rate-limiting and exponential backoff
- RiskIntelligenceEngine for AML/KYC compliance pattern detection
- ScoringEngine for influence, control, and investigation priority scoring
- NetworkX-based analytics: PageRank, Louvain community detection, centrality measures
- Visual structure graphs with pyvis: community coloring, spotlight focus, cross-company links
- Unit test suite for engines
- Documentation:
  - Comprehensive README with quick start and troubleshooting
  - Project structure overview
  - Graph schema documentation
  - Setup guide for Windows, macOS, and Linux
  - Detailed rate limiting and risk engine documentation

### Known Limitations

- Name-collision caveat: Officer nodes merged on {name, role}, PSC nodes on {name} alone
- Two distinct individuals with the same name may be incorrectly merged
- Queries.cypher is reference-only; Query Studio templates are independent

---

## Release Notes

For detailed information about releases, see [GitHub Releases](https://github.com/xlr8-source/ubo-knowledge-graph/releases).

### Upgrading

When upgrading between versions:

1. Back up your Neo4j database
2. Review this CHANGELOG for breaking changes
3. Update your `.env` file if new environment variables are introduced
4. Re-run `python -m unittest tests/test_engines.py` to verify compatibility
5. Clear and re-import data if schema changes are noted

### Support for Older Versions

Only the latest version is actively maintained. Security updates may be backported to previous versions upon request.
