# 클러스터 분리 운영 가이드

## 📋 개요

현재는 단일 클러스터에서 네임스페이스로 환경을 분리하고 있지만, 향후 보안성과 격리를 위해 환경별로 클러스터를 분리할 때의 대응 방안을 정리합니다.

## 🏗️ 현재 아키텍처 vs 분리 아키텍처

### 현재 (Single Cluster)
```
┌─────────────────────────────────────┐
│        Kubernetes Cluster          │
│                                     │
│  ┌─────────────┐ ┌─────────────┐   │
│  │monitoring-  │ │monitoring-  │   │
│  │dev          │ │staging      │   │
│  └─────────────┘ └─────────────┘   │
│                                     │
│  ┌─────────────┐                   │
│  │monitoring-  │                   │
│  │prod         │                   │
│  └─────────────┘                   │
└─────────────────────────────────────┘
```

### 분리 후 (Multi Cluster)
```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Dev Cluster   │ │Staging Cluster  │ │  Prod Cluster   │
│                 │ │                 │ │                 │
│ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │monitoring   │ │ │ │monitoring   │ │ │ │monitoring   │ │
│ │             │ │ │ │             │ │ │ │             │ │
│ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 🔧 클러스터 분리 시 필요한 변경사항

### 1. GitHub Secrets 업데이트

현재 모든 환경이 같은 kubeconfig를 사용하지만, 분리 후에는 각각 다른 설정이 필요합니다:

```bash
# 현재 (단일 클러스터)
KUBECONFIG_DEV=<같은_클러스터_설정>
KUBECONFIG_STAGING=<같은_클러스터_설정>
KUBECONFIG_PROD=<같은_클러스터_설정>

# 분리 후 (다중 클러스터)
KUBECONFIG_DEV=<dev_클러스터_설정>
KUBECONFIG_STAGING=<staging_클러스터_설정>
KUBECONFIG_PROD=<prod_클러스터_설정>
```

**설정 방법:**
```bash
# 각 클러스터별 kubeconfig 생성
kubectl config view --raw > dev-cluster-config.yaml
kubectl config view --raw > staging-cluster-config.yaml
kubectl config view --raw > prod-cluster-config.yaml

# Base64 인코딩
cat dev-cluster-config.yaml | base64 -w 0
cat staging-cluster-config.yaml | base64 -w 0
cat prod-cluster-config.yaml | base64 -w 0
```

### 2. 네트워킹 고려사항

#### 도메인/DNS 설정
```yaml
# 현재 설정
dev.grafana.devtron.click     → 단일_클러스터_IP
staging.grafana.devtron.click → 단일_클러스터_IP
prod.grafana.devtron.click    → 단일_클러스터_IP

# 분리 후 설정
dev.grafana.devtron.click     → DEV_클러스터_IP
staging.grafana.devtron.click → STAGING_클러스터_IP
prod.grafana.devtron.click    → PROD_클러스터_IP
```

#### 인그레스 컨트롤러
각 클러스터마다 별도의 nginx-ingress-controller 설치 필요:

```bash
# 각 클러스터에서 실행
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer
```

### 3. 스토리지 분리

#### NFS 서버 분리 옵션

**Option 1: 환경별 NFS 서버**
```yaml
# dev-cluster
storageClassName: dev-nfs-client

# staging-cluster  
storageClassName: staging-nfs-client

# prod-cluster
storageClassName: prod-nfs-client
```

**Option 2: 공유 NFS, 별도 경로**
```yaml
# 모든 클러스터에서 같은 NFS 사용, 경로만 분리
nfs:
  server: shared-nfs-server.internal
  path: /data/dev      # dev 클러스터
  path: /data/staging  # staging 클러스터
  path: /data/prod     # prod 클러스터
