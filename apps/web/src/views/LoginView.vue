<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const loading = ref(false);
const form = reactive({ tenantSlug: "platform", email: "", password: "" });

async function submit() {
  if (!form.email || !form.password) {
    ElMessage.warning("请填写邮箱和密码");
    return;
  }
  loading.value = true;
  try {
    await auth.login(form.tenantSlug, form.email, form.password);
    router.push("/kbs");
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 class="login-title">财税 RAG 管理台</h2>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="租户标识">
          <el-input v-model="form.tenantSlug" placeholder="platform" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="admin@finance-rag.local" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
}
.login-card {
  width: 380px;
}
.login-title {
  text-align: center;
  margin: 0 0 16px;
}
</style>
