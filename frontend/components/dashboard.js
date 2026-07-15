// ==========================================
// METRICS & INSIGHTS COMPONENT (dashboard.js)
// ==========================================

export function renderDashboard(data, days = 7) {
    const rangeText = days === 1 ? "Today" : (days === 7 ? "This Week" : "This Month");
    
    const hasNoActivity = (!data.productive_time_seconds && !data.distracting_time_seconds && !data.neutral_time_seconds);
    const hasNoExpenses = (!data.total_spent || data.total_spent === 0);

    // If TODAY (days === 1) and there is no activity, force absolute zero/empty states
    if (days === 1 && hasNoActivity && hasNoExpenses) {
        document.getElementById("productivity-val").innerText = "0%";
        document.getElementById("focus-val").innerText = "0%";
        document.getElementById("burnout-val").innerText = "0";
        document.getElementById("burnout-risk-val").innerText = "Risk Category: Low (Today)";
        document.getElementById("burnout-warn-icon").classList.add("hidden");
        document.getElementById("burnout-card").className = "glass-card metric-card border-orange";
        document.getElementById("cost-val").innerText = "₹0.00";
        
        document.getElementById("val-time-waster").innerText = "No data";
        document.getElementById("val-spending").innerText = "No data";
        document.getElementById("val-habits").innerText = "No data";
        document.getElementById("val-suggestion").innerText = "No activity tracked today. Start the desktop tracker to begin auditing.";
        
        document.querySelector(".border-green .subtitle").innerText = "Focus weighted index (Today)";
        document.querySelector(".border-blue .subtitle").innerText = "0 Deep / 0 Total (Today)";
        document.querySelector(".border-rose .subtitle").innerText = "Potential wage loss (Today)";
        return;
    }

    // 1. Productivity Score
    const prodVal = document.getElementById("productivity-val");
    prodVal.innerText = `${data.productivity_score}%`;
    document.querySelector(".border-green .subtitle").innerText = `Focus weighted index (${rangeText})`;

    // 2. Focus Efficiency
    const focusVal = document.getElementById("focus-val");
    focusVal.innerText = `${data.focus_efficiency}%`;
    const focusSubtitle = document.querySelector(".border-blue .subtitle");
    focusSubtitle.innerText = `${data.deep_work_sessions} Deep / ${data.total_sessions} Total (${rangeText})`;

    // 3. Burnout Index & Risks
    const burnoutVal = document.getElementById("burnout-val");
    const burnoutRisk = document.getElementById("burnout-risk-val");
    const warnIcon = document.getElementById("burnout-warn-icon");

    burnoutVal.innerText = `${data.burnout_score}/100`;
    burnoutRisk.innerText = `Risk Category: ${data.burnout_risk} (${rangeText})`;

    if (data.burnout_risk === "High" || data.burnout_risk === "Medium") {
        warnIcon.classList.remove("hidden");
        document.getElementById("burnout-card").className = "glass-card metric-card border-orange border-rose";
    } else {
        warnIcon.classList.add("hidden");
        document.getElementById("burnout-card").className = "glass-card metric-card border-orange";
    }

    // 4. Distraction Cost
    const costVal = document.getElementById("cost-val");
    costVal.innerText = formatCurrency(data.distraction_cost, data.currency);
    document.querySelector(".border-rose .subtitle").innerText = `Potential wage loss (${rangeText})`;

    // 5. Insights & recommendations
    document.getElementById("val-time-waster").innerText = data.insights.biggest_time_waster === "None" ? "No data" : (data.insights.biggest_time_waster || "No data");
    document.getElementById("val-spending").innerText = data.insights.spending_pattern === "None" ? "No data" : (data.insights.spending_pattern || "No data");
    
    const habitsList = data.detected_habits || [];
    document.getElementById("val-habits").innerText = habitsList.length > 0 ? habitsList.join(", ") : "No data";
    
    document.getElementById("val-suggestion").innerText = data.insights.suggestion || "Analyzing metrics...";
}

function formatCurrency(val, currency) {
    const symbols = { "INR": "₹", "USD": "$", "EUR": "€" };
    const sym = symbols[currency] || currency;
    return `${sym}${val.toFixed(2)}`;
}
