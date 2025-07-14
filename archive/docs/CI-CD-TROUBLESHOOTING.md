# CI/CD 파이프라인 구축 및 트러블슈팅 가이드

## 개요
KT Cloud Load Balancer Exporter의 완전 자동화된 CI/CD 파이프라인 구축 과정에서 발생한 문제들과 해결 방법을 정리합니다.

## 환경 구성

### 1. 환경별 구조
- **Development**: `develop` 브랜치 → `monitoring-dev` 네임스페이스
- **Staging**: `main` 브랜치 → `monitoring-staging` 네임스페이스  
- **Production**: 수동 배포 → `monitoring` 네임스페이스

### 2. CI/CD 파이프라인 구조
```
Code Change → GitHub Actions → Docker Build → Registry Push → 
GitOps Update → ArgoCD Sync → Kubernetes Deploy
```

## 주요 문제 및 해결 과정

### 🔴 문제 1: Docker 이미지 태그 SHA 길이 불일치

**증상:**
- GitHub Actions에서 Docker 이미지 빌드 성공
- ArgoCD에서 ImagePullBackOff 오류 발생
- 이미지가 레지스트리에서 "not found" 오류

**원인 분석:**
- Docker metadata action: `develop-479179f` (7자리 short SHA)
- GitOps 매니페스트: `develop-479179f6d81e9cf820532a2d9dd0bee843f0e23f` (40자리 full SHA)

**해결 방법:**
```yaml
# .github/workflows/ci-pipeline.yml
tags: |
  type=ref,event=branch
  type=ref,event=pr
  type=sha,prefix={{branch}}-,format=long  # ← format=long 추가
  type=raw,value=latest,enable={{is_default_branch}}
```

**검증 방법:**
```bash
# 레지스트리 태그 확인
kubectl run registry-check --image=curlimages/curl --rm -i --tty -- sh
curl -u "username:password" "https://registry.cloud.kt.com/v2/repo/tags/list"
```

### 🔴 문제 2: ArgoCD 자동 동기화 실패

**증상:**
- GitOps 레포지토리 업데이트 후 ArgoCD가 자동 동기화하지 않음
- 수동으로 sync를 해야만 배포됨

**원인 분석:**
- ArgoCD Application의 `targetRevision`이 특정 커밋 SHA로 고정됨
- `targetRevision: 0f26b0b` (고정) → 새로운 커밋 감지 불가

**해결 방법:**
```bash
# Dev 환경
kubectl patch application lb-exporter-dev -n argocd --type merge \
  -p '{"spec":{"source":{"targetRevision":"develop"}}}'

# Staging 환경  
kubectl patch application lb-exporter-staging -n argocd --type merge \
  -p '{"spec":{"source":{"targetRevision":"main"}}}'
```

**올바른 ArgoCD Application 설정:**
```yaml
spec:
  source:
    targetRevision: develop  # 브랜치명 사용 (커밋 SHA 아님)
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 🔴 문제 3: ArgoCD 감지 주기가 너무 김

**증상:**
- GitOps 변경 후 3분 정도 기다려야 ArgoCD가 감지
- 실시간 배포 효과가 떨어짐

**해결 방법:**
```bash
# ArgoCD 감지 주기를 30초로 단축
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"timeout.reconciliation":"30s"}}'

# ArgoCD 재시작
kubectl rollout restart statefulset/argocd-application-controller -n argocd
kubectl rollout restart deployment/argocd-repo-server -n argocd
```

### 🔴 문제 4: 불필요한 ReplicaSet 누적

**증상:**
- 배포할 때마다 이전 ReplicaSet이 계속 남아있음
- 클러스터 리소스 낭비

**해결 방법:**
```yaml
# k8s-manifests/base/deployment.yaml
spec:
  revisionHistoryLimit: 2  # 최대 2개의 이전 버전만 보관
```

**기존 ReplicaSet 정리:**
```bash
# 불필요한 ReplicaSet 확인 (DESIRED=0)
kubectl get replicasets -n monitoring-dev

# 일괄 삭제
kubectl delete replicaset $(kubectl get replicaset -n monitoring-dev -o name | grep "0         0         0") -n monitoring-dev
```

## 트러블슈팅 명령어 모음

### 1. CI/CD 파이프라인 상태 확인
```bash
# GitHub Actions 워크플로우 상태
curl -s "https://api.github.com/repos/owner/repo/actions/runs?branch=develop" | jq '.workflow_runs[0]'