```

### 4. 보안 설정 강화

#### 클러스터별 RBAC
```yaml
# 각 클러스터마다 별도 ServiceAccount 및 권한 설정
apiVersion: v1
kind: ServiceAccount
metadata:
  name: monitoring-admin
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: monitoring-admin-binding
subjects:
- kind: ServiceAccount
  name: monitoring-admin
  namespace: monitoring
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
```

#### 네트워크 정책
```yaml
# 환경 간 트래픽 격리
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-cross-environment
  namespace: monitoring
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
```

## 🚀 마이그레이션 단계별 가이드

### Phase 1: 준비 단계
1. **새 클러스터 준비**
   ```bash
   # 각 환경별 클러스터 생성
   # - Dev Cluster
   # - Staging Cluster  
   # - Prod Cluster
   ```

2. **네트워킹 설정**
   ```bash
   # DNS 레코드 업데이트 준비
   # LoadBalancer IP 할당
   # 인그레스 컨트롤러 설치
   ```

3. **스토리지 준비**
   ```bash
   # NFS 서버 설정 또는 분리
   # StorageClass 생성
   ```

### Phase 2: 개발 환경 마이그레이션
1. **Dev 클러스터 배포**
   ```bash
   # kubeconfig 설정
   export KUBECONFIG=dev-cluster-config.yaml
   
   # 모니터링 스택 배포
   ./scripts/deploy-monitoring-stack.sh dev
   ```

2. **데이터 마이그레이션**
   ```bash
   # 기존 Grafana 대시보드 백업
   # Prometheus 데이터 백업 (필요시)
   ```

3. **DNS 업데이트**
   ```bash
   # dev.grafana.devtron.click → 새 클러스터 IP
   ```

### Phase 3: 스테이징 환경 마이그레이션
Dev 환경과 동일한 절차로 진행

### Phase 4: 프로덕션 환경 마이그레이션
더욱 신중하게 진행:
1. **점검 시간 확보**
2. **백업 완료 확인**
3. **롤백 계획 수립**
4. **단계별 전환**

## 🔄 CI/CD 파이프라인 업데이트

### GitHub Actions 수정 불필요
현재 CI/CD 파이프라인은 이미 환경별 kubeconfig를 사용하도록 설계되어 있어서, GitHub Secrets만 업데이트하면 자동으로 각 클러스터에 배포됩니다.

```yaml
# .github/workflows/monitoring-stack-cd.yml
# 이미 환경별 kubeconfig 사용
- name: Configure kubectl
  run: |
    echo "${{ secrets.KUBECONFIG_DEV }}" | base64 -d > ~/.kube/config
    kubectl config use-context dev-cluster  # 각 클러스터별 context
```

### 배포 스크립트 수정 불필요
`scripts/deploy-monitoring-stack.sh`도 수정 없이 그대로 사용 가능합니다.

## 📊 모니터링 및 관리

### 중앙 집중식 모니터링
분리된 클러스터들을 중앙에서 모니터링하기 위한 옵션:

**Option 1: Prometheus Federation**
```yaml
# Central Prometheus가 각 클러스터의 Prometheus에서 데이터 수집
- job_name: 'federate-dev'
  scrape_interval: 15s
  honor_labels: true
  metrics_path: '/federate'
  params:
    'match[]':
      - '{job=~"ktcloud-.*"}'
  static_configs:
    - targets:
      - 'dev-prometheus.internal:9090'
```

**Option 2: Grafana Datasource 통합**
```yaml
# 중앙 Grafana에서 모든 클러스터의 Prometheus 연결
datasources:
  - name: Dev-Prometheus
    url: http://dev-prometheus.internal:9090
  - name: Staging-Prometheus  
    url: http://staging-prometheus.internal:9090
  - name: Prod-Prometheus
    url: http://prod-prometheus.internal:9090
```

### 로그 중앙 집중화
```yaml
# ELK Stack 또는 Loki 구성으로 모든 클러스터 로그 수집
```

## 🚨 주의사항

### 보안 고려사항
1. **클러스터 간 통신 암호화**
2. **각 클러스터별 독립적인 인증 시스템**
3. **Secrets 관리 강화**
4. **정기적인 접근 권한 검토**

### 운영 고려사항
1. **각 클러스터별 백업 정책**
2. **장애 대응 절차 수립**
3. **비용 최적화 (클러스터 리소스 관리)**
4. **업그레이드 전략 수립**

### 성능 고려사항
1. **네트워크 레이턴시 증가 가능성**
2. **스토리지 성능 분산**
3. **클러스터별 리소스 할당 최적화**

## 🔧 도구 및 유틸리티

### 클러스터 전환 스크립트
```bash
#!/bin/bash
# scripts/switch-cluster.sh

ENVIRONMENT=${1:-"dev"}

case "$ENVIRONMENT" in
    dev)
        export KUBECONFIG=~/.kube/dev-cluster-config.yaml
        kubectl config use-context dev-cluster
        ;;
    staging)
        export KUBECONFIG=~/.kube/staging-cluster-config.yaml
        kubectl config use-context staging-cluster
        ;;
    prod)
        export KUBECONFIG=~/.kube/prod-cluster-config.yaml
        kubectl config use-context prod-cluster
        ;;
    *)
        echo "Usage: $0 {dev|staging|prod}"
        exit 1
        ;;
esac

echo "Switched to $ENVIRONMENT cluster"
kubectl cluster-info
```

### 다중 클러스터 배포 스크립트
```bash
#!/bin/bash
# scripts/deploy-all-clusters.sh

for env in dev staging prod; do
    echo "Deploying to $env cluster..."
    ./scripts/switch-cluster.sh $env
    ./scripts/deploy-monitoring-stack.sh $env
    echo "$env deployment completed"
done
```

이 가이드를 따라하면 향후 클러스터 분리 시에도 원활하게 전환할 수 있습니다.