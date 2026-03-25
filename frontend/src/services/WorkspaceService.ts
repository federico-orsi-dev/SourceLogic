import apiClient from "./apiClient";

export type Workspace = {
  id: number;
  name: string;
  root_path: string;
  status: "IDLE" | "INDEXING" | "FAILED";
  created_at: string;
  last_indexed_at?: string | null;
};

export type WorkspaceCreatePayload = {
  name: string;
  root_path: string;
};

export type WorkspaceStatus = {
  status: Workspace["status"];
};

export const WorkspaceService = {
  async list(): Promise<Workspace[]> {
    const response = await apiClient.get<Workspace[]>("/workspaces");
    return response.data;
  },

  async create(payload: WorkspaceCreatePayload): Promise<Workspace> {
    const response = await apiClient.post<Workspace>("/workspaces", payload);
    return response.data;
  },

  async status(workspaceId: number): Promise<WorkspaceStatus> {
    const response = await apiClient.get<WorkspaceStatus>(
      `/workspaces/${workspaceId}/status`
    );
    return response.data;
  },

  async ingest(workspaceId: number): Promise<{ status: string }> {
    const response = await apiClient.post<{ status: string }>(
      `/workspaces/${workspaceId}/ingest`
    );
    return response.data;
  },
};
