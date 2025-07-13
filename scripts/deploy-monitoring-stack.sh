#!/bin/bash

# 모니터링 스택 배포 스크립트
# Usage: ./scripts/deploy-monitoring-stack.sh <environment>
# Example: ./scripts/deploy-monitoring-stack.sh dev

set -euo pipefail

ENVIRONMENT=${1:-""}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 도움말 표시
show_help() {
    cat << EOF
KT Cloud 모니터링 스택 배포 스크립트

사용법:
    $0 <environment>

환경:
    dev         개발 환경에 배포
    staging     스테이징 환경에 배포  
    prod        프로덕션 환경에 배포

예시:
    $0 dev          # 개발 환경 배포
    $0 staging      # 스테이징 환경 배포
    $0 prod         # 프로덕션 환경 배포

접속 정보:
    dev:     http://dev.grafana.devtron.click:30080
    staging: http://staging.grafana.devtron.click:30080
    prod:    http://prod.grafana.devtron.click:30080

    Credentials: admin / {Environment}Admin123
EOF
}

# 환경 검증
validate_environment() {
    case "$ENVIRONMENT" in
        dev|staging|prod)
            log_info "배포 환경: $ENVIRONMENT"
            ;;
        *)
            log_error "잘못된 환경입니다. dev, staging, prod 중 하나를 선택하세요."
            show_help
            exit 1
            ;;
    esac
}

# 필수 도구 확인
check_prerequisites() {
    log_info "필수 도구 확인 중..."
    
    local missing_tools=()
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if ! command -v helm &> /dev/null; then
        missing_tools+=("helm")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "다음 도구들이 필요합니다: ${missing_tools[*]}"
        exit 1
    fi
    
    log_success "필수 도구 확인 완료"
}

# Helm 레포지토리 설정
setup_helm_repos() {
    log_info "Helm 레포지토리 설정 중..."
    
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    log_success "Helm 레포지토리 설정 완료"
}

# 네임스페이스 생성 및 라벨 설정
create_namespace() {
    local namespace="monitoring-${ENVIRONMENT}"
    
    log_info "네임스페이스 생성 중: $namespace"
    
    kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
    kubectl label namespace "$namespace" name="$namespace" --overwrite
    
    log_success "네임스페이스 생성 완료: $namespace"
}

# lb-exporter account2 배포
deploy_lb_exporter_account2() {
    log_info "lb-exporter account2 배포 중..."
    
    local env_dir="${PROJECT_ROOT}/environments/monitoring/${ENVIRONMENT}"
    
    kubectl apply -f "${env_dir}/lb-exporter-account2-secret.yaml"
    kubectl apply -f "${env_dir}/lb-exporter-account2-deployment.yaml"
    kubectl apply -f "${env_dir}/lb-exporter-account2-service.yaml"
    
    log_success "lb-exporter account2 배포 완료"
}

# Prometheus + Grafana 스택 배포
deploy_monitoring_stack() {
    log_info "Prometheus + Grafana 스택 배포 중..."
    
    local namespace="monitoring-${ENVIRONMENT}"
    local release_name="prometheus-${ENVIRONMENT}"
    local values_file="${PROJECT_ROOT}/environments/monitoring/${ENVIRONMENT}/prometheus-values-${ENVIRONMENT}.yaml"
    
    helm upgrade --install "$release_name" prometheus-community/kube-prometheus-stack \
        -f "$values_file" \
        -n "$namespace" \
        --wait --timeout=10m
    
    log_success "모니터링 스택 배포 완료"
}

# Grafana 인그레스 적용
apply_ingress() {
    log_info "Grafana 인그레스 적용 중..."
    
    local ingress_file="${PROJECT_ROOT}/environments/monitoring/${ENVIRONMENT}/grafana-ingress.yaml"
    
    kubectl apply -f "$ingress_file"
    
    log_success "Grafana 인그레스 적용 완료"
}

# 배포 상태 확인
check_deployment() {
    log_info "배포 상태 확인 중..."
    
    local namespace="monitoring-${ENVIRONMENT}"
    
    # Pod 상태 확인
    echo ""
    log_info "Pod 상태:"
    kubectl get pods -n "$namespace"
    
    echo ""
    log_info "Service 상태:"
    kubectl get svc -n "$namespace"
    
    echo ""
    log_info "Ingress 상태:"
    kubectl get ingress -n "$namespace"
    
    echo ""
}

# 접속 정보 표시
show_access_info() {
    local password
    case "$ENVIRONMENT" in
        dev) password="DevAdmin123" ;;
        staging) password="StagingAdmin123" ;;
        prod) password="ProdAdmin123" ;;
    esac
    
    cat << EOF

🎉 배포가 완료되었습니다!

📊 Grafana 접속 정보:
   URL: http://${ENVIRONMENT}.grafana.devtron.click:30080
   계정: admin
   비밀번호: ${password}

📈 사용 가능한 대시보드:
   • KT Cloud Account - ALL
   • KT Cloud LB Dashboard - ktcloud_test (DX-M1)
   • KT Cloud LB Dashboard - semascrd_d019_gov (DX-G-YS)

🔍 모니터링 대상:
   • KT Cloud Load Balancer 상태
   • 서버 연결 상태 및 성능 메트릭
   • Zone별 LB 분포 및 통계

EOF
}

# 메인 실행 함수
main() {
    if [ "$ENVIRONMENT" = "-h" ] || [ "$ENVIRONMENT" = "--help" ] || [ -z "$ENVIRONMENT" ]; then
        show_help
        exit 0
    fi
    
    log_info "KT Cloud 모니터링 스택 배포 시작"
    
    validate_environment
    check_prerequisites
    setup_helm_repos
    create_namespace
    deploy_lb_exporter_account2
    deploy_monitoring_stack
    apply_ingress
    check_deployment
    show_access_info
    
    log_success "모니터링 스택 배포 완료!"
}

# 스크립트 실행
main "$@"