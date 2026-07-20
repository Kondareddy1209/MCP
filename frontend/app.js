// ==========================================
// YOUANDYOUR THINGS ENGINE FRONTEND (app.js)
// ==========================================

import { fetchDashboard } from './api.js';

import { renderDashboard as renderMetrics } from './components/dashboard.js?v=2.0.2';
import { renderCharts } from './components/charts.js?v=2.0.2';
import { renderLiveActivity, renderRawEventsStream } from './components/activity.js?v=2.0.2';
import { renderAlerts } from './components/alerts.js?v=2.0.2';

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
    if (processName === "winword.exe" || processName === "winword") return "Word";
    if (processName === "powerpnt.exe" || processName === "powerpnt" || processName === "powerpoint") return "PowerPoint";
    
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

function resolveCurrentSession(events, usage, currentActivityBackend) {
    const IGNORE_APPS = new Set(["itsyoutrackerdaemon", "tracker.exe", "python.exe", "uvicorn.exe", "cmd.exe", "powershell.exe"]);
    
    if (currentActivityBackend && currentActivityBackend.app && !IGNORE_APPS.has(currentActivityBackend.app.toLowerCase())) {
        return {
            app: currentActivityBackend.app,
            title: currentActivityBackend.window || "Active foreground app"
        };
    }

    let latestEvent = null;
    let latestUsage = null;

    // Filter and sort events
    const filteredEvents = (events || []).filter(e => {
        const app = (e.app_name || e.app || "").toLowerCase().trim();
        return app && !IGNORE_APPS.has(app);
    });

    if (filteredEvents.length > 0) {
        latestEvent = [...filteredEvents].sort((a, b) => {
            const valA = a.timestamp || a.time || a.created_at;
            const valB = b.timestamp || b.time || b.created_at;
            return new Date(valB) - new Date(valA);
        })[0];
    }

    // Filter and sort usage
    const filteredUsage = (usage || []).filter(u => {
        const app = (u.app_name || u.app || "").toLowerCase().trim();
        return app && !IGNORE_APPS.has(app);
    });

    if (filteredUsage.length > 0) {
        latestUsage = [...filteredUsage].sort((a, b) => {
            const valA = a.timestamp || a.time || a.created_at;
            const valB = b.timestamp || b.time || b.created_at;
            return new Date(valB) - new Date(valA);
        })[0];
    }

    // PRIORITY 1 → usage (more reliable)
    if (latestUsage) {
        return {
            app: getAppName({ app_name: latestUsage.app_name || latestUsage.app || "Background" }),
            title: latestUsage.window_title || latestUsage.window || "Active session"
        };
    }

    // PRIORITY 2 → events
    if (latestEvent) {
        return {
            app: getAppName({ app_name: latestEvent.process || latestEvent.app_name || latestEvent.app || "Background" }),
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

    const displayApp = getAppName({ app_name: session.app });
    if (appNameEl) appNameEl.textContent = displayApp;
    if (windowTitleEl) windowTitleEl.textContent = session.title;

    if (pulseEl && badgeEl) {
        if (displayApp === "Idle") {
            pulseEl.className = "activity-pulse pulse-orange";
            badgeEl.className = "status-badge badge-neutral";
            badgeEl.innerText = "IDLE";
        } else {
            const cat = getCategory(displayApp);
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
    const filteredScreenTime = rawScreenTime.filter(s => /^\d{2}:\d{2}$/.test(s.date) || isInTimeframe(s));

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
        alerts: alertsList,
        raw_backend: data.raw_backend,
        current_activity: data.current_activity
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

    const { events = [], app_usage = [], expenses = [], screen_time = [], metrics = {}, insights = {}, alerts = [], raw_backend = null } = computedData;

    // Update the live details grid from computed data (Task 9)
    const liveAct = computedData.current_activity;
    if (liveAct) {
        const devEl = document.getElementById("live-device");
        const durEl = document.getElementById("live-session-dur");
        const activeEl = document.getElementById("live-today-active");
        const idleEl = document.getElementById("live-idle-timer");
        const lastEl = document.getElementById("live-last-activity");
        
        if (devEl) devEl.innerText = liveAct.device || "laptop";
        if (durEl) durEl.innerText = liveAct.app !== "SYSTEM_IDLE" ? formatDuration(liveAct.duration) : "0s";
        if (activeEl) activeEl.innerText = liveAct.today_active_time || "0.0 hrs";
        if (idleEl) idleEl.innerText = liveAct.app === "SYSTEM_IDLE" ? formatDuration(liveAct.idle_timer) : "0s";
        if (lastEl) lastEl.innerText = liveAct.last_activity || "--";
    }

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
        productivity_score: raw_backend ? raw_backend.productivity_score : metrics.productivity_score,
        estimated_score: raw_backend ? raw_backend.estimated_score : null,
        estimate_confidence: raw_backend ? raw_backend.estimate_confidence : null,
        focus_efficiency: raw_backend ? raw_backend.focus_efficiency : metrics.focus_efficiency,
        burnout_score: raw_backend ? raw_backend.burnout_score : metrics.burnout_score,
        burnout_risk: raw_backend ? raw_backend.burnout_risk : metrics.burnout_risk,
        distraction_cost: raw_backend ? raw_backend.distraction_cost : metrics.distraction_cost,
        currency: raw_backend ? (raw_backend.currency || "INR") : "INR",
        total_spent: raw_backend ? (raw_backend.total_spent || 0) : 0,
        deep_work_sessions: raw_backend ? (raw_backend.deep_work_sessions || 0) : 0,
        total_sessions: raw_backend ? (raw_backend.total_sessions || 1) : 1,

        // Map productive/distracting/neutral seconds so hasNoActivity is false
        productive_time_seconds: raw_backend && raw_backend.productivity ? raw_backend.productivity.productive_minutes * 60 : 0,
        distracting_time_seconds: raw_backend && raw_backend.productivity ? raw_backend.productivity.distracting_minutes * 60 : 0,
        neutral_time_seconds: raw_backend && raw_backend.productivity ? raw_backend.productivity.neutral_minutes * 60 : 0,

        insights: raw_backend && raw_backend.insights ? {
            biggest_time_waster: raw_backend.insights.biggest_time_waster,
            spending_pattern: raw_backend.insights.spending_pattern,
            suggestion: raw_backend.insights.suggestion
        } : {
            biggest_time_waster: insights.time_waster,
            spending_pattern: insights.expense_category,
            suggestion: insights.recommendation
        },
        detected_habits: raw_backend ? (raw_backend.detected_habits || []) : (insights.habits.includes("No data") ? [] : insights.habits),
        recommendations: raw_backend ? (raw_backend.recommendations || []) : [],
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

let ws = null;
let notificationPermissionRequested = false;

function base64UrlToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function requestDesktopNotificationPermission() {
    if (!('Notification' in window) || notificationPermissionRequested) return;
    notificationPermissionRequested = true;
    if (Notification.permission === 'default') {
        try {
            await Notification.requestPermission();
        } catch (err) {
            console.warn('Notification permission prompt failed:', err);
        }
    }
}

async function registerPushSubscription() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    try {
        const swRegistration = await navigator.serviceWorker.register('/sw.js');
        const existing = await swRegistration.pushManager.getSubscription();
        if (existing) return;

        const vapidResponse = await fetch('/api/push/vapid-public-key');
        const vapidData = await vapidResponse.json();
        if (!vapidData.publicKey) return;

        const subscription = await swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: base64UrlToUint8Array(vapidData.publicKey),
        });

        await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                endpoint: subscription.endpoint,
                keys: subscription.toJSON().keys,
                userAgent: navigator.userAgent,
                device: /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
            }),
        });
    } catch (err) {
        console.warn('Push registration skipped:', err);
    }
}

