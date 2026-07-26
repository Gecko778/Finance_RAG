<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

interface KB {
  id: string;
  name: string;
  description: string;
  is_public: boolean;
  created_at: string;
}

const auth = useAuthStore();
const router = useRouter();
const kbs = ref<KB[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const form = reactive({ name: "", description: "" });

async function load() {
  loading.value = true;
  try {
    kbs.value = (await api.get("/api/v1/kbs")).data;
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.name.trim()) {
    ElMessage.warning("请填写知识库名称");
    return;
  }
  try {
    await api.post("/api/v1/kbs", { name: form.name, description: form.description });
    ElMessage.success("已创建");
    dialogVisible.value = false;
    form.name = "";
    form.description = "";
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "创建失败");
  }
}

async function remove(kb: KB) {
  await ElMessageBox.confirm(`确认删除知识库「${kb.name}」？`, "提示", { type: "warning" });
  try {
    await api.delete(`/api/v1/kbs/${kb.id}`);
    ElMessage.success("已删除");
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "删除失败");
  }
}

function openDocs(kb: KB) {
  router.push(`/kbs/${kb.id}/documents`);
}

onMounted(load);
</script>

<template>
  <div class="toolbar">
    <h3>知识库管理</h3>
    <el-button type="primary" @click="dialogVisible = true">新建知识库</el-button>
  </div>

  <el-table v-loading="loading" :data="kbs" style="width: 100%">
    <el-table-column prop="name" label="名称" min-width="180">
      <template #default="{ row }">
        <el-link type="primary" @click="openDocs(row)">{{ row.name }}</el-link>
        <el-tag v-if="row.is_public" size="small" type="success" style="margin-left: 8px">
          公共
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="description" label="描述" min-width="220" />
    <el-table-column label="操作" width="180">
      <template #default="{ row }">
        <el-button link type="primary" @click="openDocs(row)">文档</el-button>
        <el-button
          v-if="auth.role === 'admin' && !row.is_public"
          link
          type="danger"
          @click="remove(row)"
        >
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" title="新建知识库" width="440px">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
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
</style>
