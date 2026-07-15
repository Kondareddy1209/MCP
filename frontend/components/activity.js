// ==========================================
// LIVE ACTIVITY COMPONENT (activity.js)
// ==========================================

function getAppName(log) {
    const processName = (log.app_name || "").toLowerCase().trim();
    if (processName.includes("code.exe") || processName.includes("code")) return "VS Code";
    if (processName.includes("chrome")) return "Chrome";
    if (processName.includes("firefox")) return "Firefox";
    if (processName === "cursor.exe" || processName === "cursor") return "Cursor";
    if (processName.includes("cmd.exe") || processName.includes("powershell.exe") || processName.includes("terminal")) return "Terminal";
    if (processName.includes("youtube")) return "YouTube";
    if (processName.includes("instagram")) return "Instagram";
    if (processName.includes("netflix")) return "Netflix";
    if (processName.includes("spotify")) return "Spotify";
    if (processName.includes("discord")) return "Discord";
    if (processName.includes("slack")) return "Slack";
    return "Unknown";
}

export function renderLiveActivity(events) {
    const appNameEl = document.getElementById("live-app-name");
    const windowTitleEl = document.getElementById("live-window-title");
    const pulseEl = document.getElementById("activity-pulse-el");
    const badgeEl = document.getElementById("live-state-badge");

    if (!events || events.length === 0) {
        appNameEl.innerText = "No active daemon connection";
        windowTitleEl.innerText = "Start scripts/desktop_tracker.py to track active window details.";
        pulseEl.className = "activity-pulse pulse-orange";
        badgeEl.className = "status-badge badge-neutral";
        badgeEl.innerText = "OFFLINE";
        return;
    }

    // Sort by timestamp descending and fetch newest
    const latestEvent = events[0];
    const { event_type, app_name, window_title } = latestEvent;

    // Check if idle or session finished
    if (event_type === "IDLE_START" || event_type === "SESSION_END") {
        appNameEl.innerText = "System Idle / Standby";
        windowTitleEl.innerText = "No user keyboard or mouse input detected recently.";
        pulseEl.className = "activity-pulse pulse-orange";
        badgeEl.className = "status-badge badge-neutral";
        badgeEl.innerText = "IDLE";
        return;
    }

    // Determine resolved active app (STRICT APP IDENTITY MODE)
    const processName = app_name;
    let activeApp = "Background";
    if (!processName) {
        activeApp = "Idle";
    } else {
        const resolvedApp = getAppName(latestEvent);
        activeApp = resolvedApp === "Unknown" ? "Background" : resolvedApp;
    }

    const activeTitle = window_title || "Active Foreground Window";

    appNameEl.innerText = activeApp;
    windowTitleEl.innerText = activeTitle;

    // Determine state classification based on rules
    const classRules = {
        "productive": { pulse: "pulse-green", badge: "badge-productive", text: "Productive" },
        "distracting": { pulse: "pulse-rose", badge: "badge-distracting", text: "Distracting" },
        "neutral": { pulse: "pulse-blue", badge: "badge-neutral", text: "Neutral" }
    };

    const rules = [
        { regex: /leetcode|github|stackoverflow|notion|docs\./i, classification: "productive" },
        { regex: /chatgpt|claude|gemini|copilot/i, classification: "productive" },
        { regex: /vs code|vscode|cursor|pycharm|terminal|powershell|cmd/i, classification: "productive" },
        { regex: /youtube|instagram|facebook|twitter|reddit|netflix|spotify/i, classification: "distracting" }
    ];
    
    let classification = "neutral";
    const combinedStr = `${activeApp} ${activeTitle}`.toLowerCase();
    for (const r of rules) {
        if (r.regex.test(combinedStr)) {
            classification = r.classification;
            break;
        }
    }

    const state = classRules[classification];
    pulseEl.className = `activity-pulse ${state.pulse}`;
    badgeEl.className = `status-badge ${state.badge}`;
    badgeEl.innerText = state.text;
}

export function renderRawEventsStream(events) {
    const container = document.getElementById("events-container");
    container.innerHTML = "";

    if (!events || events.length === 0) {
        container.innerHTML = `<div class="loading-placeholder">No raw database events captured yet.</div>`;
        return;
    }

    // Take top 15 logs
    events.slice(0, 15).forEach(e => {
        const row = document.createElement("div");
        row.className = "event-row-item";

        const rawTime = new Date(e.timestamp);
        const timeStr = rawTime.toLocaleTimeString();

        // Map process name representation
        const cleanProcess = getAppName(e);

        row.innerHTML = `
            <span class="event-time-badge">[${timeStr}]</span>
            <span class="event-type-badge">${e.event_type}</span>
            <span class="event-app-badge">${cleanProcess === "Unknown" ? "Background" : cleanProcess}</span>
            <span class="event-title-badge">${e.window_title ? e.window_title.substring(0, 45) + '...' : "-"}</span>
        `;
        container.appendChild(row);
    });
}
