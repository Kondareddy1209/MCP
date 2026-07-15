// ==========================================
// ANTIGRAVITY ENGINE FRONTEND (app.js)
// ==========================================

let screenTimeChartInstance = null;
let expenseChartInstance = null;
let currentAppCategoryFilter = 'productive'; // 'productive' or 'distracting'
let lastFetchedAnalyticsData = null;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Start Clock
    initClock();

    // 2. Set Default Form Dates
    const todayStr = new Date().toISOString().split('T')[0];
    document.getElementById("exp-date").value = todayStr;
    document.getElementById("scr-date").value = todayStr;

    // 3. Register Event Listeners
    document.getElementById("date-range-select").addEventListener("change", fetchAnalytics);
    document.getElementById("btn-productive").addEventListener("click", () => setAppCategoryFilter('productive'));
    document.getElementById("btn-distracting").addEventListener("click", () => setAppCategoryFilter('distracting'));
    
    // Register Form Submissions
    document.getElementById("form-expense").addEventListener("submit", handleExpenseSubmit);
    document.getElementById("form-class").addEventListener("submit", handleClassificationSubmit);
    document.getElementById("form-screen").addEventListener("submit", handleScreenTimeSubmit);

    // 4. Initial Fetch
    fetchAnalytics();
});

// Live Clock
function initClock() {
    const clockEl = document.getElementById("current-time");
    setInterval(() => {
        const now = new Date();
        clockEl.innerHTML = `<i class="fa-regular fa-clock"></i> ${now.toLocaleTimeString()}`;
    }, 1000);
}

// Form Tabs Switching
window.switchForm = function(formId) {
    // Deactivate all forms & tab buttons
    document.querySelectorAll(".action-form").forEach(f => f.classList.remove("active"));
    document.querySelectorAll(".form-tab-btn").forEach(b => b.classList.remove("active"));
    
    // Activate target
    document.getElementById(formId).classList.add("active");
    
    // Find matching button
    const buttons = document.querySelectorAll(".form-tab-btn");
    if (formId === 'form-expense') buttons[0].classList.add("active");
    if (formId === 'form-class') buttons[1].classList.add("active");
    if (formId === 'form-screen') buttons[2].classList.add("active");

    // Hide message
    const msgEl = document.getElementById("form-message");
    msgEl.className = "form-alert hidden";
};

// Toggle App Rankings Category (Productive / Distracting)
function setAppCategoryFilter(category) {
    currentAppCategoryFilter = category;
    
    document.getElementById("btn-productive").classList.toggle("active", category === 'productive');
    document.getElementById("btn-distracting").classList.toggle("active", category === 'distracting');
    
    if (lastFetchedAnalyticsData) {
        renderAppUsageRankings(lastFetchedAnalyticsData);
    }
}

// Fetch Analytics from API
async function fetchAnalytics() {
    const days = document.getElementById("date-range-select").value;
    try {
        const response = await fetch(`/api/analytics/?days=${days}`);
        if (!response.ok) throw new Error("Failed to load analytics");
        const data = await response.json();
        
        lastFetchedAnalyticsData = data;
        
        // Update dashboard UI
        updateMetricCards(data);
        renderCharts(data);
        renderAppUsageRankings(data);
        updateInsights(data);
        
    } catch (err) {
        console.error(err);
        showToast("Error updating dashboard values", "rose");
    }
}

