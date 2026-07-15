// ==========================================
// ANTIGRAVITY ENGINE ORCHESTRATOR (app.js)
// ==========================================

import { fetchDashboard } from './api.js';

import { renderDashboard as renderMetrics } from './components/dashboard.js';
import { renderCharts } from './components/charts.js';
import { renderLiveActivity, renderRawEventsStream } from './components/activity.js';
import { renderAlerts } from './components/alerts.js';

// Global application state object
const AppState = {
    selectedDays: 1,
    dashboardData: null,
    todayData: [],
    currentSession: null,
    insights: null,
    loading: true,
    charts: {},
    metrics: {},
    alerts: []
};

function isToday(timestamp) {
    if (!timestamp) return false;
    const now = new Date();
    
    // Convert YYYY-MM-DD to local time ISO to prevent UTC timezone shifts
    let val = timestamp;
    if (/^\d{4}-\d{2}-\d{2}$/.test(val)) {
        val = val + "T00:00:00";
    }
    
    const d = new Date(val);
    return (
        d.toLocaleDateString() === now.toLocaleDateString()
    );
}

function extractNameFromProcess(proc) {
    if (!proc) return "Background";
    // Extract file name from absolute path and strip .exe
    return proc.split("\\").pop().replace(".exe", "");
}

function getAppName(log) {
    const processName = (log.app_name || "").toLowerCase().trim();
    
    // PRIORITY: process name (most reliable)
    if (processName.includes("code.exe") || processName.includes("code")) return "VS Code";
    if (processName.includes("chrome")) return "Chrome";
    if (processName.includes("firefox")) return "Firefox";
    
    // STRICT match for Cursor (NOT substring matching)
    if (processName === "cursor.exe" || processName === "cursor") return "Cursor";
    
    if (processName.includes("cmd.exe") || processName.includes("powershell.exe") || processName.includes("terminal")) return "Terminal";
    if (processName.includes("youtube")) return "YouTube";
    if (processName.includes("instagram")) return "Instagram";
    if (processName.includes("netflix")) return "Netflix";
    if (processName.includes("spotify")) return "Spotify";
    if (processName.includes("discord")) return "Discord";
    if (processName.includes("slack")) return "Slack";
    
    return extractNameFromProcess(log.app_name);
}

const categoryMap = {
    "code": "productive",
    "vs code": "productive",
    "cursor": "productive",
    "terminal": "productive",
    "cmd": "productive",
    "powershell": "productive",
    "chrome": "neutral",
    "firefox": "neutral",
    "youtube": "distracting",
    "instagram": "distracting",
    "netflix": "distracting",
    "spotify": "distracting",
    "discord": "distracting",
    "slack": "neutral"
};

function getCategory(appName) {
    if (!appName) return "Unclassified";
    const key = appName.toLowerCase().trim();
    return categoryMap[key] || "Unclassified";
}

function markForLearning(appName) {
    try {
        if (!localStorage.learnQueue) {
            localStorage.learnQueue = JSON.stringify([]);
        }
        let queue = JSON.parse(localStorage.learnQueue);
        if (!queue.includes(appName)) {
            queue.push(appName);
        }
        localStorage.learnQueue = JSON.stringify(queue);
    } catch (e) {
        console.error("Error updating learning queue in localStorage:", e);
    }
}

function showSystemStatus(status) {
    console.log("System Status Update:", status);
    const suggestionEl = document.getElementById("val-suggestion");
    if (suggestionEl) {
        suggestionEl.innerText = `${status}. Ensure the tracker daemon is active.`;
    }
}

// Loading indicator helper
function showLoadingState() {
    toggleLoading(true);
}

