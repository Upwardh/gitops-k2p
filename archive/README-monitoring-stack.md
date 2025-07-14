# KT Cloud 모니터링 스택 CI/CD 파이프라인

## 🎯 프로젝트 개요

KT Cloud Load Balancer 모니터링을 위한 완전한 CI/CD 파이프라인이 구축되었습니다. 
dev, staging, prod 3개 환경에 동일한 모니터링 스택(Prometheus + Grafana)이 배포되어 있습니다.

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                       │
│                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐ │
│  │ monitoring-dev  │ │monitoring-staging│ │monitoring-prod   │ │
│  │                 │ │                 │ │                  │ │
│  │ • Prometheus    │ │ • Prometheus    │ │ • Prometheus     │ │
│  │ • Grafana       │ │ • Grafana       │ │ • Grafana        │ │
│  │ • lb-exporter×2 │ │ • lb-exporter×2 │ │ • lb-exporter×2  │ │
│  │ • NFS Storage   │ │ • NFS Storage   │ │ • NFS Storage    │ │
│  └─────────────────┘ └─────────────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🌐 접속 정보

| 환경 | URL | 계정 | 상태 |
|------|-----|------|------|
| 🟢 **DEV** | http://dev.grafana.devtron.click | admin / DevAdmin123 | ✅ Ready |
| 🟡 **STAGING** | http://staging.grafana.devtron.click | admin / StagingAdmin123 | ✅ Ready |
| 🔴 **PROD** | http://prod.grafana.devtron.click | admin / ProdAdmin123 | ✅ Ready |

## 📊 사용 가능한 대시보드

모든 환경에서 동일한 대시보드가 제공됩니다:

1. **KT Cloud Account - ALL**
   - 전체 Load Balancer 현황 대시보드
   - 템플릿 변수: Load Balancer, Zone, 상세 조회 LB

2. **KT Cloud LB Dashboard - ktcloud_test (DX-M1)**
   - DX-M1 Zone의 상세 모니터링
   - 개별 서버 성능 및 상태 추적

3. **KT Cloud LB Dashboard - semascrd_d019_gov (DX-G-YS)**
   - DX-G-YS Zone의 상세 모니터링
   - 개별 서버 성능 및 상태 추적

## 🚀 CI/CD 파이프라인

### 파이프라인 구조
```
GitHub Repository
├── .github/workflows/
│   ├── ci-pipeline.yml              ← 기존 (lb-exporter 앱)
│   └── monitoring-stack-cd.yml      ← 신규 (모니터링 스택)
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── scripts/
    └── deploy-monitoring-stack.sh
```