// Update UI Metric Cards
function updateMetricCards(data) {
    // Productivity Score
    const prodValEl = document.getElementById("productivity-val");
    prodValEl.innerText = `${data.productivity_score}%`;
    
    // Screen Time
    const screenTimeValEl = document.getElementById("screen-time-val");
    const totalSec = (data.total_screen_time.mobile || 0) + (data.total_screen_time.laptop || 0);
    const totalHrs = (totalSec / 3600).toFixed(1);
    screenTimeValEl.innerText = `${totalHrs} hrs`;
    
    const laptopHrs = (data.total_screen_time.laptop / 3600).toFixed(1);
    const mobileHrs = (data.total_screen_time.mobile / 3600).toFixed(1);
    document.getElementById("laptop-time-split").innerHTML = `<i class="fa-solid fa-laptop"></i> Laptop: ${laptopHrs}h`;
    document.getElementById("mobile-time-split").innerHTML = `<i class="fa-solid fa-mobile-screen-button"></i> Mobile: ${mobileHrs}h`;

    // Distraction Cost
    const costValEl = document.getElementById("distraction-cost-val");
    const formattedCost = formatCurrency(data.distraction_cost, data.currency);
    costValEl.innerText = formattedCost;
    
    // Get Hourly Rate for label
    document.getElementById("hourly-rate-footer").innerHTML = `<i class="fa-solid fa-calculator"></i> Time conversion enabled`;

    // Financial Expenses
    const expensesValEl = document.getElementById("expenses-val");
    expensesValEl.innerText = formatCurrency(data.total_spent, data.currency);
}

// Update AI Insights panel
function updateInsights(data) {
    document.getElementById("insight-time-waster").innerText = data.insights.biggest_time_waster || "None";
    document.getElementById("insight-spending").innerText = data.insights.spending_pattern || "None";
    
    const suggestionEl = document.getElementById("insight-suggestion");
    suggestionEl.innerText = data.insights.suggestion || "No suggestions available yet.";
}

// Render Top Apps Horizontal Rankings
function renderAppUsageRankings(data) {
    const container = document.getElementById("rankings-container");
    container.innerHTML = "";
    
    const list = currentAppCategoryFilter === 'productive' ? data.top_productive_apps : data.top_distracting_apps;
    
    if (!list || list.length === 0) {
        container.innerHTML = `<div class="loading-placeholder">No ${currentAppCategoryFilter} apps found in selected date range.</div>`;
        return;
    }

    // Find max duration for scaling percentages
    const maxDur = Math.max(...list.map(a => a.duration_seconds), 1);
    
    list.forEach(app => {
        const itemEl = document.createElement("div");
        itemEl.className = "rank-item";
        
        const hrs = (app.duration_seconds / 3600).toFixed(1);
        const percentage = (app.duration_seconds / maxDur) * 100;
        
        const fillClass = currentAppCategoryFilter === 'productive' ? 'fill-productive' : 'fill-distracting';
        
        itemEl.innerHTML = `
            <div class="rank-details">
                <span class="app-name-label">${app.app_name}</span>
                <span class="app-duration-label">${hrs} hrs (${formatSeconds(app.duration_seconds)})</span>
            </div>
            <div class="rank-progress-bg">
                <div class="rank-progress-fill ${fillClass}" style="width: ${percentage}%"></div>
            </div>
        `;
        container.appendChild(itemEl);
    });
}

// Render Charts (Chart.js)
function renderCharts(data) {
    // 1. Screen Time Bar Chart
    const screenCtx = document.getElementById("screenTimeChart").getContext("2d");
    if (screenTimeChartInstance) screenTimeChartInstance.destroy();
    
    const laptopHrs = ((data.total_screen_time.laptop || 0) / 3600).toFixed(1);
    const mobileHrs = ((data.total_screen_time.mobile || 0) / 3600).toFixed(1);
    
    screenTimeChartInstance = new Chart(screenCtx, {
        type: 'bar',
        data: {
            labels: ['Laptop Usage', 'Mobile Usage'],
            datasets: [{
                label: 'Screen Hours',
                data: [laptopHrs, mobileHrs],
                backgroundColor: ['#00b4d8', '#9d4edd'],
                borderColor: ['rgba(0, 180, 216, 0.5)', 'rgba(157, 78, 221, 0.5)'],
                borderWidth: 1,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (ctx) => `${ctx.formattedValue} hrs` } }
            },
            scales: {
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#8e94a9' } },
                x: { grid: { display: false }, ticks: { color: '#8e94a9' } }
            }
        }
    });

    // 2. Expense Doughnut Chart
    const expenseCtx = document.getElementById("expenseChart").getContext("2d");
    if (expenseChartInstance) expenseChartInstance.destroy();
    
    const categories = Object.keys(data.expense_summary);
    const values = Object.values(data.expense_summary);
    
    if (categories.length === 0) {
        categories.push("No Expenses logged");
        values.push(0);
    }
    
    expenseChartInstance = new Chart(expenseCtx, {
        type: 'doughnut',
        data: {
            labels: categories,
            datasets: [{
                data: values,
                backgroundColor: [
                    '#ff1744', '#00b4d8', '#00e676', '#9d4edd', '#ffb703', '#f72585'
                ],
                borderWidth: 2,
                borderColor: '#171821'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#f1f3f9', font: { family: 'Outfit', size: 12 } }
                }
            },
            cutout: '65%'
        }
    });
}