function resolveCurrentSession(events, usage) {
    let latestEvent = null;
    let latestUsage = null;

    // Sort events using safe date fallbacks (timestamp, time, created_at)
    if (events && events.length > 0) {
        latestEvent = [...events].sort((a, b) => {
            const valA = a.timestamp || a.time || a.created_at;
            const valB = b.timestamp || b.time || b.created_at;
            return new Date(valB) - new Date(valA);
        })[0];
    }

    // Sort usage using safe date fallbacks (timestamp, time, created_at)
    if (usage && usage.length > 0) {
        latestUsage = [...usage].sort((a, b) => {
            const valA = a.timestamp || a.time || a.created_at;
            const valB = b.timestamp || b.time || b.created_at;
            return new Date(valB) - new Date(valA);
        })[0];
    }

    // PRIORITY 1 → usage (more reliable)
    if (latestUsage && latestUsage.app_name) {
        return {
            app: latestUsage.app_name,
            title: latestUsage.window_title || "Active session"
        };
    }

    // PRIORITY 2 → events
    if (latestEvent) {
        return {
            app: latestEvent.process || latestEvent.app_name || "Background",
            title: latestEvent.window_title || latestEvent.title || "No window title"
        };
    }

    // FALLBACK
    return {
        app: "Idle",
        title: "No activity detected"
    };
}

function renderCurrentSession(session) {
    if (!session) return;

    const appNameEl = document.getElementById("appName") || document.getElementById("live-app-name");
    const windowTitleEl = document.getElementById("windowTitle") || document.getElementById("live-window-title");
    const pulseEl = document.getElementById("activity-pulse-el");
    const badgeEl = document.getElementById("live-state-badge");

    if (appNameEl) appNameEl.textContent = session.app;
    if (windowTitleEl) windowTitleEl.textContent = session.title;

    if (pulseEl && badgeEl) {
        if (session.app === "Idle") {
            pulseEl.className = "activity-pulse pulse-orange";
            badgeEl.className = "status-badge badge-neutral";
            badgeEl.innerText = "IDLE";
        } else {
            const cat = getCategory(session.app);
            if (cat === "productive") {
                pulseEl.className = "activity-pulse pulse-green";
                badgeEl.className = "status-badge badge-productive";
                badgeEl.innerText = "PRODUCTIVE";
            } else if (cat === "distracting") {
                pulseEl.className = "activity-pulse pulse-rose";
                badgeEl.className = "status-badge badge-distracting";
                badgeEl.innerText = "DISTRACTING";
            } else {
                pulseEl.className = "activity-pulse pulse-blue";
                badgeEl.className = "status-badge badge-neutral";
                badgeEl.innerText = "NEUTRAL";
            }
        }
    }
}

