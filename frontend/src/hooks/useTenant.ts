import { useEffect, useState } from "react";
import apiClient from "../services/apiClient";

const LS_API_KEY = "sourcelogic_api_key";

export const useTenant = () => {
  const [tenant, setTenant] = useState<string>("tenant-a");
  const [apiKey, setApiKeyState] = useState<string>(
    () => localStorage.getItem(LS_API_KEY) ?? ""
  );

  // Sync X-Tenant-ID for dev mode
  useEffect(() => {
    apiClient.defaults.headers.common["X-Tenant-ID"] = tenant;
  }, [tenant]);

  // Sync X-API-Key for api_key mode; persist to localStorage
  useEffect(() => {
    if (apiKey) {
      apiClient.defaults.headers.common["X-API-Key"] = apiKey;
      localStorage.setItem(LS_API_KEY, apiKey);
    } else {
      delete apiClient.defaults.headers.common["X-API-Key"];
      localStorage.removeItem(LS_API_KEY);
    }
  }, [apiKey]);

  const setApiKey = (key: string) => setApiKeyState(key);

  return { tenant, setTenant, apiKey, setApiKey };
};
