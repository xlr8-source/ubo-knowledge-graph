# ============================================================
# scoring_engine.py – Corporate Ownership Scoring & Priority Engine
# ============================================================

def calculate_influence_score(degree: int, control_percentage: float, directorship_count: int) -> float:
    """
    Calculate an Influence Score from 0 to 100.
    Based on:
      - directorship_count (number of companies an officer/PSC is associated with)
      - control_percentage (approximate percentage of ownership/control: 25, 50, 75, or 100)
      - degree (total direct relationships in the graph)
    """
    # Weighting factors
    w_degree = min(degree * 5.0, 30.0)             # max 30 pts for overall connectivity
    w_boards = min(directorship_count * 15.0, 45.0)  # max 45 pts for holding multiple board seats
    w_control = min(control_percentage, 25.0)        # max 25 pts for direct equity control
    
    score = w_degree + w_boards + w_control
    return min(max(score, 0.0), 100.0)


def calculate_control_score(nature_of_control_str: str) -> float:
    """
    Map Companies House nature-of-control strings to a numeric control strength (0 to 100).
    """
    noc = (nature_of_control_str or "").lower()
    if not noc:
        return 0.0
    
    # Check for highest control tier first
    if "75-to-100" in noc or "significant-influence-or-control" in noc:
        return 100.0
    if "50-to-75" in noc:
        return 75.0
    if "25-to-50" in noc:
        return 50.0
    
    # Standard roles or lower tier control
    return 25.0


def calculate_investigation_priority(risk_score: float, influence_score: float, connectivity_score: float) -> float:
    """
    Compute an Investigation Priority Score (0 to 100) to bubble up targets for AML/KYC.
    Formula: 50% Risk + 25% Influence + 25% Connectivity
    """
    priority = (0.50 * risk_score) + (0.25 * influence_score) + (0.25 * connectivity_score)
    return min(max(priority, 0.0), 100.0)


def get_risk_tier(risk_score: float) -> str:
    """Categorise risk scores into standard operational intelligence tiers."""
    if risk_score >= 75.0:
        return "CRITICAL"
    elif risk_score >= 50.0:
        return "HIGH"
    elif risk_score >= 25.0:
        return "MEDIUM"
    return "LOW"
