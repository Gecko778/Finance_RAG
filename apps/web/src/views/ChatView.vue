<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, API_BASE, getToken } from "@/api/client";

interface KB {
  id: string;
  name: string;
}
interface Citation {
  filename: string;
  doc_number: string;
  seq: number;
  effective_date: string | null;
  expire_date: string | null;
  source: string;
}

const kbs = ref<KB[]>([]);
const selectedKbs = ref<string[]>([]);
const query = ref("");
const answer = ref("");
const citations = ref<Citation[]>([]);
const streaming = ref(false);

onMounted(async () => {
  kbs.value = (await api.get("/api/v1/kbs")).data;
});

async function send() {
  if (!query.value.trim()) {
    ElMessage.warning("请输入问题");
    return;
  }
  answer.value = "";
  citations.value = [];
  streaming.value = true;
  try {
    const resp = await fetch(`${API_BASE}/api/v1/chat`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getToken()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query.value,
        kb_ids: selectedKbs.value.length ? selectedKbs.value : null,
      }),
    });
    if (!resp.ok || !resp.body) throw new Error((await resp.json()).detail ?? "请求失败");
    await consumeSSE(resp.body);
  } catch (e: any) {
    ElMessage.error(e.message ?? "对话失败");
  } finally {
    streaming.value = false;
  }
}

// 解析 SSE：event: citations|token|done
async function consumeSSE(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const block of events) {
      const evline = block.split("\n").find((l) => l.startsWith("event:"));
      const dataline = block.split("\n").find((l) => l.startsWith("data:"));
      if (!evline || !dataline) continue;
      const event = evline.slice(6).trim();
      const data = JSON.parse(dataline.slice(5).trim());
      if (event === "citations") citations.value = data.citations;
      else if (event === "token") answer.value += data.text;
    }
  }
}
</script>

<template>
  <h3>对话测试</h3>
  <el-alert
    type="info"
    :closable="false"
    show-icon
    title="回答仅供参考，正式对客户输出前请财税人员复核。"
    style="margin-bottom: 12px"
  />
  <el-form>
    <el-form-item label="知识库范围（不选=全部可见）">
      <el-select v-model="selectedKbs" multiple placeholder="全部" style="width: 100%">
        <el-option v-for="kb in kbs" :key="kb.id" :label="kb.name" :value="kb.id" />
      </el-select>
    </el-form-item>
    <el-form-item>
      <el-input
        v-model="query"
        type="textarea"
        :rows="2"
        placeholder="例如：小规模纳税人季度起征点是多少？"
        @keyup.enter.ctrl="send"
      />
    </el-form-item>
    <el-button type="primary" :loading="streaming" @click="send">发送（Ctrl+Enter）</el-button>
  </el-form>

  <el-card v-if="answer || streaming" style="margin-top: 16px">
    <template #header>回答</template>
    <div class="answer">{{ answer }}<span v-if="streaming" class="cursor">▍</span></div>
  </el-card>

  <div v-if="citations.length" style="margin-top: 16px">
    <h4>引用出处</h4>
    <el-card v-for="(c, i) in citations" :key="i" shadow="never" class="citation">
      <div class="cite-head">
        <el-tag size="small">[{{ i + 1 }}]</el-tag>
        <strong>{{ c.filename }}</strong>
        <span v-if="c.doc_number" class="muted">{{ c.doc_number }}</span>
      </div>
      <div class="muted">
        条款序号 {{ c.seq }}
        <span v-if="c.source"> · 来源 {{ c.source }}</span>
        <span v-if="c.effective_date"> · 生效 {{ c.effective_date }}</span>
        <span v-if="c.expire_date"> · 失效 {{ c.expire_date }}</span>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.answer {
  white-space: pre-wrap;
  line-height: 1.7;
}
.cursor {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.citation {
  margin-bottom: 8px;
}
.cite-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
