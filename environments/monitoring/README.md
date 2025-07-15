# KT Cloud LB Monitoring Dashboards - GitOps Management

이 디렉터리는 KT Cloud Load Balancer 모니터링 대시보드를 GitOps 방식으로 관리합니다.

## 📁 디렉터리 구조

```
environments/monitoring/
├── base/                                    # 기본 대시보드 템플릿
│   ├── dashboard-all-enhanced.json         # 통합 대시보드 (Total 값 포함)
│   ├── dashboard-ktcloud-test-dx-m1.json   # ktcloud_test (DX-M1) 전용
│   ├── dashboard-semascrd-dx-g-ys.json     # semascrd_d019_gov (DX-G-YS) 전용
│   └── kustomization.yaml                  # 기본 Kustomize 설정
├── dev/                                     # 개발 환경
│   ├── dashboard-*.json                     # 환경별 대시보드 파일
│   └── kustomization.yaml                  # Dev 환경 Kustomize 설정
├── staging/                                 # 스테이징 환경
│   ├── dashboard-*.json                     
│   └── kustomization.yaml                  
└── prod/                                    # 프로덕션 환경
    ├── dashboard-*.json                     
    └── kustomization.yaml                  
```

## 🚀 배포 방법

### 환경별 배포

```bash
# 개발 환경 배포
cd environments/monitoring/dev
kubectl apply -k .

# 스테이징 환경 배포
cd environments/monitoring/staging
kubectl apply -k .

# 프로덕션 환경 배포
cd environments/monitoring/prod
kubectl apply -k .
```

### 변경사항 미리보기

```bash
# 배포 전 YAML 확인
kubectl kustomize environments/monitoring/dev
```

## 📊 대시보드 종류

### 1. **통합 대시보드** (`dashboard-all-enhanced.json`)
- **용도**: 모든 계정의 통합 모니터링
- **특징**: TTFB, Throughput, Requests Total 값 포함
- **UID**: `ktcloud-lb-enhanced-totals-dashboard`

### 2. **ktcloud_test 전용** (`dashboard-ktcloud-test-dx-m1.json`)
- **용도**: ktcloud_test 계정 (DX-M1 Zone) 전용
- **필터링**: `zone="DX-M1"`
- **UID**: `ktcloud-lb-dx-m1-dashboard`

### 3. **semascrd_d019_gov 전용** (`dashboard-semascrd-dx-g-ys.json`)
- **용도**: semascrd_d019_gov 계정 (DX-G-YS Zone) 전용
- **필터링**: `zone="DX-G-YS"`
- **UID**: `ktcloud-lb-dx-g-ys-dashboard`

## 🔧 Enhanced 메트릭

모든 대시보드에서 다음 Total 값들을 확인할 수 있습니다:

- **TTFB Total**: `avg(ktcloud_server_avg_ttfb_ms{...})` - 전체 평균 응답 시간
- **Throughput Total**: `sum(ktcloud_server_throughput_rate_kbps{...})` - 전체 처리량 합계  
- **Requests Total**: `sum(ktcloud_server_requests_rate_per_sec{...})` - 전체 요청율 합계

## 🎨 시각화 특징

- Total 값은 굵은 선(3px)으로 구분되어 표시
- 계정별로 다른 색상 테마 적용
- 범례에 lastNotNull, sum, max, mean 값 표시
- 30초 자동 새로고침

## 🔄 대시보드 수정 워크플로우

### 1. 로컬에서 수정
```bash
# 대시보드 JSON 파일 수정
vi environments/monitoring/base/dashboard-all-enhanced.json
```

### 2. 환경별 동기화
```bash
# 모든 환경에 변경사항 복사
cp environments/monitoring/base/dashboard-*.json environments/monitoring/dev/
cp environments/monitoring/base/dashboard-*.json environments/monitoring/staging/
cp environments/monitoring/base/dashboard-*.json environments/monitoring/prod/
```

### 3. 배포 테스트
```bash
# Dev 환경에서 먼저 테스트
cd environments/monitoring/dev
kubectl apply -k .

# Grafana에서 대시보드 확인 후 다른 환경 배포
```

### 4. 버전 관리
```bash
# Git으로 변경사항 커밋
git add environments/monitoring/
git commit -m "feat: Update dashboard with new metrics"
git push
```

## 🏗️ CI/CD 통합

향후 CI/CD 파이프라인에서 자동 배포를 위한 설정:

```yaml
# GitHub Actions 예시
- name: Deploy Dashboards
  run: |
    kubectl apply -k environments/monitoring/dev
    kubectl apply -k environments/monitoring/staging
    # Production은 수동 승인 필요
```

## 📋 환경별 설정

| 환경 | Namespace | Grafana Instance | Auto-Deploy |
|------|-----------|------------------|-------------|
| Dev | `monitoring-dev` | `prometheus-dev` | ✅ |
| Staging | `monitoring-staging` | `prometheus-staging` | ✅ |
| Prod | `monitoring` | `prometheus-prod` | ❌ (Manual) |

## 🔍 트러블슈팅

### ConfigMap이 생성되지 않는 경우
```bash
# Kustomize 빌드 확인
kubectl kustomize environments/monitoring/dev

# 파일 경로 확인
ls -la environments/monitoring/base/dashboard-*.json
```

### Grafana에서 대시보드가 보이지 않는 경우
```bash
# ConfigMap 레이블 확인
kubectl get configmap ktcloud-lb-dashboards -o yaml | grep grafana_dashboard

# Grafana 재시작
kubectl rollout restart deployment prometheus-dev-grafana -n monitoring-dev
```

### 대시보드 내용이 업데이트되지 않는 경우
```bash
# ConfigMap 강제 재생성
kubectl delete configmap ktcloud-lb-dashboards -n monitoring-dev
kubectl apply -k environments/monitoring/dev
```

## ✅ 장점

1. **버전 관리**: 모든 대시보드 변경사항이 Git으로 추적됨
2. **환경 일관성**: Base 템플릿으로 환경 간 일관성 보장
3. **롤백 용이**: Git 히스토리를 통한 쉬운 롤백
4. **자동화 가능**: CI/CD 파이프라인과 쉬운 통합
5. **검토 프로세스**: Pull Request를 통한 변경사항 검토