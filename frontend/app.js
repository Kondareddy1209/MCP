// ==========================================
// YOUANDYOUR THINGS ENGINE FRONTEND (app.js)
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
    
    // STRICT matches first — prevent substring false positives
    if (processName === "cursor.exe" || processName === "cursor") return "Cursor";
    if (processName === "code.exe" || processName === "code" || processName === "vs code" || processName.startsWith("code -")) return "VS Code";
    if (processName === "chrome.exe" || processName === "chrome") return "Chrome";
    if (processName === "firefox.exe" || processName === "firefox") return "Firefox";
    if (processName === "msedge.exe" || processName === "msedge") return "Edge";
    
    // Partial matches for terminal/shell tools
    if (processName.includes("cmd") || processName.includes("powershell") || processName.includes("terminal") || processName.includes("wt.exe")) return "Terminal";
    
    // Partial matches for browser-based apps (window title based)
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

// ==========================================
// PURE TELEMETRY COMPUTATION ENGINE
// ==========================================
// DB: itsyou_clean.db (single source of truth)
// Timestamps: IST (Asia/Kolkata, UTC+5:30), stored as local datetime strings
// Format: "2026-07-15 11:30:00" (space separator, no Z suffix)
// STEP 8: Frontend trusts backend data 100% — NO fallback to old/cached values

