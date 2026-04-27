import apiClient from "./apiClient";
import type { Citation } from "../hooks/useStreaming";

export type Session = {
  id: number;
  workspaceId: number;
  title: string;
  createdAt: string;
};

export type SessionCreateResponse = {
  session_id: number;
};

export type Message = {
  id: number;
  session_id: number;
  role: "user" | "bot";
  content: string;
  sources?: { citations?: Citation[] } | Citation[] | null;
  timestamp: string;
};

// Shape returned by GET /workspaces/{id}/sessions (snake_case from FastAPI)
type SessionRead = {
  id: number;
  workspace_id: number;
  title: string;
  created_at: string;
};

export const SessionService = {
  async create(workspaceId: number, title?: string): Promise<SessionCreateResponse> {
    const response = await apiClient.post<SessionCreateResponse>(
      `/workspaces/${workspaceId}/sessions`,
      { title }
    );
    return response.data;
  },

  async list(workspaceId: number): Promise<Session[]> {
    const response = await apiClient.get<SessionRead[]>(
      `/workspaces/${workspaceId}/sessions`
    );
    return response.data.map((s) => ({
      id: s.id,
      workspaceId: s.workspace_id,
      title: s.title,
      createdAt: s.created_at,
    }));
  },

  async history(sessionId: number, limit = 100, offset = 0): Promise<Message[]> {
    const response = await apiClient.get<Message[]>(
      `/sessions/${sessionId}/history?limit=${limit}&offset=${offset}`
    );
    return response.data;
  },

  async delete(sessionId: number): Promise<void> {
    await apiClient.delete(`/sessions/${sessionId}`);
  },
};
