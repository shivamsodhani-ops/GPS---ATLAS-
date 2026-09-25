import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("atlas_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = () => {};
export function registerUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      onUnauthorized();
    }
    return Promise.reject(err);
  }
);

export function apiErrorMessage(err, fallback = "Something went wrong") {
  const detail = err?.response?.data?.detail;

  // FastAPI/Pydantic validation errors (HTTP 422) return `detail` as an
  // array of {loc, msg, type} objects, not a string. Rendering that array
  // directly as a React child throws ("Objects are not valid as a React
  // child"), which crashes the whole page instead of showing an error
  // message -- that's what "page goes blank after clicking Sign in" was.
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => (typeof d === "string" ? d : d?.msg || JSON.stringify(d)))
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }

  return err?.message || fallback;
}