function computeTelemetryEngine(data, days) {
    const now = new Date();
    const meta = data.meta || {};

    // ── TODAY string from server meta (most reliable) ──────────────────
    // Server sends today_ist: "2026-07-15" — use this to avoid browser TZ issues
    const localTodayStr = meta.today_ist || [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, '0'),
        String(now.getDate()).padStart(2, '0')
    ].join('-');

    console.group("🕵️ TELEMETRY ENGINE v2.0 — itsyou_clean.db");
    console.log("SERVER today_ist  :", meta.today_ist || "not sent");
    console.log("SERVER start_date :", meta.start_date || "not sent");
    console.log("SERVER record_count:", meta.record_count ?? "?");
    console.log("SERVER database   :", meta.database || "?");
    console.log("DAYS selected     :", days);
    console.log("USER TZ           :", Intl.DateTimeFormat().resolvedOptions().timeZone);
    console.groupEnd();

    // ── Local midnight of today ────────────────────────────────────────
    const localMidnightToday = new Date(`${localTodayStr}T00:00:00`);

    // ── Cutoff for N-day range ─────────────────────────────────────────
    const cutoffDate = new Date(localMidnightToday);
    cutoffDate.setDate(cutoffDate.getDate() - (days - 1));

    // ── isDateInRange: checks YYYY-MM-DD date field ────────────────────
    function isDateInRange(dateStr) {
        if (!dateStr) return false;
        if (days === 1) return dateStr === localTodayStr;
        const d = new Date(dateStr + "T00:00:00");
        if (isNaN(d.getTime())) return false;
        return d >= cutoffDate;
    }

    // ── isTimestampInRange: normalizes "YYYY-MM-DD HH:MM:SS" ──────────
    function isTimestampInRange(tsStr) {
        if (!tsStr) return false;
        const normalized = String(tsStr).replace(' ', 'T'); // space → T
        const d = new Date(normalized);
        if (isNaN(d.getTime())) return false;
        if (days === 1) return d >= localMidnightToday;
        return d >= cutoffDate;
    }

    // ── Unified record filter ──────────────────────────────────────────
    function isInTimeframe(record) {
        if (record.date) return isDateInRange(record.date);
        const ts = record.timestamp || record.time || record.created_at;
        return isTimestampInRange(ts);
    }

    const rawEvents     = data.events      || [];
    const rawUsage      = data.app_usage   || [];
    const rawExpenses   = data.expenses    || [];
    const rawScreenTime = data.screen_time || [];

    // ── STEP 1: Log raw sample ─────────────────────────────────────────
    console.group("📦 Raw API Sample (first 3)");
    console.log(rawUsage.slice(0, 3).map(u => ({
        app: u.app_name, date: u.date, timestamp: u.timestamp
    })));
    console.groupEnd();

    const filteredEvents     = rawEvents.filter(e  => isTimestampInRange(e.timestamp));
    const filteredUsage      = rawUsage.filter(u   => isInTimeframe(u));
    const filteredExpenses   = rawExpenses.filter(e => isInTimeframe(e));
    const filteredScreenTime = rawScreenTime.filter(s => isInTimeframe(s));

    // ── STEP 5: Filter counts ──────────────────────────────────────────
    console.group("📊 Filter Counts");
    console.log(`app_usage  : RAW=${rawUsage.length}  → FILTERED=${filteredUsage.length}`);
    console.log(`events     : RAW=${rawEvents.length}  → FILTERED=${filteredEvents.length}`);
    console.log(`TODAY=${localTodayStr}  cutoff=${cutoffDate.toDateString()}`);
    if (rawUsage.length > 0) {
        console.log(`DB latest date: "${rawUsage[0].date}" | today match? ${rawUsage[0].date === localTodayStr}`);
    }
    console.groupEnd();

    // ── STEP 8: NO FALLBACK — trust backend data ───────────────────────
    // If today has no data → show clean empty state ("No Data")
    // This is correct: new DB starts empty, data grows as tracker runs
    const resolvedUsage = filteredUsage;

    if (filteredUsage.length === 0 && rawUsage.length > 0 && days === 1) {
        console.info(`ℹ️ No data for today (${localTodayStr}). Start the tracker to collect data.`);
        console.info(`   Server has data up to: ${rawUsage[0]?.date || "unknown"}`);
    }

    const normalizedUsage = resolvedUsage.map(app => {
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
        console.warn("⚠️ No telemetry data for this timeframe — start the tracker");
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

function renderDashboard(computedData, days) {
    // ✅ 1. HARD RESET STATE (MANDATORY)
    AppState.charts = {};
    AppState.metrics = {};
    AppState.insights = {};
    AppState.alerts = [];

    // ✅ 2. NULL DATA → wipe charts and show empty state
    if (!computedData) {
        console.warn("⚠️ computedData is null — clearing all charts");
        showSystemStatus("No telemetry data available yet");
        try {
            // CRITICAL: Always destroy canvas charts on empty data to prevent ghost apps
            renderCharts([], []);
            renderAlerts([]);
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
        } catch (e) {
            console.error("Failed to render empty state:", e);
        }
        return;
    }

    const { events = [], app_usage = [], expenses = [], screen_time = [], metrics = {}, insights = {}, alerts = [] } = computedData;

    // 🔍 LIFECYCLE LOGS
    console.log("COMPUTED DATA:", computedData);
    console.log("EVENTS LENGTH:", events?.length);
    console.log("APP USAGE LENGTH:", app_usage?.length);

    // ✅ EMPTY GUARD: wipe charts, then return — do NOT skip chart clearing
    if (!app_usage || app_usage.length === 0) {
        console.warn("⚠️ No app usage after filtering — clearing charts");
        try {
            renderCharts([], []);  // MANDATORY: clears ghost apps from canvas
            renderAlerts([]);
        } catch (e) {
            console.error("Failed to clear empty charts:", e);
        }
        return;
    }

    // 🧪 STEP 5 — VERIFY FILTER
    console.log("FILTERED APP USAGE:", app_usage.map(a => a.app_name));

    // ✅ 3. BUILD CHART DATA (PURE REDUCER)
    const appDistribution = (app_usage || []).reduce((acc, item) => {
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
        (app_usage || [])
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
    console.log("CHART LABELS:", labels);

    // ✅ 8. FINAL ASSERTION FOR CURSOR GHOST SPECIFIC
    if (labels.includes("cursor") && !rawApps.has("cursor")) {
        throw new Error("🚨 Ghost app detected: Cursor should not be rendered");
    }

    const computedMetrics = {
        ...metrics,
        insights: {
            biggest_time_waster: insights.time_waster,
            spending_pattern: insights.expense_category,
            suggestion: insights.recommendation
        },
        detected_habits: insights.habits.includes("No data") ? [] : insights.habits,
        alerts: alerts
    };

    // Protect Entire Render Pipeline (Wrap rendering in try/catch)
    try {
        renderCurrentSession(AppState.currentSession);
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
        renderCharts(chartMappedUsages, screen_time || []);
    } catch (err) {
        console.error("renderCharts failure:", err);
    }
    try {
        renderRawEventsStream(events || []);
    } catch (err) {
        console.error("renderRawEventsStream failure:", err);
    }
    try {
        renderAlerts(alerts);
    } catch (err) {
        console.error("renderAlerts failure:", err);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 DOMContentLoaded fired — registering listeners");
    // Register Dropdown Events
    const rangeSelect = document.getElementById("days-range-select");
    rangeSelect.addEventListener("change", (e) => {
        console.log("📆 Range changed to:", e.target.value, "days");
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
    console.log("🔄 initializeDashboard called — starting polling loop");
    showLoadingState();
    try {
        // Run initial full sync
        await syncDashboard();
        
        // Setup polling interval: unified cycle every 10 seconds
        setInterval(syncDashboard, 10000);
        console.log("⏰ Polling interval set (10s)");
        
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
            analytics: raw.analytics || raw.metrics || {},
            // ✅ Pass meta through so computeTelemetryEngine can log timezone info
            meta: raw.meta || null
        };
        
        console.log("NORMALIZED DATA:", data); // DEBUG LOG
        AppState.dashboardData = data;

        if (!AppState.dashboardData) {
            showLoadingState();
            return;
        }

        const session = resolveCurrentSession(data.events, data.app_usage);
        AppState.currentSession = session;
        
        // compute telemetry engine first
        const computedData = computeTelemetryEngine(AppState.dashboardData, days);
        
        // FORCE RENDER (pass computedData directly)
        renderDashboard(computedData, days);
        
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
