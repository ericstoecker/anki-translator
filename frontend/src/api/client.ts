const API_BASE = "/api";

let authToken: string | null = localStorage.getItem("token");

export function setToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem("token", token);
  } else {
    localStorage.removeItem("token");
  }
}

export function getToken(): string | null {
  return authToken;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401 && !path.startsWith("/auth/login")) {
      setToken(null);
      window.location.href = "/login";
    }
    throw new Error(error.detail || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => request<{ id: string; username: string; native_language: string | null }>("/auth/me"),

  updateMe: (native_language: string) =>
    request("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ native_language }),
    }),

  // OCR
  ocr: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ words: string[]; raw_text: string }>("/ocr", {
      method: "POST",
      body: form,
    });
  },

  // Translation
  translate: (data: {
    word: string;
    source_language: string;
    target_language: string;
    deck_id?: string;
    native_language?: string;
  }) =>
    request<{
      word: string;
      translation: string;
      native_translation?: string;
      part_of_speech?: string;
      context?: string;
    }>("/translate", { method: "POST", body: JSON.stringify(data) }),

  formatCard: (data: {
    word: string;
    source_language: string;
    target_language: string;
    deck_id: string;
    native_language?: string;
  }) =>
    request<{
      note_type_id: string;
      fields: Record<string, string>;
      translation: Record<string, string>;
    }>("/translate/format-card", { method: "POST", body: JSON.stringify(data) }),

  // Cards
  listCards: (params?: { deck_id?: string; status?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return request<Array<{
      id: string;
      fields: Record<string, string>;
      status: string;
      source_word: string | null;
      created_at: string;
    }>>(`/cards${query ? `?${query}` : ""}`);
  },

  createCard: (data: {
    deck_id: string;
    note_type_id: string;
    fields: Record<string, string>;
    tags?: string;
    source_word?: string;
    source_language?: string;
    target_language?: string;
  }) =>
    request<{ id: string }>("/cards", { method: "POST", body: JSON.stringify(data) }),

  acceptCard: (cardId: string) =>
    request(`/cards/${cardId}/accept`, { method: "POST" }),

  deleteCard: (cardId: string) =>
    request(`/cards/${cardId}`, { method: "DELETE" }),

  // Decks
  listDecks: () =>
    request<Array<{
      id: string;
      name: string;
      source_language: string | null;
      target_language: string | null;
    }>>("/decks"),

  updateDeck: (deckId: string, data: { source_language?: string; target_language?: string }) =>
    request(`/decks/${deckId}`, { method: "PATCH", body: JSON.stringify(data) }),

  getNoteTypes: (deckId: string) =>
    request<Array<{
      id: string;
      name: string;
      fields: Array<{ name: string; ordinal: number }>;
    }>>(`/decks/${deckId}/note-types`),

  // Duplicates
  checkDuplicate: (data: { word: string; deck_id: string; source_language: string }) =>
    request<{ is_duplicate: boolean; duplicate_of_id?: string; explanation?: string }>(
      "/duplicates/check",
      { method: "POST", body: JSON.stringify(data) }
    ),
};
