const API_BASE = '/api';
const REQUEST_HEADERS = {
  'Content-Type': 'application/json',
};

async function request(url, options = {}, serviceName = 'Backend') {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${serviceName} returned ${response.status}.`);
  }
  return response;
}

export async function checkBackendHealth(signal) {
  await request(`${API_BASE}/health`, {
    signal,
  }, 'Health check');
}

export async function getRecommendation(workload) {
  const response = await request(`${API_BASE}/recommend`, {
    method: 'POST',
    headers: REQUEST_HEADERS,
    body: JSON.stringify({ workload }),
  }, 'Recommendation service');
  return response.json();
}

export async function simulateWorkload(workload, changes) {
  const response = await request(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: REQUEST_HEADERS,
    body: JSON.stringify({ workload, changes }),
  }, 'Scenario simulation service');
  return response.json();
}

export async function getRecommendationReport(workload) {
  const response = await request(`${API_BASE}/report`, {
    method: 'POST',
    headers: REQUEST_HEADERS,
    body: JSON.stringify({ workload }),
  }, 'Report service');
  return response.blob();
}
