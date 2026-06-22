"""
Unit tests for the CarbonRoute Emissions Engine.
Verify emissions math, multipliers, and SLA audit functionality.
"""

import sys
import os

# Append the directory containing emissions_engine to sys.path so we can import it
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from emissions_engine import CarbonEmissionsEngine


def test_base_emissions():
    """Verify base emissions calculation matches static formula."""
    # 100 km, 10 tonnes, HGV average (base factor = 62.0)
    # Expected base = 100 * 10 * 62.0 = 62,000 g = 62.0 kg
    res = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD",
        distance_km=100.0,
        weight_tonnes=10.0,
        utilization_ratio=1.0,
        congestion_level=0.0,
        weather_severity=0.0,
        empty_backhaul=False
    )
    
    assert res["mode"] == "ROAD"
    assert res["base_emissions_kg"] == 62.0
    assert res["adjusted_emissions_kg"] == 62.0
    assert res["carbon_variance_kg"] == 0.0
    assert res["multipliers"]["utilization"] == 1.0
    assert res["multipliers"]["congestion"] == 1.0
    assert res["multipliers"]["weather"] == 1.0


def test_underloading_multiplier():
    """Verify underutilization increases emission footprint."""
    res_full = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, utilization_ratio=1.0
    )
    res_underloaded = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, utilization_ratio=0.5
    )
    
    assert res_underloaded["adjusted_emissions_kg"] > res_full["adjusted_emissions_kg"]
    assert res_underloaded["multipliers"]["utilization"] > 1.0


def test_congestion_and_weather_impact():
    """Verify traffic and severe weather increase emission footprint."""
    res_ideal = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, congestion_level=0.0, weather_severity=0.0
    )
    res_congested_storm = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, congestion_level=0.8, weather_severity=0.5
    )
    
    assert res_congested_storm["adjusted_emissions_kg"] > res_ideal["adjusted_emissions_kg"]
    assert res_congested_storm["multipliers"]["congestion"] > 1.0
    assert res_congested_storm["multipliers"]["weather"] > 1.0


def test_empty_backhaul_penalty():
    """Verify empty backhaul penalty increases final emissions footprint by 60%."""
    res_no_backhaul = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, empty_backhaul=False
    )
    res_with_backhaul = CarbonEmissionsEngine.calculate_emissions(
        mode="ROAD", distance_km=100.0, weight_tonnes=10.0, empty_backhaul=True
    )
    
    expected_ratio = res_with_backhaul["adjusted_emissions_kg"] / res_no_backhaul["adjusted_emissions_kg"]
    # Check if ratio is close to 1.60
    assert abs(expected_ratio - 1.60) < 0.01


def test_sla_audit():
    """Verify SLA auditor identifies compliance and calculates penalties correctly."""
    # Base: 100 km, 10 tonnes = 1000 t-km.
    # Total emissions: 100 kg = 100,000 g.
    # Actual intensity = 100,000 g / 1000 t-km = 100 g/t-km.
    
    # 1. Compliant Case (SLA threshold is 120 g/t-km)
    audit_ok = CarbonEmissionsEngine.audit_against_sla(
        calculated_emissions_kg=100.0,
        sla_threshold_kg_per_tkm=120.0,
        distance_km=100.0,
        weight_tonnes=10.0
    )
    assert audit_ok["is_compliant"] is True
    assert audit_ok["penalty_fee_usd"] == 0.0
    
    # 2. Non-compliant Case (SLA threshold is 80 g/t-km)
    # Expected compliance threshold total emissions: (80 * 1000) / 1000 = 80 kg.
    # We generated 100 kg. Overage = 20 kg.
    # Penalty = 20 kg * $0.05 = $1.00.
    audit_fail = CarbonEmissionsEngine.audit_against_sla(
        calculated_emissions_kg=100.0,
        sla_threshold_kg_per_tkm=80.0,
        distance_km=100.0,
        weight_tonnes=10.0
    )
    assert audit_fail["is_compliant"] is False
    assert audit_fail["penalty_fee_usd"] == 1.00
    assert audit_fail["variance_percentage"] == 25.0 # (100 - 80) / 80 = 0.25 = 25%


if __name__ == "__main__":
    print("Running CarbonRoute Emissions Engine Tests...")
    test_base_emissions()
    test_underloading_multiplier()
    test_congestion_and_weather_impact()
    test_empty_backhaul_penalty()
    test_sla_audit()
    print("All tests passed successfully! [OK]")
