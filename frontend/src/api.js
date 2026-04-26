const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function exchangeAwsTokenForAppToken(idToken) {
  const response = await fetch(`${API_BASE_URL}/auth/aws/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!response.ok) {
    const detail = await safeError(response);
    throw new Error(detail || "Failed to exchange AWS token");
  }
  return response.json();
}

export async function fetchAuthMe(appToken) {
  return fetchWithBearer("/auth/me", appToken);
}

export async function fetchCatalog(appToken) {
  if (!appToken) {
    return fetchPublic("/catalog");
  }
  return fetchWithBearer("/catalog", appToken);
}

export async function fetchMyCatalog(appToken) {
  return fetchWithBearer("/catalog/me", appToken);
}

async function fetchWithBearer(path, appToken) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${appToken}` },
  });
  if (!response.ok) {
    const detail = await safeError(response);
    throw new Error(detail || `Request failed: ${path}`);
  }
  return response.json();
}

async function fetchPublic(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const detail = await safeError(response);
    throw new Error(detail || `Request failed: ${path}`);
  }
  return response.json();
}

async function safeError(response) {
  try {
    const payload = await response.json();
    return payload.detail || JSON.stringify(payload);
  } catch {
    return null;
  }
}
