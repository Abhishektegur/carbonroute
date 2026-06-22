"""
CarbonRoute FastAPI Server

Provides backend endpoints for retrieving shipment data, updating SLAs,
calculating dynamic carbon, and serving static dashboard files.
"""

import os
import uuid
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from emissions_engine import CarbonEmissionsEngine, BASE_EMISSION_FACTORS
import db

app = FastAPI(title="CarbonRoute API", description="Dynamic Scope 3 Logistics Carbon Auditor")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_db():
    db.init_db()

# Serve UI static files
UI_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def serve_home():
    return FileResponse(os.path.join(UI_DIR, "index.html"))

@app.get("/styles.css")
def serve_css():
    return FileResponse(os.path.join(UI_DIR, "styles.css"))

@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(UI_DIR, "app.js"))


# API Schemas
class ShipmentInput(BaseModel):
    mode: str = Field(..., description="ROAD, RAIL, AIR, or OCEAN")
    origin: str
    destination: str
    distance_km: float
    weight_tonnes: float
    utilization_ratio: float = 1.0
    congestion_level: float = 0.0
    weather_severity: float = 0.0
    empty_backhaul: bool = False

class SLARuleInput(BaseModel):
    mode: str
    sla_threshold_g_tkm: float


# API Routes

@app.get("/api/slas")
def get_slas():
    try:
        return db.get_sla_rules()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/slas")
def update_sla(rule: SLARuleInput):
    try:
        if rule.mode.upper() not in BASE_EMISSION_FACTORS:
            raise HTTPException(status_code=400, detail="Invalid transport mode.")
        if rule.sla_threshold_g_tkm <= 0:
            raise HTTPException(status_code=400, detail="Threshold must be positive.")
        
        db.update_sla_rule(rule.mode, rule.sla_threshold_g_tkm)
        return {"status": "success", "message": f"SLA threshold for {rule.mode.upper()} updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shipments")
