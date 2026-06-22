"""
CarbonRoute Emissions Engine

Calculates activity-based Scope 3 GHG emissions for freight transport
using base emission factors (g CO2e per tonne-km) modified by dynamic,
real-world telemetry variables (weight utilization, traffic congestion,
weather events, and empty backhauls).
"""

from typing import Dict, Any

# Base emission factors in grams of CO2e per tonne-kilometer (g CO2e / t-km)
# Derived from GHG Protocol and DEFRA standards
BASE_EMISSION_FACTORS: Dict[str, float] = {
    "ROAD": 62.0,    # Heavy goods vehicle (HGV) average
    "RAIL": 22.0,    # Freight train average
    "AIR": 602.0,    # Cargo plane average
    "OCEAN": 8.4     # Container ship average
}

# Average tare (empty) vehicle weights in tonnes
VEHICLE_TARE_WEIGHTS: Dict[str, float] = {
    "ROAD": 15.0,    # HGV cab + empty trailer
    "RAIL": 500.0,   # Entire cargo train empty weight average
    "AIR": 80.0,     # Large cargo plane empty weight (Boeing 767-F class)
    "OCEAN": 20000.0 # Container ship empty weight displacement average
}

# Max payload capacities in tonnes
VEHICLE_MAX_PAYLOADS: Dict[str, float] = {
    "ROAD": 25.0,
    "RAIL": 1500.0,
    "AIR": 50.0,
    "OCEAN": 50000.0
}


class CarbonEmissionsEngine:
    """
    Mathematical engine that computes logistics carbon footprints and alerts
    on SLA compliance variances using dynamic factors.
    """

    @staticmethod
    def calculate_emissions(
        mode: str,
        distance_km: float,
        weight_tonnes: float,
        utilization_ratio: float = 1.0,
        congestion_level: float = 0.0,  # 0.0 (free flow) to 1.0 (gridlock)
        weather_severity: float = 0.0,  # 0.0 (clear) to 1.0 (extreme storm)
        empty_backhaul: bool = False
    ) -> Dict[str, Any]:
        """
        Computes the dynamic carbon emissions of a shipment leg.
        
        Formula:
          Base Emissions = Distance * Weight * BaseFactor
          Adjustments = Base Emissions * WeightUtilizationMultiplier * CongestionMultiplier * WeatherMultiplier
          Backhaul Penalty = If empty_backhaul is True, add empty leg carbon.
          Total Emissions = Adjustments + Backhaul Penalty
        """
        mode = mode.upper()
        if mode not in BASE_EMISSION_FACTORS:
            raise ValueError(f"Unknown transport mode: {mode}. Supported modes: {list(BASE_EMISSION_FACTORS.keys())}")

        if distance_km <= 0 or weight_tonnes <= 0:
            raise ValueError("Distance and weight must be greater than zero.")

        base_factor = BASE_EMISSION_FACTORS[mode]
        
        # 1. Base Emissions (standard static calculation)
        base_emissions_g = distance_km * weight_tonnes * base_factor
        
        # 2. Weight Utilization Multiplier
        # Underloaded vehicles burn more fuel per cargo unit because of the tare weight.
        # Ratio of 1.0 means fully loaded (multiplier = 1.0).
        # Ratio of 0.1 means mostly empty, spiking emissions per cargo tonne-km.
        clamped_utilization = max(0.05, min(1.0, utilization_ratio))
        utilization_multiplier = 1.0 + (1.0 - clamped_utilization) * 1.8
        
        # 3. Congestion Multiplier
        # Traffic congestion results in stop-and-go fuel burns, mainly affecting ROAD.
        # Can affect AIR/OCEAN via terminal port waiting/idling times.
        clamped_congestion = max(0.0, min(1.0, congestion_level))
        congestion_severity_impact = 0.5 if mode == "ROAD" else 0.15
        congestion_multiplier = 1.0 + (clamped_congestion * congestion_severity_impact)
        
        # 4. Weather Multiplier
        # Severe weather (headwinds, snow, heavy seas) increases friction and drag.
        clamped_weather = max(0.0, min(1.0, weather_severity))
        weather_severity_impact = 0.3 if mode in ("AIR", "OCEAN") else 0.1
        weather_multiplier = 1.0 + (clamped_weather * weather_severity_impact)
        
        # 5. Core emissions calculated for cargo leg
        adjusted_emissions_g = (
            base_emissions_g * 
            utilization_multiplier * 
            congestion_multiplier * 
            weather_multiplier
        )
        
        # 6. Empty Backhaul Penalty
        # If the carrier had to return empty, the emissions of the return leg
        # are allocated to this shipment. Empty leg is modeled as tare weight only.
        backhaul_emissions_g = 0.0
        if empty_backhaul:
            # Empty return leg has no cargo weight, but burns fuel for its tare weight.
            # We estimate return leg burns 60% of the loaded leg's base fuel consumption.
            backhaul_emissions_g = adjusted_emissions_g * 0.60
            
        total_emissions_g = adjusted_emissions_g + backhaul_emissions_g
        total_emissions_kg = total_emissions_g / 1000.0
        base_emissions_kg = base_emissions_g / 1000.0
        
        return {
            "mode": mode,
            "distance_km": distance_km,
            "weight_tonnes": weight_tonnes,
            "base_emissions_kg": round(base_emissions_kg, 2),
            "adjusted_emissions_kg": round(total_emissions_kg, 2),
            "carbon_variance_kg": round(total_emissions_kg - base_emissions_kg, 2),
            "multipliers": {
                "utilization": round(utilization_multiplier, 2),
                "congestion": round(congestion_multiplier, 2),
                "weather": round(weather_multiplier, 2),
                "empty_backhaul_added": empty_backhaul
            }
        }

    @staticmethod
    def audit_against_sla(
        calculated_emissions_kg: float,
        sla_threshold_kg_per_tkm: float,
        distance_km: float,
        weight_tonnes: float
    ) -> Dict[str, Any]:
        """
        Audits calculated emissions against a carrier SLA threshold (g CO2e per t-km).
        Returns a compliance report detailing deviations and penalty outcomes.
        """
        # Calculate emissions intensity of this specific run (g CO2e per t-km)
        total_g = calculated_emissions_kg * 1000.0
        tkm = distance_km * weight_tonnes
        actual_intensity = total_g / tkm
        
        is_compliant = actual_intensity <= sla_threshold_kg_per_tkm
        variance_percentage = ((actual_intensity - sla_threshold_kg_per_tkm) / sla_threshold_kg_per_tkm) * 100.0
        
        # Calculate simulated penalty:
        # If non-compliant, charge $0.05 per kg of carbon exceeded.
        penalty_fee = 0.0
        if not is_compliant:
            carbon_overage_kg = calculated_emissions_kg - ((sla_threshold_kg_per_tkm * tkm) / 1000.0)
            penalty_fee = max(0.0, carbon_overage_kg * 0.05) # $0.05 per excess kg
            
        return {
            "sla_threshold_g_tkm": round(sla_threshold_kg_per_tkm, 2),
            "actual_intensity_g_tkm": round(actual_intensity, 2),
            "is_compliant": is_compliant,
            "variance_percentage": round(variance_percentage, 1),
            "penalty_fee_usd": round(penalty_fee, 2)
        }