// PURE TELEMETRY COMPUTATION ENGINE
function computeTelemetryEngine(data, days) {
    const now = new Date();
    
    function isInTimeframe(timestamp) {
        if (!timestamp) return false;
        
        let val = timestamp;
        if (/^\d{4}-\d{2}-\d{2}$/.test(val)) {
            val = val + "T00:00:00";
        }
        const d = new Date(val);
        if (isNaN(d.getTime())) return false;
        
        if (days === 1) {
            return d.toLocaleDateString() === now.toLocaleDateString();
        } else {
            const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
            return d >= cutoff;
        }
    }
    
    const rawEvents = data.events || [];
    const rawUsage = data.app_usage || data.apps || [];
    const rawExpenses = data.expenses || [];
    const rawScreenTime = data.screen_time || [];
    
    const filteredEvents = rawEvents.filter(e => isInTimeframe(e.timestamp));
    const filteredUsage = rawUsage.filter(u => isInTimeframe(u.timestamp || u.date));
    const filteredExpenses = rawExpenses.filter(e => isInTimeframe(e.timestamp || e.date));
    const filteredScreenTime = rawScreenTime.filter(s => isInTimeframe(s.date));
    
    const normalizedUsage = filteredUsage.map(app => {
        const cleanName = getAppName(app);
        const dur = app.duration_seconds || app.duration || 0;
        return {
            ...app,
            app: cleanName,
            name: cleanName,
            app_name: cleanName,
            duration: dur,
            duration_seconds: dur
        };
    });

    if (filteredEvents.length === 0 && normalizedUsage.length === 0) {
        console.warn("⚠️ No telemetry data available yet");
        return null;
    }
    
    const totalUsageHours = normalizedUsage.reduce((sum, u) => {
        return sum + (u.duration / 3600);
    }, 0);
    
    const productiveHours = normalizedUsage.reduce((sum, u) => {
        const category = getCategory(u.app_name);
        return sum + (category === "productive" ? (u.duration / 3600) : 0);
    }, 0);
    
    const distractionHours = normalizedUsage.reduce((sum, u) => {
        const category = getCategory(u.app_name);
        return sum + (category === "distracting" ? (u.duration / 3600) : 0);
    }, 0);
    
    const safeTotal = totalUsageHours > 0 ? totalUsageHours : 1;
    const productivityScore = Math.round((productiveHours / safeTotal) * 100);
    
    const deepWorkSessions = productivityScore > 50 ? 1 : 0;
    const totalSessions = 1;
    const focusEfficiency = totalSessions > 0 ? Math.round((deepWorkSessions / totalSessions) * 100) : 0;
    
    const lateNightUsage = normalizedUsage.some(app => {
        const ts = app.timestamp || app.date || now.toISOString();
        let val = ts;
        if (/^\d{4}-\d{2}-\d{2}$/.test(val)) {
            val = val + "T00:00:00";
        }
        const hour = new Date(val).getHours();
        return hour >= 23;
    });
    const continuousSession = normalizedUsage.some(app => (app.duration / 3600) > 4);
    const distractionRatio = totalUsageHours > 0 ? (distractionHours / totalUsageHours) : 0;
    
    let burnoutIndex = 10;
    if (totalUsageHours > 8) burnoutIndex += 30;
    if (lateNightUsage) burnoutIndex += 20;
    if (continuousSession) burnoutIndex += 20;
    if (distractionRatio > 0.4) burnoutIndex += 20;
    burnoutIndex = Math.min(burnoutIndex, 100);
    
    const burnoutRisk = burnoutIndex > 70 ? "High" : (burnoutIndex > 40 ? "Medium" : "Low");
    
    let topCategory = "No data";
    let totalSpend = 0;
    if (filteredExpenses.length > 0) {
        const categoryMap = {};
        filteredExpenses.forEach(e => {
            categoryMap[e.category] = (categoryMap[e.category] || 0) + e.amount;
            totalSpend += e.amount;
        });
        const entries = Object.entries(categoryMap);
        if (entries.length > 0) {
            const top = entries.reduce((max, curr) => (curr[1] > max[1] ? curr : max));
            topCategory = `${top[0]} (₹${top[1].toFixed(2)})`;
        }
    }
    
    let timeWaster = "No data";
    const timeWasters = normalizedUsage.filter(app => getCategory(app.app_name) === "distracting");
    if (timeWasters.length > 0) {
        const maxApp = timeWasters.reduce((max, app) =>
            app.duration > max.duration ? app : max
        );
        const hours = maxApp.duration / 3600;
        timeWaster = `${maxApp.app_name} (${hours.toFixed(1)} hrs)`;
    }
    
    const habits = normalizedUsage
        .filter(app => (app.duration / 60) > 60)
        .map(app => app.name);
    const uniqueHabits = [...new Set(habits)];
    const habitsResult = uniqueHabits.length > 0 ? uniqueHabits : ["No data"];
    
    let suggestion = "No activity tracked";
    if (normalizedUsage.length > 0) {
        suggestion = productivityScore > 70 
            ? "Great job maintaining focus today!" 
            : "Try to minimize distractions during work blocks.";
    }
    
    let alertsList = [];
    if (normalizedUsage.length > 0) {
        if (burnoutIndex > 70) {
            alertsList.push({
                priority: "HIGH",
                timestamp: now.toISOString(),
                message: "Burnout Warning: Exceeded 8 hours of usage today with active late-night sessions."
            });
        }
        if (distractionHours > 3) {
            alertsList.push({
                priority: "MEDIUM",
                timestamp: now.toISOString(),
                message: "Distraction Overload: High distraction app usage today."
            });
        }
    }
    
    // MANDATORY LOGGING
    console.log("EVENT COUNT:", filteredEvents.length);
    console.log("USAGE COUNT:", normalizedUsage.length);
    console.log("TOTAL HOURS:", totalUsageHours.toFixed(2));
    console.log("PRODUCTIVITY SCORE:", productivityScore);
    console.log("FILTERED TIME RANGE:", days === 1 ? "Today" : `Last ${days} Days`);
    
    return {
        events: filteredEvents,
        app_usage: normalizedUsage,
        expenses: filteredExpenses,
        screen_time: filteredScreenTime,
        metrics: {
            productivity_score: productivityScore,
            focus_efficiency: focusEfficiency,
            burnout_score: burnoutIndex,
            burnout_risk: burnoutRisk,
            distraction_cost: distractionHours * 100,
            deep_work_sessions: deepWorkSessions,
            total_sessions: totalSessions,
            currency: "INR",
            total_spent: totalSpend,
            total_usage_hours: totalUsageHours
        },
        insights: {
            time_waster: timeWaster,
            expense_category: topCategory,
            habits: habitsResult,
            recommendation: suggestion
        },
        alerts: alertsList
    };
}

