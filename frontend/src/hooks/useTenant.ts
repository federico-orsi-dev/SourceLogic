import { useEffect, useState } from "react";
import apiClient from "../services/apiClient";

export const useTenant = () => {
  const [tenant, setTenant] = useState<string>("tenant-a");

  useEffect(() => {
    apiClient.defaults.headers.common["X-Tenant-ID"] = tenant;
  }, [tenant]);

  return { tenant, setTenant };
};
