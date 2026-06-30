import sys
import unittest
from unittest.mock import MagicMock
from pathlib import Path

# Add root folder to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scoring_engine import (
    calculate_influence_score,
    calculate_control_score,
    calculate_investigation_priority,
    get_risk_tier
)
from risk_engine import RiskIntelligenceEngine


class TestScoringEngine(unittest.TestCase):
    
    def test_calculate_influence_score(self):
        # Base case
        score = calculate_influence_score(degree=2, control_percentage=25.0, directorship_count=1)
        # w_degree = min(2 * 5.0, 30.0) = 10.0
        # w_boards = min(1 * 15.0, 45.0) = 15.0
        # w_control = min(25.0, 25.0) = 25.0
        # Total = 50.0
        self.assertEqual(score, 50.0)
        
        # High connectivity and multiple boards
        score_high = calculate_influence_score(degree=10, control_percentage=100.0, directorship_count=4)
        # w_degree = min(50.0, 30.0) = 30.0
        # w_boards = min(60.0, 45.0) = 45.0
        # w_control = min(100.0, 25.0) = 25.0
        # Total = 100.0
        self.assertEqual(score_high, 100.0)
        
        # Zero bounds
        score_zero = calculate_influence_score(0, 0.0, 0)
        self.assertEqual(score_zero, 0.0)

    def test_calculate_control_score(self):
        # 75 to 100 control
        self.assertEqual(calculate_control_score("ownership-of-shares-75-to-100-percent"), 100.0)
        self.assertEqual(calculate_control_score("significant-influence-or-control"), 100.0)
        
        # 50 to 75 control
        self.assertEqual(calculate_control_score("voting-rights-50-to-75-percent"), 75.0)
        
        # 25 to 50 control
        self.assertEqual(calculate_control_score("ownership-of-shares-25-to-50-percent"), 50.0)
        
        # Unknown/missing
        self.assertEqual(calculate_control_score(""), 0.0)
        self.assertEqual(calculate_control_score(None), 0.0)
        
        # Other fallback roles
        self.assertEqual(calculate_control_score("some-minor-control"), 25.0)

    def test_calculate_investigation_priority(self):
        # 50% Risk + 25% Influence + 25% Connectivity
        priority = calculate_investigation_priority(risk_score=80.0, influence_score=60.0, connectivity_score=40.0)
        # (0.50 * 80) + (0.25 * 60) + (0.25 * 40) = 40 + 15 + 10 = 65.0
        self.assertEqual(priority, 65.0)
        
        # Caps check
        priority_max = calculate_investigation_priority(120.0, 110.0, 150.0)
        self.assertEqual(priority_max, 100.0)

    def test_get_risk_tier(self):
        self.assertEqual(get_risk_tier(90.0), "CRITICAL")
        self.assertEqual(get_risk_tier(60.0), "HIGH")
        self.assertEqual(get_risk_tier(40.0), "MEDIUM")
        self.assertEqual(get_risk_tier(10.0), "LOW")


class TestRiskEngine(unittest.TestCase):
    
    def test_get_tier(self):
        # Initialize with dummy driver
        dummy_driver = MagicMock()
        engine = RiskIntelligenceEngine(dummy_driver)
        
        self.assertEqual(engine.get_tier(80.0), "CRITICAL")
        self.assertEqual(engine.get_tier(55.0), "HIGH")
        self.assertEqual(engine.get_tier(30.0), "MEDIUM")
        self.assertEqual(engine.get_tier(15.0), "LOW")


if __name__ == "__main__":
    unittest.main()