// Form Handlers
async function handleExpenseSubmit(e) {
    e.preventDefault();
    const amount = parseFloat(document.getElementById("exp-amount").value);
    const category = document.getElementById("exp-category").value;
    const date = document.getElementById("exp-date").value;
    const description = document.getElementById("exp-desc").value;

    const payload = { amount, category, date, description };

    try {
        const response = await fetch('/api/expenses/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Failed to post expense");
        
        showFormAlert("success", "Expense logged successfully!");
        showToast("Logged Expense of " + amount, "green");
        
        // Reset and refresh
        document.getElementById("exp-amount").value = "";
        document.getElementById("exp-desc").value = "";
        fetchAnalytics();
        
    } catch (err) {
        showFormAlert("error", "Error: " + err.message);
    }
}

async function handleClassificationSubmit(e) {
    e.preventDefault();
    const app_name = document.getElementById("cls-app-name").value;
    const classification = document.getElementById("cls-type").value;

    const payload = { app_name, classification };

    try {
        const response = await fetch('/api/classifications/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Failed to save classification");
        
        showFormAlert("success", `App "${app_name}" classified as ${classification}`);
        showToast(`Saved classification for ${app_name}`, "purple");
        
        document.getElementById("cls-app-name").value = "";
        fetchAnalytics();
        
    } catch (err) {
        showFormAlert("error", "Error: " + err.message);
    }
}

async function handleScreenTimeSubmit(e) {
    e.preventDefault();
    const total_time_seconds = parseInt(document.getElementById("scr-seconds").value);
    const device = document.getElementById("scr-device").value;
    const date = document.getElementById("scr-date").value;

    const payload = { total_time_seconds, device, date };

    try {
        const response = await fetch('/api/screen-time/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Failed to save screen time");
        
        showFormAlert("success", `Screen time saved for ${device}`);
        showToast(`Logged ${device} screen time`, "blue");
        
        document.getElementById("scr-seconds").value = "";
        fetchAnalytics();
        
    } catch (err) {
        showFormAlert("error", "Error: " + err.message);
    }
}

// Utilities
function showFormAlert(type, message) {
    const alertEl = document.getElementById("form-message");
    alertEl.className = `form-alert ${type}`;
    alertEl.innerText = message;
    
    setTimeout(() => {
        alertEl.classList.add("hidden");
    }, 4000);
}

function showToast(message, color = "blue") {
    const toast = document.getElementById("toast");
    
    let icon = '<i class="fa-solid fa-info-circle text-blue"></i>';
    if (color === "green") icon = '<i class="fa-solid fa-circle-check text-green"></i>';
    if (color === "rose") icon = '<i class="fa-solid fa-triangle-exclamation text-rose"></i>';
    if (color === "purple") icon = '<i class="fa-solid fa-fingerprint text-purple"></i>';
    
    toast.innerHTML = `${icon} <span>${message}</span>`;
    toast.className = `toast border-neon-${color}`;
    
    setTimeout(() => {
        toast.className = "toast hidden";
    }, 3500);
}

function formatCurrency(val, currency) {
    const symbols = { "INR": "₹", "USD": "$", "EUR": "€" };
    const sym = symbols[currency] || currency;
    return `${sym} ${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function formatSeconds(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hrs > 0) {
        return `${hrs}h ${mins}m`;
    }
    return `${mins}m`;
}
