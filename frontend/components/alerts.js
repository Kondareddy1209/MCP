// ==========================================
// REAL-TIME ALERTS COMPONENT (alerts.js)
// ==========================================

function formatTime(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ""; // prevent "Invalid Date"
    return d.toLocaleTimeString();
}

export function renderAlerts(alerts) {
    const container = document.getElementById("alerts-container");
    container.innerHTML = "";

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="coaching-card" style="background: rgba(255, 255, 255, 0.02); border-color: rgba(255, 255, 255, 0.05); border-left-color: var(--text-secondary);">
                <div class="coaching-header" style="color: var(--text-secondary);"><i class="fa-solid fa-circle-check"></i> System Clear</div>
                <p class="coaching-text">No alerts for today</p>
            </div>
        `;
        return;
    }

    alerts.forEach(alert => {
        const row = document.createElement("div");
        const priorityClass = alert.priority ? alert.priority.toLowerCase() : "medium";
        
        row.className = `alert-row ${priorityClass}`;
        
        const displayTime = formatTime(alert.timestamp);
        
        row.innerHTML = `
            <div class="alert-message"><strong>[${alert.priority || "INFO"}]</strong> ${alert.message}</div>
            <div class="alert-time"><i class="fa-regular fa-clock"></i> ${displayTime || "No time"}</div>
        `;
        container.appendChild(row);
    });
}