def get_shipments(limit: int = 50):
    try:
        return db.get_all_shipments(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/shipments")
def audit_and_save_shipment(payload: ShipmentInput):
    try:
        # 1. Calculate dynamic emissions
        emissions = CarbonEmissionsEngine.calculate_emissions(
            mode=payload.mode,
            distance_km=payload.distance_km,
            weight_tonnes=payload.weight_tonnes,
            utilization_ratio=payload.utilization_ratio,
            congestion_level=payload.congestion_level,
            weather_severity=payload.weather_severity,
            empty_backhaul=payload.empty_backhaul
        )
        
        # 2. Get SLA threshold
        slas = db.get_sla_rules()
        sla_threshold = slas.get(payload.mode.upper(), 100.0)
        
        # 3. Audit against SLA
        audit = CarbonEmissionsEngine.audit_against_sla(
            calculated_emissions_kg=emissions["adjusted_emissions_kg"],
            sla_threshold_kg_per_tkm=sla_threshold,
            distance_km=payload.distance_km,
            weight_tonnes=payload.weight_tonnes
        )
        
        # 4. Save to database
        shipment_id = "SHIP-" + str(uuid.uuid4())[:8].upper()
        
        # Format input for DB helper
        ship_data = {
            "mode": payload.mode.upper(),
            "origin": payload.origin,
            "destination": payload.destination,
            "distance_km": payload.distance_km,
            "weight_tonnes": payload.weight_tonnes,
            "utilization_ratio": payload.utilization_ratio,
            "congestion_level": payload.congestion_level,
            "weather_severity": payload.weather_severity,
            "empty_backhaul": payload.empty_backhaul,
            "base_emissions_kg": emissions["base_emissions_kg"],
            "adjusted_emissions_kg": emissions["adjusted_emissions_kg"],
            "carbon_variance_kg": emissions["carbon_variance_kg"]
        }
        
        db.save_shipment(shipment_id, ship_data, audit)
        
        return {
            "id": shipment_id,
            "emissions": emissions,
            "audit": audit
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics")
def get_analytics():
    try:
        return db.get_analytics_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed")
def seed_database():
    """Generates simulated historical shipping records to populate the dashboard."""
    try:
        # Clear existing shipments to generate fresh seed data
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shipments")
        conn.commit()
        conn.close()
        
        # Historical routes
        routes = [
            ("ROAD", "Frankfurt", "Munich", 380.0, 18.0),
            ("ROAD", "Hamburg", "Berlin", 290.0, 15.0),
            ("RAIL", "Rotterdam", "Duisburg", 220.0, 120.0),
            ("RAIL", "Leipzig", "Stuttgart", 430.0, 95.0),
            ("AIR", "London Heathrow", "Frankfurt", 650.0, 8.0),
            ("AIR", "Paris CDG", "Munich", 700.0, 5.0),
            ("OCEAN", "Shanghai", "Hamburg", 18500.0, 8000.0),
            ("OCEAN", "New York", "Rotterdam", 6200.0, 12000.0),
            ("ROAD", "Milan", "Munich", 490.0, 12.0),
            ("RAIL", "Gdynia", "Nuremberg", 880.0, 150.0)
        ]
        
        slas = db.get_sla_rules()
        
        # Populate 15 historical shipments spanning the last 5 days
        for i in range(15):
            mode, origin, dest, base_dist, base_wt = random.choice(routes)
            
            # Add random fluctuations
            distance = base_dist * random.uniform(0.95, 1.05)
            weight = base_wt * random.uniform(0.9, 1.1)
            utilization = random.choice([1.0, 0.9, 0.8, 0.7, 0.5, 0.4])
            congestion = random.choice([0.0, 0.1, 0.2, 0.5, 0.8]) if mode == "ROAD" else random.choice([0.0, 0.1, 0.3])
            weather = random.choice([0.0, 0.1, 0.2, 0.6, 0.9])
            backhaul = random.choice([True, False, False, False]) # 25% chance of empty backhaul penalty
            
            # Compute
            emissions = CarbonEmissionsEngine.calculate_emissions(
                mode=mode,
                distance_km=distance,
                weight_tonnes=weight,
                utilization_ratio=utilization,
                congestion_level=congestion,
                weather_severity=weather,
                empty_backhaul=backhaul
            )
            
            sla = slas.get(mode, 100.0)
            audit = CarbonEmissionsEngine.audit_against_sla(
                calculated_emissions_kg=emissions["adjusted_emissions_kg"],
                sla_threshold_kg_per_tkm=sla,
                distance_km=distance,
                weight_tonnes=weight
            )
            
            shipment_id = "SHIP-HIST-" + str(i + 100).upper()
            
            ship_data = {
                "mode": mode,
                "origin": origin,
                "destination": dest,
                "distance_km": round(distance, 1),
                "weight_tonnes": round(weight, 1),
                "utilization_ratio": utilization,
                "congestion_level": congestion,
                "weather_severity": weather,
                "empty_backhaul": backhaul,
                "base_emissions_kg": emissions["base_emissions_kg"],
                "adjusted_emissions_kg": emissions["adjusted_emissions_kg"],
                "carbon_variance_kg": emissions["carbon_variance_kg"]
            }
            
            # Save into DB
            db.save_shipment(shipment_id, ship_data, audit)
            
            # Retroactively offset timestamp for historical feel
            conn = db.get_db_connection()
            cursor = conn.cursor()
            offset_hours = (15 - i) * 6 # Spread back in time
            timestamp = (datetime.now() - timedelta(hours=offset_hours)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE shipments SET timestamp = ? WHERE id = ?", (timestamp, shipment_id))
            conn.commit()
            conn.close()
            
        return {"status": "success", "message": "Database seeded with 15 historical shipments."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate-live")
def simulate_single_live():
    """Triggers a single real-time simulated logistics shipment with dynamic congestion/weather anomalies."""
    try:
        # Mock active pipelines
        routes = [
            ("ROAD", "Frankfurt", "Munich", 380.0, 18.0),
            ("ROAD", "Hamburg", "Berlin", 290.0, 15.0),
            ("ROAD", "Stuttgart", "Cologne", 360.0, 14.0),
            ("RAIL", "Rotterdam", "Duisburg", 220.0, 120.0),
            ("RAIL", "Leipzig", "Stuttgart", 430.0, 95.0),
            ("AIR", "London Heathrow", "Frankfurt", 650.0, 8.0),
            ("AIR", "Paris CDG", "Munich", 700.0, 5.0),
            ("OCEAN", "Shanghai", "Hamburg", 18500.0, 8000.0)
        ]
        
        mode, origin, dest, base_dist, base_wt = random.choice(routes)
        
        # Introduce heavy anomalies (storms, delays, underloadings) to demonstrate audit capabilities
        utilization = random.choice([1.0, 0.85, 0.7, 0.45]) # Underloads
        congestion = random.choice([0.1, 0.3, 0.75, 0.9]) if mode == "ROAD" else random.choice([0.0, 0.25])
        weather = random.choice([0.0, 0.2, 0.55, 0.85]) # Heavy storm chance
        backhaul = random.choice([True, False, False]) # Empty backhaul penalty
        
        # Calculate
        emissions = CarbonEmissionsEngine.calculate_emissions(
            mode=mode,
            distance_km=base_dist,
            weight_tonnes=base_wt,
            utilization_ratio=utilization,
            congestion_level=congestion,
            weather_severity=weather,
            empty_backhaul=backhaul
        )
        
        slas = db.get_sla_rules()
        sla = slas.get(mode, 100.0)
        
        audit = CarbonEmissionsEngine.audit_against_sla(
            calculated_emissions_kg=emissions["adjusted_emissions_kg"],
            sla_threshold_kg_per_tkm=sla,
            distance_km=base_dist,
            weight_tonnes=base_wt
        )
        
        shipment_id = "SHIP-LIVE-" + str(uuid.uuid4())[:8].upper()
        
        ship_data = {
            "mode": mode,
            "origin": origin,
            "destination": dest,
            "distance_km": base_dist,
            "weight_tonnes": base_wt,
            "utilization_ratio": utilization,
            "congestion_level": congestion,
            "weather_severity": weather,
            "empty_backhaul": backhaul,
            "base_emissions_kg": emissions["base_emissions_kg"],
            "adjusted_emissions_kg": emissions["adjusted_emissions_kg"],
            "carbon_variance_kg": emissions["carbon_variance_kg"]
        }
        
        db.save_shipment(shipment_id, ship_data, audit)
        
        return {
            "id": shipment_id,
            "emissions": emissions,
            "audit": audit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
