<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, API_BASE, getToken } from "@/api/client";

const props = defineProps<{ kbId: string }>();
const router = useRouter();

interface Doc {
  id: string;
  filename: string;
  status: string;
  error_msg: string;
  doc_number: string;
  effective_date: string | null;
  expire_date: string | null;
  source: string;
}

const docs = ref<Doc[]>([]);
const loading = ref(false);
const uploadVisible = ref(false);
const uploading = ref(false);
const file = ref<File | null>(null);
const meta = reactive({ doc_number: "", effective_date: "", expire_date: "", source: "" });
let timer: number | undefined;

const STATUS: Record<string, { text: string; type: string }> = {
  uploaded: { text: "待处理", type: "info" },
  parsing: { text: "解析中", type: "warning" },
  chunking: { text: "切块中", type: "warning" },
  embedding: { text: "向量化中", type: "warning" },
  ready: { text: "就绪", type: "success" },
  failed: { text: "失败", type: "danger" },
};

async function load() {
  loading.value = true;
  try {
    docs.value = (await api.get(`/api/v1/kbs/${props.kbId}/documents`)).data;
  } finally {
    loading.value = false;
  }
  // 有处理中的文档则轮询刷新
  const pending = docs.value.some((d) => !["ready", "failed"].includes(d.status));
  if (pending && !timer) timer = window.setInterval(load, 3000);
  if (!pending && timer) {
    clearInterval(timer);
    timer = undefined;
  }
}

function onFileChange(uploadFile: { raw: File }) {
  file.value = uploadFile.raw;
}

async function submitUpload() {
  if (!file.value) {
    ElMessage.warning("请选择文件");
    return;
  }
  const fd = new FormData();
  fd.append("file", file.value);
  for (const [k, v] of Object.entries(meta)) if (v) fd.append(k, v);
  uploading.value = true;
  try {
    // 用原生 fetch 传 multipart（axios 也可，这里保持简单）
    const resp = await fetch(`${API_BASE}/api/v1/kbs/${props.kbId}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!resp.ok) throw new Error((await resp.json()).detail ?? "上传失败");
    ElMessage.success("已上传，后台处理中");
    uploadVisible.value = false;
    file.value = null;
    Object.assign(meta, { doc_number: "", effective_date: "", expire_date: "", source: "" });
    load();
  } catch (e: any) {
    ElMessage.error(e.message ?? "上传失败");
  } finally {
    uploading.value = false;
  }
}

async function remove(doc: Doc) {
  await ElMessageBox.confirm(`确认删除「${doc.filename}」？`, "提示", { type: "warning" });
  await api.delete(`/api/v1/documents/${doc.id}`);
  ElMessage.success("已删除");
  load();
}

onMounted(load);
onUnmounted(() => timer && clearInterval(timer));
</script>

<template>
  <div class="toolbar">
    <div>
      <el-button link @click="router.push('/kbs')">← 返回知识库</el-button>
      <h3 style="display: inline; margin-left: 8px">文档管理</h3>
    </div>
    <el-button type="primary" @click="uploadVisible = true">上传文档</el-button>
  </div>

  <el-table v-loading="loading" :data="docs" style="width: 100%">
    <el-table-column prop="filename" label="文件名" min-width="200" />
    <el-table-column label="状态" width="110">
      <template #default="{ row }">
        <el-tooltip v-if="row.status === 'failed'" :content="row.error_msg">
          <el-tag :type="STATUS[row.status]?.type">{{ STATUS[row.status]?.text }}</el-tag>
        </el-tooltip>
        <el-tag v-else :type="STATUS[row.status]?.type">{{ STATUS[row.status]?.text }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="doc_number" label="文号" min-width="140" />
    <el-table-column prop="effective_date" label="生效日期" width="120" />
    <el-table-column prop="expire_date" label="失效日期" width="120" />
    <el-table-column prop="source" label="来源" min-width="120" />
    <el-table-column label="操作" width="90">
      <template #default="{ row }">
        <el-button link type="danger" @click="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="uploadVisible" title="上传文档" width="480px">
    <el-form label-position="top">
      <el-form-item label="文件（PDF / DOCX / TXT / MD）">
        <el-upload :auto-upload="false" :limit="1" :on-change="onFileChange" :show-file-list="true">
          <el-button>选择文件</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="文号">
        <el-input v-model="meta.doc_number" placeholder="如 财税〔2026〕1号" />
      </el-form-item>
      <el-form-item label="生效日期">
        <el-date-picker v-model="meta.effective_date" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="失效日期（失效政策默认不被检索）">
        <el-date-picker v-model="meta.expire_date" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="来源机关">
        <el-input v-model="meta.source" placeholder="如 国家税务总局" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="uploadVisible = false">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
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
