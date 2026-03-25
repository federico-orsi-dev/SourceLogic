import apiClient from "./apiClient";

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
  sources?: string[] | null;
  timestamp: string;
};

export const SessionService = {
  async create(workspaceId: number, title?: string): Promise<SessionCreateResponse> {
    const response = await apiClient.post<SessionCreateResponse>(
      `/workspaces/${workspaceId}/sessions`,
      { title }
    );
    return response.data;
  },

  async history(sessionId: number): Promise<Message[]> {
    const response = await apiClient.get<Message[]>(
      `/sessions/${sessionId}/history`
    );
    return response.data;
  },
};