async function setupNotifications() {
    await requestDesktopNotificationPermission();
    await registerPushSubscription();
}
function connectWebSocket() {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/ws/live`;
    
    console.log("🔌 Connecting WebSocket to:", wsUrl);
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log("✅ WebSocket connected");
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "ping") {
                // Heartbeat keepalive (Task 10)
                ws.send(JSON.stringify({ type: "pong" }));
                return;
            }
            if (data.type === "alert" && 'Notification' in window && Notification.permission === 'granted') {
                try {
                    new Notification(data.title || 'Alert', { body: data.body || '' });
                } catch (err) {
                    console.warn('Browser notification failed:', err);
                }
            }
            console.log("📥 WebSocket update received:", data);
            handleLiveUpdate(data);
        } catch (e) {
            console.error("Error parsing WebSocket message:", e);
        }
    };
    
    ws.onclose = () => {
        console.warn("❌ WebSocket closed — reconnecting in 3 seconds...");
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error("⚠️ WebSocket error:", err);
    };
}

function formatDuration(sec) {
    if (sec <= 0 || isNaN(sec)) return "0s";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function handleLiveUpdate(data) {
    // 1. Update Currently Active App Display
    const active = data.last_active;
    const appNameEl = document.getElementById("live-app-name");
    const windowTitleEl = document.getElementById("live-window-title");
    const pulseEl = document.getElementById("activity-pulse-el");
    const badgeEl = document.getElementById("live-state-badge");

    const IGNORE_APPS = new Set(["itsyoutrackerdaemon", "tracker.exe", "python.exe", "uvicorn.exe", "cmd.exe", "powershell.exe"]);
    const isActiveUserApp = active && active.app !== "None" && active.status === "active" && !IGNORE_APPS.has(active.app.toLowerCase());

    if (isActiveUserApp) {
        if (appNameEl) appNameEl.innerText = active.app;
        if (windowTitleEl) windowTitleEl.innerText = active.window;

        // M2 fix: derive classification
        let classification = "neutral";
        if (active.classification) {
            classification = active.classification;
        } else {
            const combinedStr = `${active.app} ${active.window || ""}`.toLowerCase();
            if (/leetcode|github|stackoverflow|notion|docs\.|chatgpt|claude|gemini|copilot|vs code|vscode|cursor|pycharm|terminal|powershell|cmd/i.test(combinedStr)) {
                classification = "productive";
            } else if (/youtube|instagram|facebook|twitter|x\.com|reddit|netflix|spotify|steam|twitch|disney|hulu|prime/i.test(combinedStr)) {
                classification = "distracting";
            }
        }

        const classRules = {
            "productive": { pulse: "pulse-green", badge: "badge-productive", text: "Productive" },
            "distracting": { pulse: "pulse-rose", badge: "badge-distracting", text: "Distracting" },
            "neutral": { pulse: "pulse-blue", badge: "badge-neutral", text: "Neutral" }
        };
        const state = classRules[classification] || classRules["neutral"];
        if (pulseEl) pulseEl.className = `activity-pulse ${state.pulse}`;
        if (badgeEl) {
            badgeEl.className = `status-badge ${state.badge}`;
            badgeEl.innerText = state.text.toUpperCase();
        }
    } else {
        // Handle Idle, Inactive, or daemon-only states correctly
        const isIdle = active && (active.app === "SYSTEM_IDLE" || active.app === "Idle" || (active.app && IGNORE_APPS.has(active.app.toLowerCase())));
        if (appNameEl) appNameEl.innerText = isIdle ? "User is idle" : "System Idle / Standby";
        if (windowTitleEl) windowTitleEl.innerText = isIdle ? "No user keyboard or mouse input detected recently." : "No active foreground window.";
        if (pulseEl) pulseEl.className = "activity-pulse pulse-orange";
        if (badgeEl) {
            badgeEl.className = "status-badge badge-neutral";
            badgeEl.innerText = "IDLE";
        }
    }

    // Update the live details grid (Task 9)
    const liveAct = data.current_activity;
    if (liveAct) {
        const devEl = document.getElementById("live-device");
        const durEl = document.getElementById("live-session-dur");
        const activeEl = document.getElementById("live-today-active");
        const idleEl = document.getElementById("live-idle-timer");
        const lastEl = document.getElementById("live-last-activity");
        
        if (devEl) devEl.innerText = liveAct.device || "laptop";
        if (durEl) durEl.innerText = liveAct.app !== "SYSTEM_IDLE" ? formatDuration(liveAct.duration) : "0s";
        if (activeEl) activeEl.innerText = liveAct.today_active_time || "0.0 hrs";
        if (idleEl) idleEl.innerText = liveAct.app === "SYSTEM_IDLE" ? formatDuration(liveAct.idle_timer) : "0s";
        if (lastEl) lastEl.innerText = liveAct.last_activity || "--";
    }

    // 2. Update Recent Events Stream (STEP 5)
    if (data.delta_event) {
        const container = document.getElementById("events-container");
        if (container) {
            const placeholder = container.querySelector(".loading-placeholder");
            if (placeholder) placeholder.remove();

            const row = document.createElement("div");
            row.className = "event-row-item";
            const rawTime = new Date(data.delta_event.timestamp);
            const timeStr = rawTime.toLocaleTimeString();

            // Map process name representation
            let cleanProcess = "Unknown";
            const processName = (data.delta_event.app_name || "").toLowerCase().trim();
            if (processName.includes("code")) cleanProcess = "VS Code";
            else if (processName.includes("chrome")) cleanProcess = "Chrome";
            else if (processName.includes("firefox")) cleanProcess = "Firefox";
            else if (processName.includes("cursor")) cleanProcess = "Cursor";
            else if (processName.includes("terminal") || processName.includes("powershell") || processName.includes("cmd")) cleanProcess = "Terminal";
            else if (processName.includes("youtube")) cleanProcess = "YouTube";
            else if (processName.includes("instagram")) cleanProcess = "Instagram";
            else cleanProcess = data.delta_event.app_name || "Unknown";

            row.innerHTML = `
                <span class="event-time-badge">[${timeStr}]</span>
                <span class="event-type-badge">${data.delta_event.event_type}</span>
                <span class="event-app-badge">${cleanProcess}</span>
                <span class="event-title-badge">${data.delta_event.window_title ? data.delta_event.window_title.substring(0, 45) : "-"}</span>
            `;
            container.insertBefore(row, container.firstChild);
            
            // Trim to top 15 events
            while (container.children.length > 15) {
                container.lastChild.remove();
            }
        }
    }

    // 3. Update Doughnut Chart (STEP 5)
    if (AppState.selectedDays === 1 && data.updated_summary) {
        const labels = Object.keys(data.updated_summary);
        const durations = Object.values(data.updated_summary);
        const chartMappedUsages = labels.map((appLabel, index) => ({
            app_name: appLabel,
            duration_seconds: durations[index]
        }));
        renderCharts(chartMappedUsages, []);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 DOMContentLoaded fired — registering listeners");
    setupNotifications();
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
    console.log("🔄 initializeDashboard called — starting dashboard");
    showLoadingState();
    try {
        // Run initial full sync
        await syncDashboard();

        // Setup real-time WebSocket connection (primary update mechanism)
        connectWebSocket();

        // Resilience fallback poll: 60s — only matters if WebSocket has dropped.
        // WebSocket pushes updates on every event; poll is a safety net, not the main loop.
        setInterval(syncDashboard, 60000);
        console.log("⏰ Resilience fallback poll set (60s). WebSocket is primary.");

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
            meta: raw.meta || null,
            raw_backend: raw,
            current_activity: raw.current_activity || null
        };
        
        console.log("NORMALIZED DATA:", data); // DEBUG LOG
        AppState.dashboardData = data;

        if (!AppState.dashboardData) {
            showLoadingState();
            return;
        }

        const session = resolveCurrentSession(data.events, data.app_usage, raw.current_activity);
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
