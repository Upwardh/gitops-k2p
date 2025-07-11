# 환경 구축 가이드

## 전체 아키텍처

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Development   │    │     Staging      │    │   Production    │
│   (monitoring-  │    │   (monitoring-   │    │   (monitoring)  │
│      dev)       │    │    staging)      │    │                 │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│ develop branch  │    │  main branch     │    │ manual deploy   │
│ Auto-sync: ON   │    │ Auto-sync: ON    │    │ Auto-sync: OFF  │
│ Self-heal: ON   │    │ Self-heal: ON    │    │ Self-heal: OFF  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │     ArgoCD Controller   │
                    │   (argocd namespace)    │
                    └─────────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │    GitOps Repository    │
                    │  github.com/owner/repo  │
                    └─────────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │   GitHub Actions CI     │
                    │  (build & push & update)│
                    └─────────────────────────┘
```

## 1. 개발 환경 (Development)

### 네임스페이스: `monitoring-dev`

### ArgoCD Application 설정:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: lb-exporter-dev
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/Upwardh/gitops-k2p
    targetRevision: develop  # develop 브랜치 추적
    path: k8s-manifests/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
  revisionHistoryLimit: 10
```

### Kustomization 설정 (`k8s-manifests/overlays/dev/kustomization.yaml`):
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: monitoring-dev

resources:
  - ../../base

namePrefix: dev-

commonLabels:
  environment: dev

images:
  - name: registry.cloud.kt.com/nqtv7l5h/lb-exporter:latest
    newTag: develop-<commit-sha>  # GitHub Actions가 자동 업데이트

replicas:
  - name: lb-exporter
    count: 1

patches:
  - target:
      kind: Deployment
      name: lb-exporter
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/cpu
        value: 50m
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/memory
        value: 64Mi
```

### 배포 플로우:
1. `develop` 브랜치에 코드 커밋
2. GitHub Actions 트리거 (CI 파이프라인)
3. Docker 이미지 빌드 및 레지스트리 푸시
4. GitOps 레포지토리 자동 업데이트 (`newTag` 변경)
5. ArgoCD 자동 감지 (30초 주기)
6. `monitoring-dev` 네임스페이스에 자동 배포

## 2. 스테이징 환경 (Staging)

### 네임스페이스: `monitoring-staging`

### ArgoCD Application 설정:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: lb-exporter-staging
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/Upwardh/gitops-k2p
    targetRevision: main  # main 브랜치 추적
    path: k8s-manifests/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring-staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
  revisionHistoryLimit: 10
```

### Kustomization 설정 (`k8s-manifests/overlays/staging/kustomization.yaml`):
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: monitoring-staging

resources:
  - ../../base

namePrefix: staging-

commonLabels:
  environment: staging

images:
  - name: registry.cloud.kt.com/nqtv7l5h/lb-exporter:latest
    newTag: main-<commit-sha>  # GitHub Actions가 자동 업데이트

replicas:
  - name: lb-exporter
    count: 1

patches:
  - target:
      kind: Deployment
      name: lb-exporter
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/cpu
        value: 100m
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/memory
        value: 128Mi
```

### 배포 플로우:
1. `develop` → `main` 브랜치 머지
2. GitHub Actions 트리거 (CI 파이프라인)
3. Docker 이미지 빌드 및 레지스트리 푸시
4. GitOps 레포지토리 자동 업데이트 (`newTag` 변경)
5. ArgoCD 자동 감지 (30초 주기)
6. `monitoring-staging` 네임스페이스에 자동 배포

## 3. 프로덕션 환경 (Production)

### 네임스페이스: `monitoring`

### ArgoCD Application 설정:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: lb-exporter-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/Upwardh/gitops-k2p
    targetRevision: v1.0.0  # 특정 태그 버전 사용
    path: k8s-manifests/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    # 자동 동기화 비활성화 (수동 승인 필요)
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
  revisionHistoryLimit: 10
```

### 배포 플로우:
1. Staging 환경에서 충분한 테스트 완료
2. Git 태그 생성 (예: `v1.0.0`)
3. ArgoCD에서 수동으로 `targetRevision` 업데이트
4. 수동 동기화 승인
5. `monitoring` 네임스페이스에 배포

