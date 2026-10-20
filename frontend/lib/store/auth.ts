import { create } from "zustand";

import type { AuthToken, User } from "@/lib/api/types";
import * as api from "@/lib/api/endpoints";
import { ApiError, endSession, onSessionEnded } from "@/lib/api/client";
import {
  getAccessToken,
  hasSessionHint,
  setAccessToken,
  setSessionHint,
  takeLegacyRefreshToken,
} from "@/lib/api/token";

/**
 * idle — sessiya hali tiklanmoqda (UI skeleton ko'rsatadi, login'ga yo'naltirmaydi);
 * authenticated / anonymous — aniq holat.
 */
type AuthStatus = "idle" | "authenticated" | "anonymous";

type AuthState = {
  user: User | null;
  status: AuthStatus;
  loadMe: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const RETRY_MAX_MS = 30_000;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let retryAttempt = 0;

function clearRetry(): void {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  retryAttempt = 0;
}

export const useAuthStore = create<AuthState>((set, get) => {
  const startSession = async (token: AuthToken) => {
    setAccessToken(token.access_token, token.expires_in);
    setSessionHint(true);
    const user = await api.me();
    clearRetry();
    set({ user, status: "authenticated" });
  };

  // Server sessiyani rad etdi (refresh 401) yoki boshqa tabda chiqildi.
  onSessionEnded(() => {
    clearRetry();
    set({ user: null, status: "anonymous" });
  });

  return {
    user: null,
    status: "idle",

    /**
     * Sessiyani tiklaydi: access token bo'lmasa refresh cookie bilan jimgina yangilanadi
     * (apiFetch ichida), keyin profil olinadi. Faqat 401 — "chiqildi". Tarmoq yoki server
     * xatosida holat o'zgarmaydi: tiklanayotgan bo'lsa backoff bilan qayta uriniladi.
     */
    loadMe: async () => {
      if (!getAccessToken() && !hasSessionHint()) {
        clearRetry();
        set({ user: null, status: "anonymous" });
        return;
      }
      try {
        const user = await api.me();
        clearRetry();
        set({ user, status: "authenticated" });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          endSession();
          return;
        }
        if (get().status === "idle" && typeof window !== "undefined") {
          const delay = Math.min(1000 * 2 ** retryAttempt, RETRY_MAX_MS);
          retryAttempt += 1;
          if (retryTimer) clearTimeout(retryTimer);
          retryTimer = setTimeout(() => void get().loadMe(), delay);
        }
      }
    },

    login: async (email, password) => {
      await startSession(await api.login(email, password));
    },

    loginWithGoogle: async (credential) => {
      await startSession(await api.googleLogin(credential));
    },

    register: async (email, password, fullName) => {
      await api.register({ email, password, full_name: fullName });
      await startSession(await api.login(email, password));
    },

    logout: async () => {
      try {
        await api.logout();
      } catch {
        // Tarmoq xatosi bo'lsa ham lokal sessiya tozalanadi. Server sessiyasi o'z muddatigacha
        // ochiq qolishi mumkin, lekin hint yo'q — bu brauzer uni boshqa ishlatmaydi.
      }
      takeLegacyRefreshToken();
      endSession();
    },
  };
});