# ArgoCD 애플리케이션 상태
kubectl get applications -n argocd

# Pod 이미지 확인
kubectl get pods -n monitoring-dev -o jsonpath='{.items[0].spec.containers[0].image}'
```

### 2. 레지스트리 연결 테스트
```bash
# 레지스트리 접근 테스트
kubectl run registry-test --image=curlimages/curl --rm -i --tty -- sh
curl -v https://registry.cloud.kt.com/v2/

# 인증된 태그 목록 조회
TOKEN=$(curl -s -u "user:pass" "https://registry.cloud.kt.com/service/token?service=harbor-registry&scope=repository:repo:pull" | jq -r .token)
curl -H "Authorization: Bearer $TOKEN" "https://registry.cloud.kt.com/v2/repo/tags/list"
```

### 3. ArgoCD 강제 동기화
```bash
# 애플리케이션 리프레시
kubectl annotate application app-name -n argocd argocd.argoproj.io/refresh=hard --overwrite

# 특정 커밋으로 동기화
kubectl patch application app-name -n argocd --type merge \
  -p '{"spec":{"source":{"targetRevision":"commit-sha"}}}'
```

### 4. 로그 확인
```bash
# 애플리케이션 로그
kubectl logs -n monitoring-dev deployment/dev-lb-exporter --tail=20

# ArgoCD 컨트롤러 로그
kubectl logs -n argocd statefulset/argocd-application-controller

# GitHub Actions 로그 (API)
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/owner/repo/actions/runs/run-id/logs"
```

## 모니터링 및 알림

### 1. 핵심 모니터링 포인트
- GitHub Actions 워크플로우 성공률
- Docker 이미지 빌드 및 푸시 성공률
- ArgoCD 동기화 상태
- Pod 헬스 체크 상태
- 메트릭 엔드포인트 응답

### 2. 알림 설정 (예시)
```yaml
# ArgoCD Notification 설정
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
data:
  service.slack: |
    token: $slack-token
  template.app-sync-failed: |
    message: Application {{.app.metadata.name}} sync failed
  trigger.on-sync-failed: |
    - when: app.status.operationState.phase in ['Error', 'Failed']
      send: [app-sync-failed]
```

## 베스트 프랙티스

### 1. CI/CD 파이프라인
- SHA 태그는 항상 full format 사용
- 환경별로 다른 브랜치 전략 적용
- 이미지 태그에 브랜치명 prefix 사용

### 2. ArgoCD 관리
- `targetRevision`은 브랜치명 사용
- 자동 동기화 및 self-heal 활성화
- 적절한 감지 주기 설정 (30초 권장)

### 3. 리소스 관리
- `revisionHistoryLimit` 설정으로 ReplicaSet 관리
- 정기적인 불필요 리소스 정리
- 네임스페이스별 리소스 할당량 설정

### 4. 보안
- 레지스트리 인증 정보는 Kubernetes Secret 사용
- GitHub Actions Secrets로 민감 정보 관리
- Pod Security Context 적용

## 문제 발생 시 체크리스트

### ✅ GitHub Actions 실패 시
1. 트리거 조건 확인 (`paths` 필터)
2. Registry 인증 정보 확인
3. Dockerfile 빌드 오류 확인
4. Secret 값 확인

### ✅ 이미지 Pull 실패 시
1. 이미지 태그 일치 여부 확인
2. 레지스트리 접근 권한 확인
3. imagePullSecret 설정 확인
4. 네트워크 연결 확인

### ✅ ArgoCD 동기화 실패 시
1. `targetRevision` 설정 확인
2. Git 레포지토리 접근 권한 확인
3. Kustomize 문법 오류 확인
4. 애플리케이션 로그 확인

### ✅ Pod 시작 실패 시
1. 리소스 요청량 확인
2. 환경 변수 설정 확인
3. Secret/ConfigMap 존재 확인
4. Security Context 설정 확인

---

## 참고 자료
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Kustomize Documentation](https://kustomize.io/)
- [Docker Metadata Action](https://github.com/docker/metadata-action)

---
**작성일**: 2025-07-12  
**작성자**: CI/CD 파이프라인 구축 프로젝트  
**버전**: 1.0.0