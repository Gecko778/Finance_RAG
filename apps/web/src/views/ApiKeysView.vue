<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api } from "@/api/client";

interface ApiKey {
  id: string;
  name: string;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

const keys = ref<ApiKey[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const form = reactive({ name: "", scopes: ["retrieval"] as string[] });
const newKey = ref<string>("");

async function load() {
  loading.value = true;
  try {
    keys.value = (await api.get("/api/v1/apikeys")).data;
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.name.trim() || form.scopes.length === 0) {
    ElMessage.warning("请填写名称并至少选择一个权限");
    return;
  }
  try {
    const { data } = await api.post("/api/v1/apikeys", { ...form });
    newKey.value = data.api_key;
    dialogVisible.value = false;
    form.name = "";
    form.scopes = ["retrieval"];
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "创建失败");
  }
}

async function revoke(k: ApiKey) {
  await ElMessageBox.confirm(`确认吊销「${k.name}」？吊销后立即失效。`, "提示", { type: "warning" });
  await api.delete(`/api/v1/apikeys/${k.id}`);
  ElMessage.success("已吊销");
  load();
}
onMounted(load);
</script>

<template>
  <div class="toolbar">
    <h3>API Key 管理</h3>
    <el-button type="primary" @click="dialogVisible = true">新建 API Key</el-button>
  </div>

  <el-alert
    v-if="newKey"
    type="success"
    :closable="true"
    show-icon
    title="新 API Key（仅此一次显示，请立即复制保存）"
    style="margin-bottom: 12px"
    @close="newKey = ''"
  >
    <code class="newkey">{{ newKey }}</code>
  </el-alert>

  <el-table v-loading="loading" :data="keys" style="width: 100%">
    <el-table-column prop="name" label="名称" min-width="160" />
    <el-table-column label="权限" min-width="160">
      <template #default="{ row }">
        <el-tag v-for="s in row.scopes" :key="s" size="small" style="margin-right: 4px">
          {{ s }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.revoked_at ? 'danger' : 'success'">
          {{ row.revoked_at ? "已吊销" : "有效" }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="last_used_at" label="最后使用" width="180" />
    <el-table-column label="操作" width="90">
      <template #default="{ row }">
        <el-button v-if="!row.revoked_at" link type="danger" @click="revoke(row)">吊销</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" title="新建 API Key" width="440px">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="如 小智机器人" />
      </el-form-item>
      <el-form-item label="权限范围">
        <el-checkbox-group v-model="form.scopes">
          <el-checkbox value="retrieval">检索 (retrieval)</el-checkbox>
          <el-checkbox value="chat">问答 (chat)</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.newkey {
  font-family: monospace;
  word-break: break-all;
}
</style>
