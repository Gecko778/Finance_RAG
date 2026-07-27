import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "@/api/client";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue") },
    {
      path: "/",
      component: () => import("@/layouts/MainLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/kbs" },
        { path: "kbs", component: () => import("@/views/KnowledgeBasesView.vue") },
        {
          path: "kbs/:kbId/documents",
          component: () => import("@/views/DocumentsView.vue"),
          props: true,
        },
        { path: "chat", component: () => import("@/views/ChatView.vue") },
        { path: "members", component: () => import("@/views/MembersView.vue") },
        { path: "apikeys", component: () => import("@/views/ApiKeysView.vue") },
        { path: "audit", component: () => import("@/views/AuditView.vue") },
      ],
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !getToken()) return "/login";
  if (to.path === "/login" && getToken()) return "/kbs";
  return true;
});

export default router;
