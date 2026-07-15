// ==========================================
// VISUALIZATION CHARTS COMPONENT (charts.js)
// ==========================================

let appChartInstance = null;
let screenChartInstance = null;

export function renderCharts(appUsage, screenTime) {
    renderAppUsagePie(appUsage);
    renderScreenTimeLine(screenTime);
}

function renderAppUsagePie(appUsage) {
    const canvas = document.getElementById("appUsageChart");
    if (!canvas) return;
    
    // ✅ ALWAYS destroy existing chart from DOM-level registry first
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    const ctx = canvas.getContext("2d");

    // Handle empty data — render clean placeholder, never leave ghost data
    if (!appUsage || appUsage.length === 0) {
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['No Active App Logs'],
                datasets: [{ data: [1], backgroundColor: ['rgba(255,255,255,0.05)'], borderWidth: 1, borderColor: '#2a2d3a' }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#8e94a9', font: { family: 'Outfit', size: 11 } } },
                    tooltip: { enabled: false }
                },
                cutout: '70%'
            }
        });
        return;
    }

    // Group durations by app
    const appDurations = {};
    appUsage.forEach(item => {
        appDurations[item.app_name] = (appDurations[item.app_name] || 0) + item.duration_seconds;
    });

    // Sort apps by duration descending
    const sortedApps = Object.entries(appDurations)
        .sort((a, b) => b[1] - a[1]);

    let labels = sortedApps.map(x => x[0]);
    let data = sortedApps.map(x => (x[1] / 3600).toFixed(2)); // convert to hours

    // Limit to top 5 and aggregate others
    if (labels.length > 5) {
        const topLabels = labels.slice(0, 5);
        const topData = data.slice(0, 5).map(Number);
        const otherSum = data.slice(5).map(Number).reduce((sum, val) => sum + val, 0);

        topLabels.push("Others");
        topData.push(Number(otherSum.toFixed(2)));

        labels = topLabels;
        data = topData;
    }

    appChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#00e676', '#29b6f6', '#9d4edd', '#ff9100', '#ff1744', '#f72585'
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
                    labels: { color: '#f1f3f9', font: { family: 'Outfit', size: 11 } }
                },
                tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.raw} hrs` } }
            },
            cutout: '70%'
        }
    });
}

function renderScreenTimeLine(screenTime) {
    const canvas = document.getElementById("screenTimeChart");
    if (!canvas) return;

    // ✅ ALWAYS destroy existing chart from DOM-level registry first
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    const ctx = canvas.getContext("2d");

    // Handle empty data - render clean empty line chart
    if (!screenTime || screenTime.length === 0) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['No Data'],
                datasets: [
                    { label: 'Laptop', data: [0], borderColor: 'rgba(41,182,246,0.2)', borderWidth: 1, fill: false },
                    { label: 'Mobile', data: [0], borderColor: 'rgba(157,78,221,0.2)', borderWidth: 1, fill: false }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#8e94a9', font: { family: 'Outfit' } } } },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#8e94a9' }, min: 0, max: 1 },
                    x: { grid: { display: false }, ticks: { color: '#8e94a9' } }
                }
            }
        });
        return;
    }

    // Group screen time by date and device
    const dateGroups = {}; // { 'YYYY-MM-DD': { laptop: X, mobile: Y } }
    screenTime.forEach(record => {
        const dateStr = record.date;
        dateGroups[dateStr] = dateGroups[dateStr] || { laptop: 0, mobile: 0 };
        dateGroups[dateStr][record.device] = record.total_time_seconds / 3600.0; // convert to hours
    });

    // Sort dates chronologically
    const sortedDates = Object.keys(dateGroups).sort();
    
    // Take the last 7 entries for cleaner line charts
    const displayDates = sortedDates.slice(-7);
    const laptopData = displayDates.map(d => dateGroups[d].laptop.toFixed(1));
    const mobileData = displayDates.map(d => dateGroups[d].mobile.toFixed(1));

    screenChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayDates.map(d => formatDateLabel(d)),
            datasets: [
                {
                    label: 'Laptop',
                    data: laptopData,
                    borderColor: '#29b6f6',
                    backgroundColor: 'rgba(41, 182, 246, 0.05)',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Mobile',
                    data: mobileData,
                    borderColor: '#9d4edd',
                    backgroundColor: 'rgba(157, 78, 221, 0.05)',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#f1f3f9', font: { family: 'Outfit' } } }
            },
            scales: {
                y: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: '#8e94a9' } },
                x: { grid: { display: false }, ticks: { color: '#8e94a9' } }
            }
        }
    });
}

function formatDateLabel(dateStr) {
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch (e) {
        return dateStr;
    }
}
