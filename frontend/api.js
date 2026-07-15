// ==========================================
// ANTIGRAVITY API LAYER (api.js)
// ==========================================

const BASE_URL = "/api";

async function request(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        throw new Error(`API error calling ${url}: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchAnalytics(days = 7) {
    return request(`${BASE_URL}/analytics/?days=${days}`);
}

export async function fetchDashboard(days = 7) {
    return request(`${BASE_URL}/dashboard?days=${days}`);
}


export async function fetchAppUsage() {
    return request(`${BASE_URL}/app-usage/`);
}

export async function fetchScreenTime() {
    return request(`${BASE_URL}/screen-time/`);
}

export async function fetchExpenses() {
    return request(`${BASE_URL}/expenses/`);
}

export async function fetchEvents(limit = 20) {
    return request(`${BASE_URL}/events/?limit=${limit}`);
}

export async function fetchAlerts() {
    return request(`${BASE_URL}/alerts`);
}
