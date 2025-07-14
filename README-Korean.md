# KT Cloud Load Balancer Exporter (한국어 가이드)

> **참고**: 이 문서는 [README.md](README.md) 영문판의 한국어 번역본입니다.

엔터프라이즈급 CI/CD 파이프라인을 갖춘 KT Cloud Load Balancer 모니터링을 위한 Prometheus Exporter입니다.

## 🚀 빠른 시작

### 사전 요구사항
- Docker
- Kubernetes 클러스터
- KT Cloud 계정 (API 접근 권한)
- GitHub 계정 (CI/CD용)

### 로컬 개발 환경 구성
```bash
# 저장소 복제
git clone <repository-url>
cd ktcloud-api

# 종속성 설치
cd my-k8s-project/lb-exporter
pip install -r requirements.txt

# 환경 변수 설정
export CLOUD_ID=your_cloud_id
export CLOUD_PASSWORD=your_password  
export CLOUD_ZONE=DX-M1

# Exporter 실행
python lb-exporter.py
```

### 빠른 배포
```bash
# 개발 환경 배포
./scripts/deploy.sh dev deploy

# GitOps용 ArgoCD 설치
./scripts/setup-argocd.sh install

# ArgoCD로 배포
./scripts/deploy.sh staging argocd
```

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub        │    │   ArgoCD        │    │   Kubernetes    │
│   Actions       │───▶│   GitOps        │───▶│   Cluster       │
│   (CI)          │    │   (CD)          │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   lb-exporter   │
                                              │   Pod           │
                                              └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   KT Cloud      │
                                              │   Load          │
                                              │   Balancers     │
                                              └─────────────────┘
```

## ✨ 주요 기능

### 모니터링 기능
- **실시간 LB 모니터링**: 로드밸런서 상태 및 성능 추적
- **서버 레벨 메트릭**: 개별 백엔드 서버 상태 및 성능
- **멀티 존 지원**: 다양한 KT Cloud 존 모니터링
- **Prometheus 통합**: 네이티브 Prometheus 메트릭 내보내기

### CI/CD 파이프라인
- **GitHub Actions**: 자동화된 테스트, 빌드, 배포
- **ArgoCD**: GitOps 기반 지속적 배포
- **보안 스캔**: 포괄적인 취약점 스캔
- **멀티 환경**: 개발, 스테이징, 프로덕션 환경

### 보안 기능
- **시크릿 관리**: Kubernetes 시크릿을 통한 자격증명 저장
- **RBAC**: 역할 기반 접근 제어
- **보안 스캔**: 컨테이너 및 종속성 취약점 스캔
- **네트워크 정책**: 안전한 파드 간 통신

## 🌐 지원되는 KT Cloud 존
- DX-M1
- DX-Central
- DX-DCN-CJ
- DX-G
- DX-G-YS

## 📊 모니터링 메트릭

Exporter는 14개의 포괄적인 메트릭을 제공합니다:

| 메트릭 | 설명 |
|--------|------|
| `ktcloud_lb_total_count` | 총 로드밸런서 수 |
| `ktcloud_lb_info` | 로드밸런서 정보 및 상태 |
| `ktcloud_lb_server_count` | LB당 서버 수 |
| `ktcloud_lb_server_state` | 개별 서버 상태 |
| `ktcloud_server_current_connections` | 서버당 현재 연결 수 |
| `ktcloud_server_throughput_rate_kbps` | 서버 처리량 |
| `ktcloud_server_avg_ttfb_ms` | 평균 첫 바이트 응답 시간 |
| `ktcloud_server_requests_rate_per_sec` | 서버당 초당 요청 수 |

## 🔄 CI/CD 워크플로우

### GitHub Actions 파이프라인
1. **코드 품질**: 린팅, 포맷팅, 보안 스캔
2. **테스트**: 단위 테스트 및 통합 테스트
3. **빌드**: Docker 이미지 빌드 및 푸시
4. **보안**: 컨테이너 취약점 스캔
5. **배포**: 개발/스테이징 환경 자동 배포

### ArgoCD GitOps
1. **저장소 동기화**: GitOps 저장소 변경사항 모니터링
2. **애플리케이션 동기화**: Kubernetes에 변경사항 배포
3. **헬스 체크**: 배포 상태 확인
4. **롤백**: 실패 시 자동 롤백

## 🏭 환경 구성

### 개발 환경 (Development)
- **네임스페이스**: `monitoring-dev`
- **레플리카**: 1개
- **리소스**: 50m CPU, 64Mi 메모리
- **자동 동기화**: 활성화

### 스테이징 환경 (Staging)
- **네임스페이스**: `monitoring-staging`
- **레플리카**: 1개
- **리소스**: 100m CPU, 128Mi 메모리
- **자동 동기화**: 활성화

### 프로덕션 환경 (Production)
- **네임스페이스**: `monitoring-prod`
- **레플리카**: 2개
- **리소스**: 200m CPU, 256Mi 메모리
- **자동 동기화**: 수동 승인 필요

## 🛠️ 시작하기

### 1단계: GitHub 저장소 설정
```bash
# 이 저장소를 포크하기
# GitHub에 필요한 시크릿 추가:
# - REGISTRY_USERNAME
# - REGISTRY_PASSWORD
# - GITOPS_REPO
# - GITOPS_TOKEN
```

### 2단계: Kubernetes 클러스터 구성
```bash
# ArgoCD 설치
./scripts/setup-argocd.sh install

