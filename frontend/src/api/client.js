import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export function createApiClient(token) {
  const instance = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: {
      "Content-Type": "application/json",
    },
  });

  instance.interceptors.request.use((config) => {
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  return instance;
}

export async function adminLogin(email, password) {
  const response = await axios.post(`${API_BASE_URL}/api/v1/admin/login`, {
    email,
    password,
  });
  return response.data;
}


