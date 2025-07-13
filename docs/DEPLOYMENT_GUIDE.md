# 🚀 KT Cloud LB Exporter Deployment Guide

## 📋 Overview
이 가이드는 KT Cloud Load Balancer Exporter의 안전한 배포 절차를 설명합니다.

## 🏗️ Environment Architecture

### Development Environment
- **Namespace**: `monitoring-dev`
- **Trigger**: `develop` 브랜치 푸시
- **Auto Deploy**: ✅ 자동 배포
- **Resources**: 1 replica, 50m CPU, 64Mi memory

### Staging Environment  
- **Namespace**: `monitoring-staging`
- **Trigger**: `main` 브랜치 푸시
- **Auto Deploy**: ✅ 자동 배포
- **Resources**: 1 replica, 100m CPU, 128Mi memory

### Production Environment
- **Namespace**: `monitoring-prod`
- **Trigger**: `v*` 태그 생성
- **Auto Deploy**: ❌ **수동 승인 필수**
- **Resources**: 2 replicas, 200m CPU, 256Mi memory

## 🔄 Deployment Workflow

### 1. Development Deployment
```bash
# develop 브랜치에 코드 푸시
git push origin develop

# ✅ 자동으로 실행됨:
# - 이미지 빌드
# - 보안 스캔
# - dev 환경 배포
```

### 2. Staging Deployment
```bash
# develop → main 병합
git checkout main
git merge develop
git push origin main

# ✅ 자동으로 실행됨:
# - 이미지 빌드  
# - 보안 스캔
# - staging 환경 배포
```

### 3. Production Deployment (Manual Process)

#### Step 1: Create Release Tag
```bash
# 릴리스 태그 생성
git tag v1.2.3
git push origin v1.2.3
```

#### Step 2: Review Release PR
1. GitHub Actions가 자동으로 `release/prod-v1.2.3` 브랜치 생성
2. Production manifest 업데이트 PR 생성됨
3. **⚠️ PR 검토 및 승인 필수**

#### Step 3: Manual ArgoCD Sync
1. PR 머지 후 ArgoCD UI 접속
2. `lb-exporter-prod` 애플리케이션 선택
3. **수동으로 Sync 버튼 클릭**
4. 배포 진행 상황 모니터링

## 🛡️ Safety Measures

### Production 배포 안전 장치
- ✅ **Manual Approval Required**: 수동 승인 필수
- ✅ **PR Review Process**: 코드 리뷰 프로세스
- ✅ **ArgoCD Manual Sync**: 수동 동기화만 허용
- ✅ **Security Scanning**: 보안 스캔 통과 필수
- ✅ **Rollback Ready**: 즉시 롤백 가능

### 환경별 격리
- ✅ **Separate Namespaces**: 환경별 네임스페이스 분리
- ✅ **Different Resource Limits**: 환경별 리소스 제한
- ✅ **Branch Protection**: 브랜치 보호 규칙

## 🚨 Emergency Procedures

### Rollback Production
```bash
# 이전 버전으로 롤백
kubectl patch application lb-exporter-prod -n argocd \
  --type='merge' -p='{"spec":{"source":{"targetRevision":"previous-commit-hash"}}}'

# ArgoCD에서 수동 sync
```

### Health Check
```bash
# Production 상태 확인
kubectl get pods -n monitoring-prod
kubectl logs -n monitoring-prod deployment/lb-exporter

# 메트릭 엔드포인트 확인
kubectl port-forward -n monitoring-prod svc/lb-exporter 9105:9105
curl http://localhost:9105/metrics
```

## 📞 Support Contacts

### CI/CD Issues
- GitHub Actions 로그 확인
- ArgoCD UI에서 sync 상태 확인

### Application Issues  
- Prometheus 메트릭 확인
- Grafana 대시보드 모니터링
- 애플리케이션 로그 분석

## 🔗 Useful Links
- [ArgoCD UI](https://argocd.yourdomain.com)
- [Grafana Dashboard](https://grafana.yourdomain.com)
- [Prometheus](https://prometheus.yourdomain.com)

---
**⚠️ 중요: Production 배포는 항상 업무 시간 중에 수행하고, 롤백 계획을 사전에 준비하세요.**