function renderDashboard(state) {
    // ✅ 1. HARD RESET STATE (MANDATORY)
    state.charts = {};
    state.metrics = {};
    state.insights = {};
    state.alerts = [];

    if (!state || !state.dashboardData) return;

    const days = state.selectedDays;
    
    // ✅ 2. USE ONLY FILTERED DATA
    const filtered = computeTelemetryEngine(state.dashboardData, days);

    if (!filtered) {
        showSystemStatus("No telemetry data available yet");
        try {
            renderMetrics({
                productivity_score: 0,
                focus_efficiency: 0,
                burnout_score: 0,
                burnout_risk: "Low",
                distraction_cost: 0,
                deep_work_sessions: 0,
                total_sessions: 1,
                currency: "INR",
                insights: {
                    biggest_time_waster: "No data",
                    spending_pattern: "No data",
                    suggestion: "No activity tracked"
                },
                detected_habits: [],
                alerts: []
            }, days);
            renderCharts([], []);
            renderAlerts([]);
        } catch (e) {
            console.error("Failed to render empty state:", e);
        }
        return;
    }

    console.log("FILTERED APP USAGE:", filtered.app_usage);

    // ✅ 3. BUILD CHART DATA (PURE REDUCER)
    const appDistribution = (filtered.app_usage || []).reduce((acc, item) => {
        if (!item) return acc;
        
        // Support app, name, or app_name safely
        const appNameField = item.app || item.name || item.app_name;
        if (!appNameField) return acc;

        const app = appNameField.trim().toLowerCase();
        const duration = Number(item.duration || item.duration_seconds) || 0;

        // ✅ VALIDATION
        if (!app || duration <= 0) return acc;

        acc[app] = (acc[app] || 0) + duration;

        return acc;
    }, {});

    // ✅ 4. ASSERTION (CATCH GHOST APPS)
    const rawApps = new Set(
        (filtered.app_usage || [])
            .map(a => (a.app || a.name || a.app_name)?.trim().toLowerCase())
            .filter(Boolean)
    );

    Object.keys(appDistribution).forEach(app => {
        if (!rawApps.has(app)) {
            throw new Error(`🚨 Ghost app detected: ${app}`);
        }
    });

    // ✅ 5. FINAL CHART DATA
    const labels = Object.keys(appDistribution);
    const data = Object.values(appDistribution);

    console.log("FINAL CHART DATA:", appDistribution);

    // ✅ 8. FINAL ASSERTION FOR CURSOR GHOST SPECIFIC
    const validApps = (filtered.app_usage || [])
        .filter(app =>
            app &&
            (app.app || app.name || app.app_name) &&
            typeof (app.duration || app.duration_seconds || 0) === "number" &&
            (app.duration || app.duration_seconds || 0) > 0
        )
        .map(app => (app.app || app.name || app.app_name).toLowerCase().trim());

    if (labels.includes("cursor") && !validApps.includes("cursor")) {
        throw new Error("🚨 Ghost app detected: Cursor should not be rendered");
    }

    // 5. UI RENDER GUARD
    if (!labels.length) {
        console.warn("No valid app usage data");
        return;
    }

    const computedMetrics = {
        ...filtered.metrics,
        insights: {
            biggest_time_waster: filtered.insights.time_waster,
            spending_pattern: filtered.insights.expense_category,
            suggestion: filtered.insights.recommendation
        },
        detected_habits: filtered.insights.habits.includes("No data") ? [] : filtered.insights.habits,
        alerts: filtered.alerts
    };

    // Protect Entire Render Pipeline (Wrap rendering in try/catch)
    try {
        renderCurrentSession(state.currentSession);
    } catch (err) {
        console.error("renderCurrentSession failure:", err);
    }
    try {
        renderMetrics(computedMetrics, days);
    } catch (err) {
        console.error("renderMetrics failure:", err);
    }
    try {
        // Map back to expected components layout
        const chartMappedUsages = labels.map((appLabel, index) => ({
            app_name: appLabel,
            duration_seconds: data[index]
        }));
        renderCharts(chartMappedUsages, filtered.screen_time || []);
    } catch (err) {
        console.error("renderCharts failure:", err);
    }
    try {
        renderRawEventsStream(filtered.events || []);
    } catch (err) {
        console.error("renderRawEventsStream failure:", err);
    }
    try {
        renderAlerts(filtered.alerts);
    } catch (err) {
        console.error("renderAlerts failure:", err);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Register Dropdown Events
    const rangeSelect = document.getElementById("days-range-select");
    rangeSelect.addEventListener("change", (e) => {
        // Prevent State Leak on change
        AppState.selectedDays = parseInt(e.target.value);
        AppState.todayData = [];
        AppState.insights = null;
        AppState.dashboardData = null;
        syncDashboard();
    });

    // Start Polling Loops
    initializeDashboard();
});

