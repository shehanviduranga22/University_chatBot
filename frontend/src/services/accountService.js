const API = "http://127.0.0.1:5000";

async function request(path, payload) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Account request failed.");
  }

  return data.account;
}

export function createStudentAccount({ name, email, password }) {
  return request("/api/auth/register", { name, email, password });
}

export function loginStudent({ email, password }) {
  return request("/api/auth/login", { email, password });
}
