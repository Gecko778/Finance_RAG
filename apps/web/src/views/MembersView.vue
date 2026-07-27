<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "@/api/client";

interface Member {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const members = ref<Member[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const form = reactive({ email: "", display_name: "", role: "member", password: "" });

async function load() {
  loading.value = true;
  try {
    members.value = (await api.get("/api/v1/members")).data;
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!form.email || form.password.length < 6) {
    ElMessage.warning("请填写邮箱和至少 6 位密码");
    return;
  }
  try {
    await api.post("/api/v1/members", { ...form });
    ElMessage.success("已创建");
    dialogVisible.value = false;
    Object.assign(form, { email: "", display_name: "", role: "member", password: "" });
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "创建失败");
  }
}

async function toggle(m: Member) {
  try {
    await api.post(`/api/v1/members/${m.id}/status`, { is_active: !m.is_active });
    ElMessage.success(m.is_active ? "已停用" : "已启用");
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail ?? "操作失败");
  }
}

onMounted(load);
</script>

<template>
  <div class="toolbar">
    <h3>成员管理</h3>
    <el-button type="primary" @click="dialogVisible = true">新建成员</el-button>
  </div>

  <el-table v-loading="loading" :data="members" style="width: 100%">
    <el-table-column prop="email" label="邮箱" min-width="200" />
    <el-table-column prop="display_name" label="姓名" min-width="120" />
    <el-table-column label="角色" width="100">
      <template #default="{ row }">
        <el-tag :type="row.role === 'admin' ? 'warning' : 'info'">{{ row.role }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.is_active ? 'success' : 'danger'">
          {{ row.is_active ? "启用" : "停用" }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }">
        <el-button link :type="row.is_active ? 'danger' : 'primary'" @click="toggle(row)">
          {{ row.is_active ? "停用" : "启用" }}
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" title="新建成员" width="440px">
    <el-form label-position="top">
      <el-form-item label="邮箱">
        <el-input v-model="form.email" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.display_name" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role" style="width: 100%">
          <el-option label="成员 (member)" value="member" />
          <el-option label="管理员 (admin)" value="admin" />
        </el-select>
      </el-form-item>
      <el-form-item label="初始密码（≥6 位）">
        <el-input v-model="form.password" type="password" show-password />
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
