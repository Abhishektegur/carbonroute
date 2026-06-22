# CarbonRoute 🍃

CarbonRoute is an **activity-based, dynamic Scope 3 logistics carbon auditor and SLA enforcement engine**. 

Instead of relying on static spend-based averages (like *Distance × Weight × Emission Factor*), CarbonRoute audits shipping telemetry to calculate actual, real-world emissions impacted by payload utilization, traffic congestion, empty backhaul legs, and severe weather drag. It verifies carrier carbon performance against SLA contracts and issues simulated penalties for carbon overages.

---

## System Architecture

```
                                  +-----------------------+
                                  |   Carrier Telemetry   |
                                  | (Congestion, Weather) |
                                  +-----------------------+
                                              |
                                              v
+-------------------------+       +-----------------------+
|  Logistics Request      | ----> |  Emissions Engine     |
| (Mode, Distance, Cargo) |       | (emissions_engine.py) |
+-------------------------+       +-----------------------+
                                              |
                                              v
+-------------------------+       +-----------------------+
|  Carrier SLA contract   | ----> |  SLA Compliance Audit |
|  (g CO2e / tonne-km)    |       |  (SLA Compliance check)
+-------------------------+       +-----------------------+
                                              |
                                              v
                                  +-----------------------+       +-----------------------+
                                  |   SQLite Database     | <---> |   FastAPI Web App     |
                                  |     (carbonroute.db)  |       |       (main.py)       |
                                  +-----------------------+       +-----------------------+
                                                                              |
                                                                              v
                                                                  +-----------------------+
                                                                  |  Interactive UI       |
                                                                  |  (HTML, CSS, JS)      |
                                                                  +-----------------------+
```

---

## Core Calculations & Adjustments

The carbon engine scales base emission factors (g CO2e per t-km) dynamically:

$$\text{Actual Emissions} = (\text{Base Emissions} \times M_{\text{utilization}} \times M_{\text{congestion}} \times M_{\text{weather}}) + \text{Backhaul Penalty}$$

1. **Base Factors ($gCO_2e/t-km$):** Road ($62.0$), Rail ($22.0$), Air ($602.0$), Ocean ($8.4$).
2. **Payload Utilization ($M_{\text{utilization}}$):** Under-loaded vehicles increase emissions per cargo tonne-km since the empty tare weight must still be transported.
   $$M_{\text{utilization}} = 1.0 + (1.0 - \text{utilization\_ratio}) \times 1.8$$
3. **Congestion ($M_{\text{congestion}}$):** Models stop-and-go fuel penalties (adds up to 50% for Road HGV).
4. **Weather ($M_{\text{weather}}$):** Models drag resistance from headwinds, heavy rain, or storm turbulence (adds up to 30% for Air/Ocean).
5. **Empty Backhaul:** If the carrier had to return empty, the empty return leg's emissions (relying on empty tare weight fuel burn) are allocated directly to the shipper's carbon footprint (+60% penalty).

---

## Getting Started

### 1. Install Dependencies
Run the following commands to install the required libraries:
```bash
pip install fastapi uvicorn pydantic
```

### 2. Start the Server
Run the FastAPI development server:
```bash
python -m uvicorn main:app --reload --port 8000
```
Then, open your browser and navigate to `http://localhost:8000` to interact with the dashboard.

### 3. Seed Mock History
Once the dashboard opens, click the **"Seed History"** button in the header. This will populate the dashboard with 15 historical shipments spanning the last few days, showing a realistic blend of compliant routes and SLA violations.

---

## Command Line Interface (CLI)

For rapid audits without opening the browser, use the `audit_cli.py` utility:

```bash
python audit_cli.py --mode ROAD --dist 380 --weight 15 --util 0.7 --cong 0.4 --weat 0.2 --sla 85
```

### Sample Output:
```text
==================================================
          CARBONROUTE LOGISTICS AUDIT REPORT
==================================================
Mode:          ROAD
Route Metrics: 380.0 km | 15.00 tonnes
--------------------------------------------------
Base Emissions:       353.40 kg CO2e
Actual Emissions:     666.14 kg CO2e
Carbon Variance:      +312.74 kg CO2e

Telemetry Multipliers:
  - Load Utilization: 1.54x
  - Congestion Index: 1.20x
  - Weather Index:    1.02x
  - Empty Backhaul:   No
--------------------------------------------------
SLA Compliance Status:
  - SLA Threshold:    85.0 g/t-km
  - Actual Intensity: 116.9 g/t-km
  - Intensity Var:    +37.5%
  - Verdict:          SLA BREACH [ALERT]
  - Penalty Overage:  $9.08 USD
==================================================
```