### 자동 배포 트리거
- **develop 브랜치** → DEV 환경 자동 배포
- **main 브랜치** → STAGING → PROD 순차 배포
- **environments/** 경로 변경시에만 트리거

### GitHub Secrets 설정
다음 Secrets이 설정되어야 합니다:
- `KUBECONFIG_DEV`
- `KUBECONFIG_STAGING` 
- `KUBECONFIG_PROD`

## 🛠️ 수동 배포

### 배포 스크립트 사용
```bash
# 개발 환경 배포
./scripts/deploy-monitoring-stack.sh dev

# 스테이징 환경 배포  
./scripts/deploy-monitoring-stack.sh staging

# 프로덕션 환경 배포
./scripts/deploy-monitoring-stack.sh prod

# 도움말
./scripts/deploy-monitoring-stack.sh --help
```

### Helm 직접 사용
```bash
# 특정 환경 배포
helm upgrade --install prometheus-dev prometheus-community/kube-prometheus-stack \
  -f environments/dev/prometheus-values-dev.yaml \
  -n monitoring-dev \
  --create-namespace
```

## 💾 데이터 영구성

### NFS 기반 영구 저장소
- **Prometheus**: 10Gi (dev), 10Gi (staging), 20Gi (prod)
- **Grafana**: 5Gi (dev), 5Gi (staging), 10Gi (prod)
- **StorageClass**: ktc-nfs-client

### 백업 및 복구
```bash
# Grafana 대시보드 백업
kubectl exec -n monitoring-dev deployment/prometheus-dev-grafana -- \
  curl -s -u admin:DevAdmin123 \
  "http://localhost:3000/api/search?type=dash-db" > backup-dashboards.json

# Prometheus 데이터는 자동으로 NFS에 저장됨
```

## 📈 모니터링 메트릭

### 수집되는 주요 메트릭
- `ktcloud_lb_total_count` - 총 LB 수
- `ktcloud_lb_info` - LB 상태 정보  
- `ktcloud_lb_server_count` - LB별 서버 수
- `ktcloud_lb_server_state` - 서버 상태
- `ktcloud_server_current_connections` - 현재 연결 수
- `ktcloud_server_throughput_rate_kbps` - 처리량
- `ktcloud_server_avg_ttfb_ms` - 평균 응답 시간
- `ktcloud_server_requests_rate_per_sec` - 초당 요청 수

### 수집 주기
- **Scrape Interval**: 60초
- **Scrape Timeout**: 20초
- **데이터 보관**: 15일

## 🔧 환경별 설정

### DEV 환경
```yaml
namespace: monitoring-dev
replica: 1
resources: 
  cpu: 50m, memory: 64Mi
storage:
  prometheus: 10Gi
  grafana: 5Gi
```

### STAGING 환경  
```yaml
namespace: monitoring-staging
replica: 1
resources:
  cpu: 100m, memory: 128Mi
storage:
  prometheus: 10Gi
  grafana: 5Gi
```

### PROD 환경
```yaml
namespace: monitoring-prod
replica: 2
resources:
  cpu: 200m, memory: 256Mi
storage:
  prometheus: 20Gi
  grafana: 10Gi
```

## 🚨 트러블슈팅

### 일반적인 문제

**1. 대시보드에서 "No data" 표시**
```bash
# lb-exporter 상태 확인
kubectl get pods -n monitoring-dev | grep lb-exporter

# 메트릭 엔드포인트 확인
kubectl exec -n monitoring-dev deployment/dev-lb-exporter -- curl localhost:9105/metrics
```

**2. Grafana 접속 불가**
```bash
# 인그레스 상태 확인
kubectl get ingress -n monitoring-dev

# 서비스 상태 확인  
kubectl get svc -n monitoring-dev | grep grafana
```

**3. Pod 재시작 반복**
```bash
# 로그 확인
kubectl logs -n monitoring-dev deployment/prometheus-dev-grafana

# 리소스 사용량 확인
kubectl top pods -n monitoring-dev
```

### 로그 확인 명령어
```bash
# Prometheus 로그
kubectl logs -n monitoring-dev prometheus-prometheus-dev-kube-promet-prometheus-0

# Grafana 로그
kubectl logs -n monitoring-dev deployment/prometheus-dev-grafana

# lb-exporter 로그
kubectl logs -n monitoring-dev deployment/dev-lb-exporter
kubectl logs -n monitoring-dev deployment/dev-lb-exporter-account2
```

## 🔄 업그레이드 가이드

### 모니터링 스택 업그레이드
```bash
# Helm 차트 업데이트
helm repo update prometheus-community

# 특정 환경 업그레이드
helm upgrade prometheus-dev prometheus-community/kube-prometheus-stack \
  -f environments/dev/prometheus-values-dev.yaml \
  -n monitoring-dev
```

### 대시보드 업데이트
```bash
# 새 대시보드 임포트
kubectl exec -n monitoring-dev deployment/prometheus-dev-grafana -- \
  curl -X POST \
  -H "Content-Type: application/json" \
  -u admin:DevAdmin123 \
  -d @new-dashboard.json \
  "http://localhost:3000/api/dashboards/db"
```

## 📋 운영 체크리스트

### 일일 점검
- [ ] 모든 환경 Grafana 접속 확인
- [ ] 대시보드 데이터 수집 정상 여부 확인
- [ ] 알람 발생 내역 검토

### 주간 점검  
- [ ] 스토리지 사용량 확인
- [ ] Pod 리소스 사용량 확인
- [ ] 백업 데이터 검증

### 월간 점검
- [ ] Helm 차트 업데이트 검토
- [ ] 보안 패치 적용
- [ ] 성능 최적화 검토

## 🔮 향후 개선 계획

### 단기 (1-2개월)
- [ ] Alertmanager 알림 규칙 추가
- [ ] Slack/Email 알림 연동
- [ ] 대시보드 성능 최적화

### 중기 (3-6개월)  
- [ ] 멀티 클러스터 지원
- [ ] 로그 집중화 (ELK/Loki)
- [ ] GitOps 전환 (ArgoCD)

### 장기 (6개월+)
- [ ] Service Mesh 모니터링
- [ ] 비용 최적화 대시보드
- [ ] 머신러닝 기반 이상 탐지

## 📞 지원 및 문의

### 긴급 상황
1. 모든 환경 장애: Infrastructure 팀 연락
2. 특정 환경 장애: 해당 환경 담당자 연락
3. 데이터 손실: 백업 복구 절차 수행

### 일반 문의
- GitHub Issues 등록
- Documentation 참조: `docs/`
- 클러스터 분리 가이드: `docs/cluster-separation-guide.md`

---

**📅 최종 업데이트**: 2025-07-13
**👥 관리자**: Infrastructure Team
**📋 버전**: v1.0.0