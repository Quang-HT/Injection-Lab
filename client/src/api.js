const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error ?? "Request failed");
  }

  return response.json();
}

export function getBootstrap(userId) {
  return request(`/bootstrap?user_id=${encodeURIComponent(userId)}`);
}

export function executeConsoleQuery(query) {
  return request("/console/execute", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function getChallenge(userId, challengeId) {
  return request(`/challenges/${challengeId}?user_id=${encodeURIComponent(userId)}`);
}

export function runSimulation(userId, challengeId, inputs) {
  return request(`/challenges/${challengeId}/simulate`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, inputs }),
  });
}

export function resetSimulation(userId, challengeId) {
  return request(`/challenges/${challengeId}/reset`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}
