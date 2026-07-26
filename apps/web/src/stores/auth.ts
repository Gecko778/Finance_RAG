import { defineStore } from "pinia";
import { ref } from "vue";
import { api, clearToken, getToken, setToken } from "@/api/client";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getToken());
  const role = ref<string>("");

  async function login(tenantSlug: string, email: string, password: string): Promise<void> {
    const { data } = await api.post("/api/v1/auth/login", {
      tenant_slug: tenantSlug,
      email,
      password,
    });
    setToken(data.access_token);
    token.value = data.access_token;
    role.value = data.role;
  }

  async function fetchMe(): Promise<void> {
    const { data } = await api.get("/api/v1/auth/me");
    role.value = data.role;
  }

  function logout(): void {
    clearToken();
    token.value = null;
    role.value = "";
  }

  return { token, role, login, fetchMe, logout };
});