async function initializeDashboard() {
    showLoadingState();
    try {
        // Run initial full sync
        await syncDashboard();
        
        // Setup polling interval: unified cycle every 10 seconds (reduces DB locks and query noise)
        setInterval(syncDashboard, 10000);
        
    } catch (e) {
        console.error("Dashboard initial sync failed:", e);
        showErrorUI(e.message);
    } finally {
        toggleLoading(false);
    }
}

// Unified Polling Cycle
async function syncDashboard() {
    try {
        const days = AppState.selectedDays;
        
        // Single aggregated API request
        const raw = await fetchDashboard(days);
        console.log("RAW API RESPONSE:", raw); // DEBUG LOG
        
        // Normalize API response
        const data = {
            events: raw.events || raw.activity || [],
            app_usage: raw.app_usage || raw.usage || [],
            expenses: raw.expenses || [],
            screen_time: raw.screen_time || [],
            alerts: raw.alerts || [],
            analytics: raw.analytics || raw.metrics || {}
        };
        
        console.log("NORMALIZED DATA:", data); // DEBUG LOG
        AppState.dashboardData = data;

        if (!AppState.dashboardData) {
            showLoadingState();
            return;
        }

        const session = resolveCurrentSession(data.events, data.app_usage);
        AppState.currentSession = session;
        
        // FORCE RENDER
        renderDashboard(AppState);
        
        toggleLoading(false);
    } catch (e) {
        console.error("Error in dashboard synchronization cycle:", e);
    }
}

function toggleLoading(isLoading) {
    AppState.loading = isLoading;
    const loader = document.getElementById("loading");
    if (loader) {
        if (isLoading) {
            loader.classList.remove("hidden");
        } else {
            loader.classList.add("hidden");
        }
    }
}

function showErrorUI(errorMsg) {
    const container = document.querySelector(".dashboard-container");
    container.innerHTML = `
        <div class="glass-card" style="margin: 4rem auto; max-width: 600px; text-align: center; border-color: var(--neon-rose); padding: 3rem;">
            <span style="font-size: 3rem; color: var(--neon-rose);"><i class="fa-solid fa-triangle-exclamation"></i></span>
            <h2 style="margin-top: 1.5rem; font-size: 1.5rem;">Database Synchronization Offline</h2>
            <p style="color: var(--text-secondary); margin-top: 0.75rem; line-height: 1.5;">
                Could not connect to the Antigravity backend API service. Ensure the FastAPI application is running locally.
            </p>
            <div style="margin-top: 2rem; background: rgba(0,0,0,0.15); padding: 1rem; border-radius: 8px; font-family: monospace; font-size: 0.85rem; color: var(--neon-rose);">
                ${errorMsg}
            </div>
            <button onclick="window.location.reload()" style="margin-top: 2rem; background: linear-gradient(135deg, var(--neon-blue), #0077b6); border: none; padding: 0.75rem 2rem; border-radius: 30px; color: white; font-weight: 700; cursor: pointer;">
                Retry Sync
            </button>
        </div>
    `;
}
