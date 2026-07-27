# K8s 部署（M8）

多租户共享部署形态。有状态依赖（PG/Redis/Qdrant/MinIO）默认集群内 StatefulSet；
生产可改为托管服务（删 data-services.yaml 对应块，把连接地址指向托管实例）。

## 前置

- 一个 K8s 集群（生产集群，或本地 kind/minikube）
- Ingress 控制器（清单用 `ingressClassName: nginx`，需先装 ingress-nginx）
- 镜像仓库（集群能拉取）；或本地 kind 用 `kind load docker-image`

## 步骤

```bash
# 1. 构建三镜像（仓库根目录）
docker build -f apps/api/Dockerfile    -t <registry>/finance-rag-api:<tag> .
docker build -f apps/worker/Dockerfile -t <registry>/finance-rag-worker:<tag> .
docker build -f apps/web/Dockerfile    -t <registry>/finance-rag-web:<tag> apps/web
# 推送（或 kind load）；并把 app.yaml 里的 image 改成你的 <registry>/...:<tag>

# 2. 准备密钥（勿提交）
cp k8s/secret.example.yaml k8s/secret.yaml
#   填入真实 POSTGRES_PASSWORD / JWT_SECRET / SILICONFLOW_API_KEY / DEEPSEEK_API_KEY / MinIO 凭据
#   并把 kustomization.yaml 的 secret.example.yaml 换成 secret.yaml
#   生产建议 Sealed Secrets / External Secrets，勿用明文 Secret

# 3. 部署
kubectl apply -k k8s/

# 4. 等依赖就绪后跑迁移+种子（Job）
kubectl -n finance-rag wait --for=condition=ready pod -l app=postgres --timeout=180s
kubectl -n finance-rag apply -f k8s/app.yaml   # db-migrate Job 随之运行
kubectl -n finance-rag logs job/db-migrate

# 5. 验证
kubectl -n finance-rag get pods
kubectl -n finance-rag port-forward svc/api 8000:8000   # 然后 curl /healthz
```

## 校验（无集群时）

```bash
kubectl kustomize k8s/            # 结构/语法校验（本仓库已验证：渲染 18 个资源）
```
完整 schema 校验与运行时验证需连接集群。

## 生产加固 TODO

- 应用角色密码：M1 迁移写死 `finance_rag_app_dev` → 改为可配置或部署后 `ALTER ROLE`
- 资源 requests/limits、HptaOScaler、PodDisruptionBudget、NetworkPolicy
- 有状态服务改托管（RDS/ElastiCache/托管 Qdrant/对象存储）
- TLS（cert-manager）、私有镜像仓库 imagePullSecrets
- 密钥改 Sealed/External Secrets