# 네임스페이스 생성
kubectl create namespace monitoring-dev
kubectl create namespace monitoring-staging
kubectl create namespace monitoring-prod
```

### 3단계: 애플리케이션 배포
```bash
# 개발 환경 배포
./scripts/deploy.sh dev deploy

# 스테이징 환경 배포
./scripts/deploy.sh staging argocd

# 프로덕션 환경 배포 (수동 승인 필요)
./scripts/deploy.sh prod argocd
```

### 4단계: 애플리케이션 모니터링
```bash
# 배포 상태 확인
./scripts/deploy.sh prod check

# ArgoCD UI 접속
./scripts/setup-argocd.sh port-forward
# https://localhost:8080 열기

# 메트릭 확인
kubectl port-forward -n monitoring-prod svc/lb-exporter 9105:9105
curl http://localhost:9105/metrics
```

## 📚 문서

- [CLAUDE.md](CLAUDE.md) - 포괄적인 개발 가이드 (영문)
- [CI/CD 파이프라인](.github/workflows/) - GitHub Actions 워크플로우
- [Kubernetes 매니페스트](k8s-manifests/) - 배포 구성
- [ArgoCD 애플리케이션](k8s-manifests/argocd-apps/) - GitOps 애플리케이션
- [배포 가이드](docs/DEPLOYMENT_GUIDE.md) - 상세 배포 절차

## 🔒 보안

- 모든 컨테이너 이미지는 취약점 스캔됨
- Kubernetes 보안 컨텍스트 적용
- 접근 제어를 위한 RBAC 구현
- 저장 시 시크릿 암호화
- 파드 통신 제한을 위한 네트워크 정책

## 🤝 기여하기

1. 저장소를 포크하기
2. 기능 브랜치 생성
3. 변경사항 구현
4. 테스트 실행: `./scripts/test.sh`
5. Pull Request 제출

## 📄 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 LICENSE 파일을 참조하세요.

## 🆘 지원

질문이나 지원이 필요하시면:
- GitHub 저장소에 이슈 생성
- [CLAUDE.md](CLAUDE.md)의 트러블슈팅 섹션 확인
- ArgoCD 애플리케이션 로그 검토

## 📞 문의

- **프로젝트 관리자**: KT Cloud 모니터링 팀
- **기술 지원**: [CLAUDE.md](CLAUDE.md) 트러블슈팅 가이드 참조
- **버그 리포트**: GitHub Issues 활용

---

> **💡 팁**: 영문 원본 문서 [README.md](README.md)도 함께 참조하시기 바랍니다.