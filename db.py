"""
CarbonRoute Database Manager

Handles database initialization, schema creation for shipments and SLA rules,
and helper functions to persist audited routes and compute summary metrics.
"""

import sqlite3
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carbonroute.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the SQLite database and populates default SLA values."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Shipments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            distance_km REAL NOT NULL,
            weight_tonnes REAL NOT NULL,
            utilization_ratio REAL NOT NULL,
            congestion_level REAL NOT NULL,
            weather_severity REAL NOT NULL,
            empty_backhaul INTEGER NOT NULL,
            base_emissions_kg REAL NOT NULL,
            actual_emissions_kg REAL NOT NULL,
            carbon_variance_kg REAL NOT NULL,
            is_compliant INTEGER NOT NULL,
            actual_intensity_g_tkm REAL NOT NULL,
            penalty_fee_usd REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Create SLA Rules Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sla_rules (
            mode TEXT PRIMARY KEY,
            sla_threshold_g_tkm REAL NOT NULL
        )
    """)
    
    conn.commit()
    
    # Populate Default SLA thresholds (g CO2e / t-km)
    default_slas = {
        "ROAD": 85.0,    # Base factor is 62.0. SLA allows moderate congestion.
        "RAIL": 25.0,    # Base is 22.0.
        "AIR": 680.0,    # Base is 602.0.
        "OCEAN": 10.0    # Base is 8.4.
    }
    
    for mode, threshold in default_slas.items():
        cursor.execute(
            "INSERT OR IGNORE INTO sla_rules (mode, sla_threshold_g_tkm) VALUES (?, ?)",
            (mode, threshold)
        )
        
    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def save_shipment(shipment_id: str, ship_data: Dict[str, Any], audit_res: Dict[str, Any]) -> None:
    """Saves a fully audited shipment log to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO shipments (
            id, mode, origin, destination, distance_km, weight_tonnes,
            utilization_ratio, congestion_level, weather_severity, empty_backhaul,
            base_emissions_kg, actual_emissions_kg, carbon_variance_kg,
            is_compliant, actual_intensity_g_tkm, penalty_fee_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        shipment_id,
        ship_data["mode"],
        ship_data["origin"],
        ship_data["destination"],
        ship_data["distance_km"],
        ship_data["weight_tonnes"],
        ship_data.get("utilization_ratio", 1.0),
        ship_data.get("congestion_level", 0.0),
        ship_data.get("weather_severity", 0.0),
        1 if ship_data.get("empty_backhaul", False) else 0,
        ship_data["base_emissions_kg"],
        ship_data["adjusted_emissions_kg"],
        ship_data["carbon_variance_kg"],
        1 if audit_res["is_compliant"] else 0,
        audit_res["actual_intensity_g_tkm"],
        audit_res["penalty_fee_usd"]
    ))
    
    conn.commit()
    conn.close()


def get_all_shipments(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves list of audited shipments."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shipments ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_sla_rules() -> Dict[str, float]:
    """Retrieves all active SLA thresholds."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mode, sla_threshold_g_tkm FROM sla_rules")
    rows = cursor.fetchall()
    conn.close()
    return {row["mode"]: row["sla_threshold_g_tkm"] for row in rows}


def update_sla_rule(mode: str, threshold: float) -> None:
    """Updates the SLA threshold for a specific mode."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sla_rules SET sla_threshold_g_tkm = ? WHERE mode = ?",
        (threshold, mode.upper())
    )
    conn.commit()
    conn.close()


def get_analytics_summary() -> Dict[str, Any]:
    """Computes aggregated carbon metrics and statistics for dashboard dials."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total shipments count
    cursor.execute("SELECT COUNT(*) FROM shipments")
    total_shipments = cursor.fetchone()[0]
    
    if total_shipments == 0:
        conn.close()
        return {
            "total_shipments": 0,
            "total_actual_carbon_kg": 0.0,
            "total_base_carbon_kg": 0.0,
            "net_carbon_variance_kg": 0.0,
            "compliance_rate": 100.0,
            "total_penalties_usd": 0.0,
            "mode_distribution": {}
        }
    
    # 2. Key totals
    cursor.execute("""
        SELECT 
            SUM(base_emissions_kg) as total_base,
            SUM(actual_emissions_kg) as total_actual,
            SUM(penalty_fee_usd) as total_penalties,
            SUM(CASE WHEN is_compliant = 1 THEN 1 ELSE 0 END) as compliant_count
        FROM shipments
    """)
    totals = cursor.fetchone()
    
    total_base = totals["total_base"] or 0.0
    total_actual = totals["total_actual"] or 0.0
    total_penalties = totals["total_penalties"] or 0.0
    compliant_count = totals["compliant_count"] or 0
    compliance_rate = (compliant_count / total_shipments) * 100.0
    
    # 3. Carbon by mode
    cursor.execute("""
        SELECT mode, COUNT(*) as count, SUM(actual_emissions_kg) as carbon 
        FROM shipments 
        GROUP BY mode
    """)
    mode_rows = cursor.fetchall()
    mode_dist = {row["mode"]: {"count": row["count"], "carbon": round(row["carbon"], 2)} for row in mode_rows}
    
    conn.close()
    
    return {
        "total_shipments": total_shipments,
        "total_actual_carbon_kg": round(total_actual, 2),
        "total_base_carbon_kg": round(total_base, 2),
        "net_carbon_variance_kg": round(total_actual - total_base, 2),
        "compliance_rate": round(compliance_rate, 1),
        "total_penalties_usd": round(total_penalties, 2),
        "mode_distribution": mode_dist
    }


if __name__ == "__main__":
    init_db()
