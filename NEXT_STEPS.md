# 🚀 다음 단계: GitHub 저장소 설정

## ✅ 완료된 작업
- ArgoCD 매니페스트 파일에 실제 저장소 URL 설정 완료
- GitHub Actions 워크플로우에 저장소 정보 업데이트 완료
- 저장소: `https://github.com/Upwardh/gitops-k2p`

## 🔧 다음에 해야 할 작업

### 1. GitHub Personal Access Token 생성
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token" 클릭
3. 권한 설정:
   - `repo` (전체 저장소 접근)
   - `workflow` (GitHub Actions 접근)
   - `write:packages` (패키지 레지스트리 접근)
4. 생성된 토큰 복사 (한 번만 표시됨)

### 2. GitHub Secrets 설정
GitHub 저장소 → Settings → Secrets and variables → Actions에서 다음 추가:

```bash
# KT Cloud 레지스트리 인증 정보
REGISTRY_USERNAME = 실제_KT_Cloud_레지스트리_사용자명
REGISTRY_PASSWORD = 실제_KT_Cloud_레지스트리_패스워드

# GitOps 저장소 접근 토큰
GITOPS_TOKEN = 위에서_생성한_Personal_Access_Token
```

### 3. 현재 코드를 GitHub에 푸시
```bash
# 현재 디렉토리에서 실행
git init
git add .
git commit -m "Initial CI/CD pipeline setup"
git remote add origin https://github.com/Upwardh/gitops-k2p.git
git branch -M main
git push -u origin main
```

### 4. KT Cloud 인증 정보 설정
다음 파일을 실제 값으로 수정:
```yaml
# k8s-manifests/base/secret.yaml
stringData:
  CLOUD_ID: "실제_KT_Cloud_계정_ID"
  CLOUD_PASSWORD: "실제_KT_Cloud_패스워드"
  CLOUD_ZONE: "실제_사용_존"  # 예: DX-M1, DX-Central 등
```

### 5. 테스트 단계

#### Step 1: KT Cloud 레지스트리 접근 테스트
```bash
# 로컬에서 테스트
docker login registry.cloud.kt.com
# 사용자명과 패스워드 입력

# 테스트 빌드
cd my-k8s-project/lb-exporter
docker build -t registry.cloud.kt.com/nqtv7l5h/lb-exporter:test .
docker push registry.cloud.kt.com/nqtv7l5h/lb-exporter:test
```

#### Step 2: GitHub Actions 테스트
```bash
# 코드 푸시 후 GitHub Actions 탭에서 확인
git add .
git commit -m "Test CI/CD pipeline"
git push
```

#### Step 3: ArgoCD 설치 및 배포
```bash
# ArgoCD 설치
./scripts/setup-argocd.sh install

# 개발 환경 배포
./scripts/deploy.sh dev deploy
```

## 📋 확인 사항

### GitHub 저장소 접근 권한
- 저장소가 public인지 private인지 확인
- Private 저장소의 경우 ArgoCD에서 접근 가능하도록 설정 필요

### KT Cloud 레지스트리 네임스페이스
- 현재 설정: `nqtv7l5h`
- 다른 네임스페이스 사용 시 다음 파일들 수정 필요:
  - `.github/workflows/ci-pipeline.yml` (IMAGE_NAME)
  - `k8s-manifests/base/kustomization.yaml`
  - `k8s-manifests/overlays/*/kustomization.yaml`

## 🆘 문제 해결

### GitHub Actions 실패 시
1. Secrets 설정 확인
2. 레지스트리 인증 정보 확인
3. Actions 탭에서 로그 확인

### ArgoCD 동기화 실패 시
1. 저장소 접근 권한 확인
2. 매니페스트 문법 확인
3. ArgoCD UI에서 상세 에러 확인

## 🎯 목표 상태
- GitHub Actions가 성공적으로 실행됨
- Docker 이미지가 KT Cloud 레지스트리에 푸시됨
- ArgoCD가 저장소를 모니터링하고 배포함
- 3개 환경(dev, staging, prod)이 정상 운영됨