import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export function createApiClient(token) {
  const instance = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: {
      "Content-Type": "application/json",
    },
    timeout: 60000, // 60 second timeout for large responses
    maxContentLength: 50 * 1024 * 1024, // 50MB max response size
    maxBodyLength: 50 * 1024 * 1024, // 50MB max request size
  });

  instance.interceptors.request.use((config) => {
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      console.error("API Error:", error);
      
      // Handle 401 Unauthorized - token expired or invalid
      if (error.response?.status === 401) {
        // Clear token and redirect to login
        localStorage.removeItem("iot_admin_token");
        localStorage.removeItem("iot_user_data");
        // Only redirect if we're not already on the login page
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
      
      return Promise.reject(error);
    }
  );

  return instance;
}

export async function adminLogin(email, password) {
  const response = await axios.post(`${API_BASE_URL}/api/v1/admin/login`, {
    email,
    password,
  });
  return response.data;
}


