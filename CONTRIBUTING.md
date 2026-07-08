# Contributing to UBO Knowledge Graph

Thank you for your interest in contributing to the UBO Knowledge Graph project! This document outlines our development workflow, code expectations, and how to submit contributions.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style & Standards](#code-style--standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Getting Started

### Prerequisites

Ensure you have the following installed:
- Python 3.10+
- Git
- A Neo4j AuraDB account (free tier available)
- A Companies House API key

### Local Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/ubo-knowledge-graph.git
   cd ubo-knowledge-graph
   git remote add upstream https://github.com/xlr8-source/ubo-knowledge-graph.git
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   # or
   .venv\Scripts\activate.bat  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your `.env` file**
   ```bash
   cp .env.example .env
   # Fill in your real credentials
   ```

5. **Verify your setup**
   ```bash
   python config.py
   ```

---

## Development Workflow

### Branch Naming

Use descriptive branch names with prefixes:

- `feature/` — new functionality
  ```bash
  git checkout -b feature/add-psc-filtering
  ```

- `fix/` — bug fixes
  ```bash
  git checkout -b fix/neo4j-connection-retry
  ```

- `docs/` — documentation improvements
  ```bash
  git checkout -b docs/setup-guide
  ```

- `refactor/` — code cleanup without changing behavior
  ```bash
  git checkout -b refactor/scoring-engine
  ```

### Commit Conventions

Write clear, concise commit messages:

- **Good:** `Add batch risk scoring for shell companies` or `Fix AuraDB auto-pause handling in config.py`
- **Avoid:** `update stuff`, `bug fix`, `changes`

Example commit:
```bash
git commit -m "Add batch risk scoring for shell companies

- Implement RiskIntelligenceEngine.score_batch()
- Add weight-based rule aggregation
- Include CRITICAL/HIGH/MEDIUM/LOW tier logic
- Tested against 100-company subset"
```

### Keep Your Fork Synced

Before starting work and before submitting a PR:

```bash
git fetch upstream
git rebase upstream/main
```

---

## Code Style & Standards

### Python Code

- **Format:** Follow [PEP 8](https://pep8.org/) conventions
- **Line length:** 88 characters (Black standard)
- **Type hints:** Use them for public functions and class methods

Example:
```python
def score_batch(
    self, company_ids: list[str], risk_weights: dict[str, int]
) -> dict[str, int]:
    """
    Calculate risk scores for a batch of companies.
    
    Args:
        company_ids: List of company numbers
        risk_weights: Mapping of rule names to weight values
        
    Returns:
        Dictionary mapping company_id to risk score
    """
    scores = {}
    for company_id in company_ids:
        scores[company_id] = self._evaluate_rules(company_id, risk_weights)
    return scores
```

### Cypher Queries

- Write queries in `queries.cypher` as reference documentation
- Add inline comments explaining complex patterns
- Use `MATCH`, `WHERE`, `RETURN` on separate lines for readability

Example:
```cypher
// Find nominee directors: officers with 5+ company appointments
MATCH (officer:Officer)-[:APPOINTED_TO]->(:Company)
WITH officer, count(*) as appointment_count
WHERE appointment_count >= 5
RETURN officer, appointment_count
ORDER BY appointment_count DESC
```

### Documentation

- Docstrings: Use Google-style format (see `risk_engine.py` for examples)
- Comments: Explain *why*, not *what* — code should be self-documenting
- Update README if your change affects setup, usage, or features

---

## Testing

### Running Tests

```bash
# Run all tests
python -m unittest tests/test_engines.py

# Run specific test class
python -m unittest tests.test_engines.RiskEngineTests

# Run with verbose output
python -m unittest tests/test_engines.py -v
```

### Writing Tests

- Add tests to `tests/test_engines.py` for business logic (RiskEngine, ScoringEngine)
- Mock Neo4j connections — do not require a live database for unit tests
- Aim for >80% coverage of new code

Example:
```python
class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        """Initialize mock data for each test."""
        self.engine = RiskIntelligenceEngine(mock_connection=True)
    
    def test_shell_company_detection(self):
        """Shell structure flag triggers when active company has no directors."""
        result = self.engine._check_shell_structure(
            company_status="active",
            active_director_count=0
        )
        self.assertEqual(result, 35)  # Expected weight for this rule
```

### Before Submitting

- [ ] All tests pass locally: `python -m unittest tests/test_engines.py`
- [ ] No import errors: `python -c "import dashboard.app; import config; import risk_engine"`
- [ ] Code follows PEP 8 (use `black --check .` if available)

---

## Submitting Changes

### Before You Start

1. Check [open issues](https://github.com/xlr8-source/ubo-knowledge-graph/issues) to see if your idea is already being discussed
2. For large changes, consider opening an issue first to discuss your approach
3. Keep changes focused — one feature or fix per PR

### Making Your Changes

1. Edit files in your branch
2. Test locally (see [Testing](#testing))
3. Commit with clear messages (see [Commit Conventions](#commit-conventions))
4. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

---

## Pull Request Process

### Before Submitting

1. **Ensure your branch is up to date with main:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   git push origin feature/your-feature-name --force-with-lease
   ```

2. **Run tests one final time:**
   ```bash
   python -m unittest tests/test_engines.py
   ```

3. **Update documentation** if needed:
   - Does README need updating? (e.g., new setup step, new page)
   - Should queries.cypher be updated?
   - Is there a new risk flag or scoring rule? Add it to this doc or the README

### Creating the PR

1. Go to [GitHub](https://github.com/xlr8-source/ubo-knowledge-graph) and click **"Compare & pull request"**
2. Use the PR template (auto-populated) — fill in all sections:
   - **Description:** What does this change do?
   - **Related issues:** Link to any related issues (`Closes #123`)
   - **Type of change:** (Bug fix / Feature / Refactor / Docs)
   - **Checklist:** Verify tests pass and docs are updated

3. Submit and address review feedback:
   - Changes requested? Commit and push — no need to close and reopen
   - Merge conflicts? Rebase on main and force-push
   - Unsure about feedback? Ask questions in the PR thread

### Acceptance Criteria

Your PR will be merged when:
- ✅ All tests pass
- ✅ Documentation is updated (if applicable)
- ✅ Code follows project style standards
- ✅ At least one maintainer has approved the changes
- ✅ No merge conflicts exist

---

## Reporting Issues

### Reporting Bugs

Use the **[Bug Report](https://github.com/xlr8-source/ubo-knowledge-graph/issues/new?template=bug.md)** template and include:

- Clear description of what went wrong
- Steps to reproduce
- Expected behavior vs. actual behavior
- Python version, OS, and Neo4j version
- Relevant error messages or logs

### Suggesting Features

Use the **[Feature Request](https://github.com/xlr8-source/ubo-knowledge-graph/issues/new?template=feature.md)** template and include:

- Clear description of the feature
- Why it would be useful
- Possible implementation approach (if you have ideas)
- Example use case

---

## Questions?

- Check the [README](README.md) first — it covers setup, running, and common issues
- Review [Troubleshooting](README.md#troubleshooting) for known solutions
- Open an issue with the `question` label if you're stuck

---

## License

By contributing to this project, you agree that your contributions will be licensed under its [MIT License](LICENSE).

Thank you for making UBO Knowledge Graph better! 🎉