## 4. GitHub Actions 워크플로우

### CI 파이프라인 (`ci-pipeline.yml`):
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
    paths:
      - 'my-k8s-project/lb-exporter/**'
      - '.github/workflows/**'

env:
  REGISTRY: registry.cloud.kt.com
  IMAGE_NAME: nqtv7l5h/lb-exporter

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Run tests
        run: |
          cd my-k8s-project/lb-exporter
          pip install -r requirements.txt
          # 테스트 실행

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-,format=long  # full SHA 사용
            type=raw,value=latest,enable={{is_default_branch}}
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: my-k8s-project/lb-exporter
          push: true
          tags: ${{ steps.meta.outputs.tags }}

  deploy-dev:
    needs: [build]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    steps:
      - name: Update development manifests
        run: |
          sed -i "s|newTag: .*|newTag: develop-${{ github.sha }}|g" \
            k8s-manifests/overlays/dev/kustomization.yaml
          git add k8s-manifests/overlays/dev/kustomization.yaml
          git commit -m "Update dev image to ${{ github.sha }}"
          git push

  deploy-staging:
    needs: [build]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Update staging manifests
        run: |
          sed -i "s|newTag: .*|newTag: main-${{ github.sha }}|g" \
            k8s-manifests/overlays/staging/kustomization.yaml
          git add k8s-manifests/overlays/staging/kustomization.yaml
          git commit -m "Update staging image to ${{ github.sha }}"
          git push
```

## 5. ArgoCD 설정

### 감지 주기 최적화:
```bash
# ArgoCD ConfigMap 업데이트
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"timeout.reconciliation":"30s"}}'

# ArgoCD 재시작
kubectl rollout restart statefulset/argocd-application-controller -n argocd
kubectl rollout restart deployment/argocd-repo-server -n argocd
```

### 애플리케이션 생성:
```bash
# Development
kubectl apply -f k8s-manifests/argocd-apps/lb-exporter-dev.yaml

# Staging  
kubectl apply -f k8s-manifests/argocd-apps/lb-exporter-staging.yaml

# Production
kubectl apply -f k8s-manifests/argocd-apps/lb-exporter-prod.yaml
```

## 6. 모니터링 명령어

### 환경별 상태 확인:
```bash
# ArgoCD 애플리케이션 상태
kubectl get applications -n argocd

# 각 환경 Pod 상태
kubectl get pods -n monitoring-dev
kubectl get pods -n monitoring-staging  
kubectl get pods -n monitoring

# 이미지 태그 확인
kubectl get pods -n monitoring-dev -o jsonpath='{.items[0].spec.containers[0].image}'
```

### 배포 이력 확인:
```bash
# ArgoCD 배포 이력
kubectl get application lb-exporter-dev -n argocd -o yaml | grep -A 10 history

# ReplicaSet 상태
kubectl get replicasets -n monitoring-dev
```

### 로그 확인:
```bash
# 애플리케이션 로그
kubectl logs -n monitoring-dev deployment/dev-lb-exporter --tail=20

# ArgoCD 로그
kubectl logs -n argocd statefulset/argocd-application-controller
```

## 7. 보안 설정

### Secrets 관리:
```yaml
# Registry Secret
apiVersion: v1
kind: Secret
metadata:
  name: ktcloud-registry-secret
  namespace: monitoring-dev
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-config>

# Application Secret
apiVersion: v1
kind: Secret
metadata:
  name: dev-ktcloud-lb-exporter-secrets
  namespace: monitoring-dev
data:
  CLOUD_ID: <base64-encoded-id>
  CLOUD_PASSWORD: <base64-encoded-password>
  CLOUD_ZONE: <base64-encoded-zone>
```

### GitHub Actions Secrets:
- `REGISTRY_USERNAME`: 레지스트리 사용자명
- `REGISTRY_PASSWORD`: 레지스트리 비밀번호
- `GITOPS_TOKEN`: GitOps 레포지토리 접근 토큰

---

이 가이드를 통해 각 환경의 설정과 배포 플로우를 이해하고, 문제 발생 시 적절한 트러블슈팅을 수행할 수 있습니다.