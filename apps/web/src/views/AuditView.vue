<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/api/client";

interface AuditLog {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

const logs = ref<AuditLog[]>([]);
const loading = ref(false);
const actionFilter = ref("");

async function load() {
  loading.value = true;
  try {
    const params = actionFilter.value ? { action: actionFilter.value } : {};
    logs.value = (await api.get("/api/v1/audit", { params })).data;
  } finally {
    loading.value = false;
  }
}

function fmtDetail(d: Record<string, unknown>): string {
  return Object.keys(d).length ? JSON.stringify(d) : "—";
}

onMounted(load);
</script>

<template>
  <div class="toolbar">
    <h3>审计日志</h3>
    <div>
      <el-input
        v-model="actionFilter"
        placeholder="按操作过滤，如 document.upload"
        style="width: 240px; margin-right: 8px"
        clearable
        @keyup.enter="load"
        @clear="load"
      />
      <el-button type="primary" @click="load">查询</el-button>
    </div>
  </div>

  <el-table v-loading="loading" :data="logs" style="width: 100%">
    <el-table-column prop="created_at" label="时间" width="200" />
    <el-table-column prop="actor_type" label="操作者" width="100" />
    <el-table-column prop="action" label="操作" min-width="160" />
    <el-table-column prop="resource_type" label="资源" width="140" />
    <el-table-column label="详情" min-width="200">
      <template #default="{ row }">{{ fmtDetail(row.detail) }}</template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
