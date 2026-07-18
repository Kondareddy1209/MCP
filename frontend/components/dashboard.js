// ==========================================
// METRICS & INSIGHTS COMPONENT (dashboard.js)
// ==========================================

export function renderDashboard(data, days = 7) {
    const rangeText = days === 1 ? "Today" : (days === 7 ? "This Week" : "This Month");
    
    const hasNoActivity = (!data.productive_time_seconds && !data.distracting_time_seconds && !data.neutral_time_seconds);
    const hasNoExpenses = (!data.total_spent || data.total_spent === 0);

    // If TODAY (days === 1) and there is no activity, force absolute zero/empty states
    if (days === 1 && hasNoActivity && hasNoExpenses) {
        document.getElementById("productivity-val").innerText = "Unknown";
        document.getElementById("focus-val").innerText = "Unknown";
        document.getElementById("burnout-val").innerText = "--";
        document.getElementById("burnout-risk-val").innerText = "Risk Category: -- (Today)";
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

    // 1. Productivity Score — M7 fix: show user-verified score OR estimated fallback
    const prodVal = document.getElementById("productivity-val");
    const estSubtitle = document.querySelector(".border-green .subtitle");
    
    if (data.productivity_score !== null && data.productivity_score !== undefined) {
        // User has real classifications — show confident score
        prodVal.innerText = `${data.productivity_score}%`;
        if (estSubtitle) estSubtitle.innerText = `Focus weighted index (${rangeText})`;
    } else if (data.estimated_score !== null && data.estimated_score !== undefined) {
        // Estimated from auto_classify() — show visually distinct
        prodVal.innerText = `~${data.estimated_score}%`;
        if (estSubtitle) estSubtitle.innerText = `Estimated (auto-classified, ${rangeText})`;
        prodVal.style.opacity = "0.75";
        prodVal.title = "Estimated from app name heuristics. Classify apps in Settings for a verified score.";
    } else {
        prodVal.innerText = "Unknown";
        if (estSubtitle) estSubtitle.innerText = `Focus weighted index (${rangeText})`;
    }

    // 2. Focus Efficiency
    const focusVal = document.getElementById("focus-val");
    if (data.focus_efficiency === null || data.focus_efficiency === undefined || data.focus_efficiency === "Unknown") {
        focusVal.innerText = "Unknown";
    } else {
        focusVal.innerText = `${data.focus_efficiency}%`;
    }
    const focusSubtitle = document.querySelector(".border-blue .subtitle");
    const deepCount = data.deep_work_sessions !== undefined ? data.deep_work_sessions : 0;
    const totalCount = data.total_sessions !== undefined ? data.total_sessions : 1;
    if (focusSubtitle) focusSubtitle.innerText = `${deepCount} Deep / ${totalCount} Total (${rangeText})`;

    // 3. Burnout Index & Risks
    const burnoutVal = document.getElementById("burnout-val");
    const burnoutRisk = document.getElementById("burnout-risk-val");
    const warnIcon = document.getElementById("burnout-warn-icon");

    if (data.burnout_score === null || data.burnout_score === undefined) {
        burnoutVal.innerText = "--";
    } else {
        burnoutVal.innerText = `${data.burnout_score}/100`;
    }

    const riskLabel = data.burnout_risk || "--";
    if (burnoutRisk) burnoutRisk.innerText = `Risk Category: ${riskLabel} (${rangeText})`;

    if (data.burnout_risk === "High" || data.burnout_risk === "Medium" || data.burnout_risk === "Moderate") {
        if (warnIcon) warnIcon.classList.remove("hidden");
        document.getElementById("burnout-card").className = "glass-card metric-card border-orange border-rose";
    } else {
        if (warnIcon) warnIcon.classList.add("hidden");
        document.getElementById("burnout-card").className = "glass-card metric-card border-orange";
    }

    // 4. Distraction Cost
    const costVal = document.getElementById("cost-val");
    if (data.distraction_cost === null || data.distraction_cost === undefined) {
        costVal.innerText = "₹0.00";
    } else {
        costVal.innerText = formatCurrency(data.distraction_cost, data.currency || "INR");
    }
    const costSubtitle = document.querySelector(".border-rose .subtitle");
    if (costSubtitle) costSubtitle.innerText = `Potential wage loss (${rangeText})`;

    // 5. Insights & recommendations
    const insights = data.insights || {};
    const biggestWaster = insights.biggest_time_waster || insights.most_distracting_app;
    document.getElementById("val-time-waster").innerText = (biggestWaster === "None" || !biggestWaster) ? "No data" : biggestWaster;
    
    const spendingPattern = insights.spending_pattern;
    document.getElementById("val-spending").innerText = (spendingPattern === "None" || !spendingPattern) ? "No data" : spendingPattern;
    
    const habitsList = data.detected_habits || [];
    document.getElementById("val-habits").innerText = habitsList.length > 0 ? habitsList.join(", ") : "No data";
    
    // M8 fix: corrected key fallback — recommendations is a list, not a singular string.
    // Also check insights.suggestion (backend sends the first rec as suggestion) as a fallback.
    const recommendations = data.recommendations || [];
    const suggestionText = insights.suggestion || (recommendations.length > 0 ? recommendations[0] : null);
    document.getElementById("val-suggestion").innerText = suggestionText || "Analyzing metrics...";
}

function formatCurrency(val, currency) {
    if (val === null || val === undefined || isNaN(val)) return "₹0.00";
    const symbols = { "INR": "₹", "USD": "$", "EUR": "€" };
    const sym = symbols[currency] || currency;
    return `${sym}${Number(val).toFixed(2)}`;
}
