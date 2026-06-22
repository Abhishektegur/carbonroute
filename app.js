/**
 * CarbonRoute Frontend App Controller
 * Connects API endpoints to dynamic DOM elements, handles form state changes,
 * runs calculations, and updates metric dials.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Base emission factors (replicated client-side for immediate simulator updates)
    const BASE_EMISSION_FACTORS = {
        ROAD: 62.0,
        RAIL: 22.0,
        AIR: 602.0,
        OCEAN: 8.4
    };

    // State Variables
    let activeSlas = {
        ROAD: 85.0,
        RAIL: 25.0,
        AIR: 680.0,
        OCEAN: 10.0
    };
    let activeShipments = [];

    // DOM Elements - KPIs
    const elTotalShipments = document.getElementById("val-total-shipments");
    const elActualCarbon = document.getElementById("val-actual-carbon");
    const elBaseCarbon = document.getElementById("val-base-carbon");
    const elComplianceRate = document.getElementById("val-compliance-rate");
    const elFillCompliance = document.getElementById("fill-compliance-rate");
    const elTotalPenalties = document.getElementById("val-total-penalties");

    // DOM Elements - Sliders & Inputs
    const sliders = {
        slaRoad: document.getElementById("slider-sla-road"),
        slaRail: document.getElementById("slider-sla-rail"),
        slaAir: document.getElementById("slider-sla-air"),
        slaOcean: document.getElementById("slider-sla-ocean"),
        distance: document.getElementById("slider-distance"),
        weight: document.getElementById("slider-weight"),
        utilization: document.getElementById("slider-utilization"),
        congestion: document.getElementById("slider-congestion"),
        weather: document.getElementById("slider-weather")
    };

    const labels = {
        slaRoad: document.getElementById("val-sla-road"),
        slaRail: document.getElementById("val-sla-rail"),
        slaAir: document.getElementById("val-sla-air"),
        slaOcean: document.getElementById("val-sla-ocean"),
        distance: document.getElementById("val-distance"),
        weight: document.getElementById("val-weight"),
        utilization: document.getElementById("val-utilization"),
        congestion: document.getElementById("val-congestion"),
        weather: document.getElementById("val-weather")
    };

    const inputs = {
        origin: document.getElementById("input-origin"),
        destination: document.getElementById("input-destination"),
        emptyBackhaul: document.getElementById("check-backhaul")
    };

    // DOM Elements - Action Buttons
    const btnSeed = document.getElementById("btn-seed-data");
    const btnSimulate = document.getElementById("btn-simulate-live");
    const btnCompare = document.getElementById("btn-compare-modes");
    const btnSubmit = document.getElementById("btn-submit-shipment");
    const ledgerBody = document.getElementById("ledger-body");

    // DOM Elements - Modal
    const modal = document.getElementById("modal-audit-details");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnPrintAudit = document.getElementById("btn-print-audit");

    // Initialize UI bindings
    setupSliderBindings();
    fetchInitialData();

    // Event Listeners
    btnSeed.addEventListener("click", handleSeedDatabase);
    btnSimulate.addEventListener("click", handleSimulateLive);
    btnCompare.addEventListener("click", handleCompareModes);
    btnSubmit.addEventListener("click", handleSubmitShipment);
    btnCloseModal.addEventListener("click", () => modal.classList.add("hidden"));
    btnPrintAudit.addEventListener("click", handlePrintAudit);

    // --- Slider UI Sync ---
    function setupSliderBindings() {
        // Distance
        sliders.distance.addEventListener("input", (e) => {
            labels.distance.textContent = e.target.value;
        });

        // Weight
        sliders.weight.addEventListener("input", (e) => {
            labels.weight.textContent = parseFloat(e.target.value).toFixed(1);
        });

        // Utilization
        sliders.utilization.addEventListener("input", (e) => {
            labels.utilization.textContent = `${e.target.value}%`;
        });

        // Congestion
        sliders.congestion.addEventListener("input", (e) => {
            labels.congestion.textContent = `${e.target.value}%`;
        });

        // Weather
        sliders.weather.addEventListener("input", (e) => {
            const val = parseInt(e.target.value);
            if (val === 0) labels.weather.textContent = "Clear";
            else if (val <= 30) labels.weather.textContent = "Light Rain";
            else if (val <= 60) labels.weather.textContent = "Heavy Rain";
            else if (val <= 80) labels.weather.textContent = "Gale Winds";
            else labels.weather.textContent = "Severe Storm";
        });

        // SLA Updates on Change
        Object.keys(activeSlas).forEach((mode) => {
            const sliderKey = `sla${mode.charAt(0) + mode.slice(1).toLowerCase()}`;
            const slider = sliders[sliderKey];
            if (slider) {
                slider.addEventListener("change", async (e) => {
                    const threshold = parseFloat(e.target.value);
                    labels[sliderKey].textContent = threshold.toFixed(1);
                    activeSlas[mode] = threshold;
                    await updateSlaOnServer(mode, threshold);
                    refreshDashboard();
                });
            }
        });
    }

    // --- API Calls ---

    async function fetchInitialData() {
        try {
            // Fetch active SLAs
            const responseSlas = await fetch("/api/slas");
            if (responseSlas.ok) {
                activeSlas = await responseSlas.json();
                updateSlaSlidersInUI();
            }
            await refreshDashboard();
        } catch (err) {
            console.error("Error loading initial data:", err);
        }
    }

    async function refreshDashboard() {
        try {
            // Fetch summary stats
            const resStats = await fetch("/api/analytics");
            if (resStats.ok) {
                const stats = await resStats.json();
                updateKpiScorecard(stats);
            }

            // Fetch shipment logs
            const resShips = await fetch("/api/shipments");
            if (resShips.ok) {
                activeShipments = await resShips.json();
                renderLedgerTable(activeShipments);
            }
        } catch (err) {
            console.error("Error refreshing dashboard:", err);
        }
    }

    async function updateSlaOnServer(mode, threshold) {
        try {
            await fetch("/api/slas", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode, sla_threshold_g_tkm: threshold })
            });
        } catch (err) {
            console.error("Error updating SLA rule:", err);
        }
    }

    function updateSlaSlidersInUI() {
        Object.keys(activeSlas).forEach(mode => {
            const sliderKey = `sla${mode.charAt(0) + mode.slice(1).toLowerCase()}`;
            if (sliders[sliderKey]) {
                sliders[sliderKey].value = activeSlas[mode];
                labels[sliderKey].textContent = activeSlas[mode].toFixed(1);
            }
        });
    }

    // --- Action Handlers ---

    async function handleSeedDatabase() {
        btnSeed.textContent = "Loading...";
        btnSeed.disabled = true;
        try {
            const res = await fetch("/api/seed", { method: "POST" });
            if (res.ok) {
                await refreshDashboard();
            }
        } catch (err) {
            console.error(err);
        } finally {
            btnSeed.textContent = "⚡ Seed History";
            btnSeed.disabled = false;
        }
    }

    async function handleSimulateLive() {
        btnSimulate.textContent = "Simulating...";
        btnSimulate.disabled = true;
        try {
            const res = await fetch("/api/simulate-live", { method: "POST" });
            if (res.ok) {
                await refreshDashboard();
            }
        } catch (err) {
            console.error(err);
        } finally {
            btnSimulate.textContent = "➕ Simulate Live Cargo";
            btnSimulate.disabled = false;
        }
    }

    async function handleSubmitShipment() {
        const origin = inputs.origin.value.trim();
        const destination = inputs.destination.value.trim();
        
        if (!origin || !destination) {
            alert("Please input Origin and Destination.");
            return;
        }

        const distance = parseFloat(sliders.distance.value);
        const weight = parseFloat(sliders.weight.value);
        const utilization = parseFloat(sliders.utilization.value) / 100.0;
        const congestion = parseFloat(sliders.congestion.value) / 100.0;
        const weather = parseFloat(sliders.weather.value) / 100.0;
        const emptyBackhaul = inputs.emptyBackhaul.checked;

        // Auto-select standard mode (e.g. long distance defaults to ROAD, short/medium options)
        // Shippers usually have a default mode. Let's send a payload for ROAD.
        // For custom submits, we default to ROAD.
        const payload = {
            mode: "ROAD",
            origin,
            destination,
            distance_km: distance,
            weight_tonnes: weight,
            utilization_ratio: utilization,
            congestion_level: congestion,
            weather_severity: weather,
            empty_backhaul: emptyBackhaul
        };

        btnSubmit.disabled = true;
        try {
            const res = await fetch("/api/shipments", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                inputs.origin.value = "";
                inputs.destination.value = "";
                inputs.emptyBackhaul.checked = false;
                
                // Reset slider UI text labels
                sliders.congestion.value = 0;
                labels.congestion.textContent = "0%";
                sliders.weather.value = 0;
                labels.weather.textContent = "Clear";
                
                await refreshDashboard();
            }
        } catch (err) {
            console.error(err);
        } finally {
            btnSubmit.disabled = false;
        }
    }

    function handleCompareModes() {
        const distance = parseFloat(sliders.distance.value);
        const weight = parseFloat(sliders.weight.value);
        const utilization = parseFloat(sliders.utilization.value) / 100.0;
        const congestion = parseFloat(sliders.congestion.value) / 100.0;
        const weather = parseFloat(sliders.weather.value) / 100.0;
        const emptyBackhaul = inputs.emptyBackhaul.checked;

        const container = document.getElementById("comparison-chart-section");
        const barsList = document.getElementById("comparison-bars");
        barsList.innerHTML = "";

        // Calculate and render each mode dynamically in the chart list
        Object.keys(BASE_EMISSION_FACTORS).forEach(mode => {
            const emissions = calculateLocalEmissions(
                mode, distance, weight, utilization, congestion, weather, emptyBackhaul
            );
            
            const slaThreshold = activeSlas[mode] || 100.0;
            const tkm = distance * weight;
            const intensity = (emissions * 1000.0) / tkm;
            const isOverage = intensity > slaThreshold;
            
            // Map intensities to percentages relative to SLA threshold to represent markers
            const percentWidth = Math.min(100, (intensity / (slaThreshold * 1.5)) * 100);
            const slaMarkerLeft = (slaThreshold / (slaThreshold * 1.5)) * 100;

            const barRow = document.createElement("div");
            barRow.className = "chart-bar-row";
            barRow.innerHTML = `
                <div class="bar-labels">
                    <span class="bar-mode">${mode}</span>
                    <span class="font-bold ${isOverage ? 'text-red' : 'text-cyan'}">
                        ${intensity.toFixed(1)} g/t-km ${isOverage ? '⚠️ (SLA Breach)' : '✓'}
                    </span>
                </div>
                <div class="bar-track">
                    <div class="bar-fill bar-${mode.toLowerCase()}" style="width: ${percentWidth}%;"></div>
                    <div class="bar-limit-marker" style="left: ${slaMarkerLeft}%;" title="SLA Limit: ${slaThreshold} g/t-km"></div>
                </div>
            `;
            barsList.appendChild(barRow);
        });

        container.classList.remove("hidden");
    }

    // Local client calculator for instant comparisons
    function calculateLocalEmissions(mode, dist, weight, util, cong, weather, backhaul) {
        const factor = BASE_EMISSION_FACTORS[mode];
        const base_g = dist * weight * factor;
        
        const clamped_util = Math.max(0.05, Math.min(1.0, util));
        const util_mult = 1.0 + (1.0 - clamped_util) * 1.8;
        
        const cong_impact = mode === "ROAD" ? 0.5 : 0.15;
        const cong_mult = 1.0 + (cong * cong_impact);
        
        const weather_impact = (mode === "AIR" || mode === "OCEAN") ? 0.3 : 0.1;
        const weather_mult = 1.0 + (weather * weather_impact);
        
        let adjusted_g = base_g * util_mult * cong_mult * weather_mult;
        
        if (backhaul) {
            adjusted_g += adjusted_g * 0.60;
        }
        
        return adjusted_g / 1000.0; // returns in kg
    }

    // --- UI Update Helpers ---

    function updateKpiScorecard(stats) {
        elTotalShipments.textContent = stats.total_shipments;
        elActualCarbon.textContent = stats.total_actual_carbon_kg.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
        elBaseCarbon.textContent = stats.total_base_carbon_kg.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
        
        elComplianceRate.textContent = `${stats.compliance_rate}%`;
        elFillCompliance.style.width = `${stats.compliance_rate}%`;
        
        // Color compliance score depending on rate
        if (stats.compliance_rate < 70) {
            elComplianceRate.className = "kpi-value text-red";
            elFillCompliance.style.background = "var(--color-red)";
        } else if (stats.compliance_rate < 90) {
            elComplianceRate.className = "kpi-value text-amber";
            elFillCompliance.style.background = "var(--color-amber)";
        } else {
            elComplianceRate.className = "kpi-value text-cyan";
            elFillCompliance.style.background = "linear-gradient(90deg, var(--color-green), var(--accent-cyan))";
        }
        
        elTotalPenalties.textContent = `$${stats.total_penalties_usd.toFixed(2)}`;
    }

    function renderLedgerTable(shipments) {
        if (shipments.length === 0) {
            ledgerBody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">No shipments logged. Click "Seed History" or "Simulate Live Cargo" to populate.</td>
                </tr>
            `;
            return;
        }

        ledgerBody.innerHTML = "";
        shipments.forEach(shipment => {
            const tr = document.createElement("tr");
            tr.addEventListener("click", () => openAuditModal(shipment));
            
            const isCompliant = shipment.is_compliant === 1;
            const statusBadge = isCompliant 
                ? '<span class="badge-status badge-compliant">Compliant</span>'
                : `<span class="badge-status badge-violation">SLA Breach ($${shipment.penalty_fee_usd.toFixed(2)})</span>`;

            tr.innerHTML = `
                <td><span class="font-bold text-cyan">${shipment.id}</span></td>
                <td><span class="badge-mode">${shipment.mode}</span></td>
                <td><span class="font-bold">${shipment.origin}</span> ➔ <span class="font-bold">${shipment.destination}</span></td>
                <td>${shipment.distance_km} km / ${shipment.weight_tonnes} t</td>
                <td>${shipment.actual_emissions_kg.toFixed(1)}</td>
                <td>${shipment.actual_intensity_g_tkm.toFixed(1)} g/t-km</td>
                <td>${statusBadge}</td>
            `;
            ledgerBody.appendChild(tr);
        });
    }

    // --- Modal Audit Report Details ---

    function openAuditModal(shipment) {
        document.getElementById("modal-shipment-id").textContent = shipment.id;
        document.getElementById("modal-route-origin").textContent = shipment.origin;
        document.getElementById("modal-route-destination").textContent = shipment.destination;
        document.getElementById("modal-route-mode").textContent = shipment.mode;
        document.getElementById("modal-route-metrics").textContent = `${shipment.distance_km} km | ${shipment.weight_tonnes} tonnes`;

        document.getElementById("modal-base-emissions").textContent = `${shipment.base_emissions_kg.toFixed(1)} kg`;
        document.getElementById("modal-actual-emissions").textContent = `${shipment.actual_emissions_kg.toFixed(1)} kg`;
        
        const varianceVal = shipment.carbon_variance_kg;
        const elVariance = document.getElementById("modal-carbon-variance");
        elVariance.textContent = `${varianceVal >= 0 ? '+' : ''}${varianceVal.toFixed(1)} kg`;
        elVariance.className = `font-bold ${varianceVal > 0 ? 'text-red' : 'text-cyan'}`;

        // Compute local multiplier details to print
        const utilFactor = 1.0 + (1.0 - shipment.utilization_ratio) * 1.8;
        const congImpact = shipment.mode === "ROAD" ? 0.5 : 0.15;
        const congFactor = 1.0 + (shipment.congestion_level * congImpact);
        const weatherImpact = (shipment.mode === "AIR" || shipment.mode === "OCEAN") ? 0.3 : 0.1;
        const weatherFactor = 1.0 + (shipment.weather_severity * weatherImpact);

        document.getElementById("modal-mult-util").textContent = `${utilFactor.toFixed(2)}x`;
        document.getElementById("modal-mult-cong").textContent = `${congFactor.toFixed(2)}x`;
        document.getElementById("modal-mult-weat").textContent = `${weatherFactor.toFixed(2)}x`;
        document.getElementById("modal-mult-back").textContent = shipment.empty_backhaul === 1 ? "+60%" : "No";

        // SLA
        const isCompliant = shipment.is_compliant === 1;
        
        // Find threshold in active list
        const threshold = activeSlas[shipment.mode] || 100.0;
        const thresholdText = `${threshold.toFixed(1)} g/t-km`;
        document.getElementById("modal-sla-threshold").textContent = thresholdText;
        
        const actualIntensity = shipment.actual_intensity_g_tkm;
        document.getElementById("modal-actual-intensity").textContent = `${actualIntensity.toFixed(1)} g/t-km`;
        
        const intensityVariance = ((actualIntensity - threshold) / threshold) * 100.0;
        document.getElementById("modal-intensity-variance").textContent = `${intensityVariance >= 0 ? '+' : ''}${intensityVariance.toFixed(1)}%`;
        
        const verdictBox = document.getElementById("modal-sla-verdict-container");
        const verdictText = document.getElementById("modal-sla-verdict");
        if (isCompliant) {
            verdictBox.className = "sla-verdict-box verdict-compliant";
            verdictText.textContent = "COMPLIANT";
        } else {
            verdictBox.className = "sla-verdict-box verdict-violation";
            verdictText.textContent = "SLA BREACH";
        }

        document.getElementById("modal-penalty-charge").textContent = `$${shipment.penalty_fee_usd.toFixed(2)}`;

        modal.classList.remove("hidden");
    }

    function handlePrintAudit() {
        window.print();
    }
});
