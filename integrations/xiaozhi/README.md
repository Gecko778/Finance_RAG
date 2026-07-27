# 小智机器人接入财税 RAG

让小智语音助手能从本项目财税知识库检索作答。

## 安装

1. 复制插件到小智服务器：
   ```
   cp integrations/xiaozhi/search_from_finance_rag.py \
      <xiaozhi-esp32-server>/main/xiaozhi-server/plugins_func/functions/
   ```

2. 在本平台后台「API Key 管理」创建一个 **scope 含 `retrieval`** 的 API Key（明文仅显示一次）。

3. 在小智 `config.yaml` 增加插件配置：
   ```yaml
   plugins:
     search_from_finance_rag:
       base_url: "http://<finance-rag-api 地址>:8000"
       api_key: "fr_xxxxxxxx"        # 上一步创建的 retrieval API Key
       kb_ids: []                     # 可选：限定知识库 id 列表，空=全部可见
       top_k: 5
   ```

4. 把 `search_from_finance_rag` 加入意图函数列表：
   ```yaml
   Intent:
     function_call:
       functions:
         - search_from_finance_rag
   ```

5. 重启小智 server。对小智提财税问题（如"小规模纳税人季度起征点是多少"），
   它会调用本插件检索知识库并据此作答。

## 说明

- 认证走 `X-API-Key` 头（本平台 API Key 机制）。
- 插件把 `/api/v1/retrieval` 返回的片段组织成带 `[序号] 来源：文号 文件名` 的引用文本，
  交由小智的 LLM 依据作答（`Action.REQLLM`）。
- 鉴权失败(401)/无权限(403)/网络异常均返回友好话术，不中断对话。

## 端到端联调（待 key）

需先：本平台配置有效 SiliconFlow key 并把政策灌库到 ready；创建 retrieval API Key；
小智 server 按上述配置启动。届时语音问答可端到端跑通。
