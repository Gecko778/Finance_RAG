<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { computed, onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const ADMIN_PATHS = ["/members", "/apikeys", "/audit"];
const activeMenu = computed(() => {
  const match = ["/chat", ...ADMIN_PATHS].find((p) => route.path.startsWith(p));
  return match ?? "/kbs";
});
const isAdmin = computed(() => auth.role === "admin");

onMounted(() => {
  auth.fetchMe().catch(() => {});
});

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-header class="header">
      <span class="title">财税 RAG 管理台</span>
      <div class="right">
        <el-tag size="small" type="info">角色：{{ auth.role || "…" }}</el-tag>
        <el-button link type="primary" @click="logout">退出登录</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px">
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/kbs">
            <el-icon><Files /></el-icon><span>知识库管理</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon><span>对话测试</span>
          </el-menu-item>
          <template v-if="isAdmin">
            <el-menu-item index="/members">
              <el-icon><User /></el-icon><span>成员管理</span>
            </el-menu-item>
            <el-menu-item index="/apikeys">
              <el-icon><Key /></el-icon><span>API Key</span>
            </el-menu-item>
            <el-menu-item index="/audit">
              <el-icon><Document /></el-icon><span>审计日志</span>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
