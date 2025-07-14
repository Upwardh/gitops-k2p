# 🔧 CI/CD 파이프라인 설정 체크리스트

## 1. ArgoCD Application 설정 수정 필요

### 파일 위치 및 수정 내용:
```bash
# 1. k8s-manifests/argocd-apps/lb-exporter-dev.yaml
# 2. k8s-manifests/argocd-apps/lb-exporter-staging.yaml  
# 3. k8s-manifests/argocd-apps/lb-exporter-prod.yaml
# 4. k8s-manifests/argocd-apps/project.yaml

# 수정할 내용:
repoURL: https://github.com/YOUR_ORG/ktcloud-api-gitops
↓
repoURL: https://github.com/실제조직명/실제GitOps저장소명
```

## 2. KT Cloud 인증 정보 설정

### 파일: k8s-manifests/base/secret.yaml
```yaml
stringData:
  CLOUD_ID: "실제_KT_Cloud_계정_ID"
  CLOUD_PASSWORD: "실제_KT_Cloud_패스워드"
  CLOUD_ZONE: "실제_사용_존"  # 예: DX-M1, DX-Central, DX-DCN-CJ, DX-G, DX-G-YS
```

## 3. Container Registry 네임스페이스 확인

### 현재 설정된 값:
```
registry.cloud.kt.com/nqtv7l5h/lb-exporter
```

### 다른 네임스페이스 사용 시 수정할 파일들:
- `.github/workflows/ci-pipeline.yml` (IMAGE_NAME 변수)
- `k8s-manifests/base/kustomization.yaml`
- `k8s-manifests/overlays/*/kustomization.yaml`

## 4. GitHub Repository 설정

### 필요한 GitHub Secrets 추가:
```bash
# Settings > Secrets and variables > Actions 에서 추가:

REGISTRY_USERNAME=실제_KT_Cloud_레지스트리_사용자명
REGISTRY_PASSWORD=실제_KT_Cloud_레지스트리_패스워드
GITOPS_REPO=실제_GitOps_저장소_URL
GITOPS_TOKEN=GitHub_Personal_Access_Token
```

### GitHub Personal Access Token 권한:
- repo (전체 저장소 접근)
- workflow (GitHub Actions 워크플로우)
- write:packages (패키지 쓰기)

## 5. 배포 환경 설정

### 개발 환경 (Development):
- 네임스페이스: `monitoring-dev`
- 이미지 태그: `develop-latest`
- 자동 동기화: 활성화

### 스테이징 환경 (Staging):
- 네임스페이스: `monitoring-staging`
- 이미지 태그: `main-latest`
- 자동 동기화: 활성화

### 프로덕션 환경 (Production):
- 네임스페이스: `monitoring`
- 이미지 태그: 특정 버전 태그 (예: v1.0.0)
- 자동 동기화: 수동 승인 필요

## 6. 확인 사항

### KT Cloud 레지스트리 접근 확인:
```bash
# 로컬에서 테스트
docker login registry.cloud.kt.com
docker build -t registry.cloud.kt.com/nqtv7l5h/lb-exporter:test .
docker push registry.cloud.kt.com/nqtv7l5h/lb-exporter:test
```

### Kubernetes 클러스터 접근 확인:
```bash
kubectl cluster-info
kubectl get nodes
```

### 지원되는 KT Cloud 존:
- DX-M1
- DX-Central
- DX-DCN-CJ
- DX-G
- DX-G-YS

## 7. 다음 단계 실행 순서

### 1단계: 설정 파일 수정
```bash
# 위에서 언급한 파일들을 실제 값으로 수정
```

### 2단계: GitHub 설정
```bash
# GitHub Secrets 추가
# GitHub Actions 활성화
```

### 3단계: ArgoCD 설치
```bash
./scripts/setup-argocd.sh install
```

### 4단계: 첫 배포
```bash
# 개발 환경 배포
./scripts/deploy.sh dev deploy

# 스테이징 환경 배포
./scripts/deploy.sh staging argocd
```

### 5단계: 모니터링
```bash
# ArgoCD UI 접속
./scripts/setup-argocd.sh port-forward
# https://localhost:8080

# 배포 상태 확인
./scripts/deploy.sh prod check
```