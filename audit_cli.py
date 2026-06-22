"""
CarbonRoute Command-Line Auditor

A CLI utility for logistics managers to run instant, activity-based Scope 3 carbon audits 
and SLA compliance checks directly from the command line.
"""

import argparse
import sys
from emissions_engine import CarbonEmissionsEngine


def run_cli_audit():
    parser = argparse.ArgumentParser(
        description="CarbonRoute CLI Auditor - Activity-Based Scope 3 Carbon Compliance"
    )
    
    # Required arguments
    parser.add_argument(
        "--mode", required=True, choices=["ROAD", "RAIL", "AIR", "OCEAN"],
        help="Transport mode (ROAD, RAIL, AIR, OCEAN)"
    )
    parser.add_argument(
        "--dist", required=True, type=float,
        help="Distance of transport leg in kilometers (km)"
    )
    parser.add_argument(
        "--weight", required=True, type=float,
        help="Weight of shipment in metric tonnes (t)"
    )
    
    # Optional telemetry factors
    parser.add_argument(
        "--util", type=float, default=1.0,
        help="Payload weight capacity utilization (0.05 to 1.0, default: 1.0)"
    )
    parser.add_argument(
        "--cong", type=float, default=0.0,
        help="Traffic congestion factor (0.0 to 1.0, default: 0.0)"
    )
    parser.add_argument(
        "--weat", type=float, default=0.0,
        help="Weather/environmental severity index (0.0 to 1.0, default: 0.0)"
    )
    parser.add_argument(
        "--backhaul", action="store_true",
        help="Apply empty backhaul repositioning penalty"
    )
    parser.add_argument(
        "--sla", type=float,
        help="Negotiated SLA carbon intensity limit (g CO2e / t-km) to audit against"
    )

    args = parser.parse_args()

    try:
        # 1. Run emissions calculations
        res = CarbonEmissionsEngine.calculate_emissions(
            mode=args.mode,
            distance_km=args.dist,
            weight_tonnes=args.weight,
            utilization_ratio=args.util,
            congestion_level=args.cong,
            weather_severity=args.weat,
            empty_backhaul=args.backhaul
        )

        # 2. Print Header
        print("\n" + "="*50)
        print("          CARBONROUTE LOGISTICS AUDIT REPORT")
        print("="*50)
        print(f"Mode:          {res['mode']}")
        print(f"Route Metrics: {res['distance_km']:.1f} km | {res['weight_tonnes']:.2f} tonnes")
        print("-"*50)
        
        # 3. Print Calculations
        print(f"Base Emissions:       {res['base_emissions_kg']:.2f} kg CO2e")
        print(f"Actual Emissions:     {res['adjusted_emissions_kg']:.2f} kg CO2e")
        print(f"Carbon Variance:      {res['carbon_variance_kg']:+.2f} kg CO2e")
        
        print("\nTelemetry Multipliers:")
        print(f"  - Load Utilization: {res['multipliers']['utilization']:.2f}x")
        print(f"  - Congestion Index: {res['multipliers']['congestion']:.2f}x")
        print(f"  - Weather Index:    {res['multipliers']['weather']:.2f}x")
        print(f"  - Empty Backhaul:   {'Yes (+60%%)' if res['multipliers']['empty_backhaul_added'] else 'No'}")
        
        # 4. Run SLA Audit if requested
        if args.sla is not None:
            audit = CarbonEmissionsEngine.audit_against_sla(
                calculated_emissions_kg=res["adjusted_emissions_kg"],
                sla_threshold_kg_per_tkm=args.sla,
                distance_km=args.dist,
                weight_tonnes=args.weight
            )
            
            print("-"*50)
            print("SLA Compliance Status:")
            print(f"  - SLA Threshold:    {audit['sla_threshold_g_tkm']:.1f} g/t-km")
            print(f"  - Actual Intensity: {audit['actual_intensity_g_tkm']:.1f} g/t-km")
            print(f"  - Intensity Var:    {audit['variance_percentage']:+.1f}%")
            
            status = "COMPLIANT [OK]" if audit["is_compliant"] else "SLA BREACH [ALERT]"
            print(f"  - Verdict:          {status}")
            if not audit["is_compliant"]:
                print(f"  - Penalty Overage:  ${audit['penalty_fee_usd']:.2f} USD")
        
        print("="*50 + "\n")

    except Exception as e:
        print(f"Error executing audit: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_cli_audit()
