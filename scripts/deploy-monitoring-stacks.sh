#!/bin/bash

# KT Cloud API Monitoring Stack Deployment Script
# Prometheus + Grafana 환경별 배포 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Helm이 설치되어 있는지 확인
check_helm() {
    if ! command -v helm &> /dev/null; then
        log_error "Helm이 설치되어 있지 않습니다. 먼저 Helm을 설치해주세요."
        log_info "Helm 설치: ./get_helm.sh"
        exit 1
    fi
    log_info "Helm 버전: $(helm version --short)"
}

# Prometheus Community Helm Repository 추가
add_prometheus_repo() {
    log_info "Prometheus Community Helm Repository 추가중..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    log_success "Prometheus Community Repository 추가 완료"
}

# 네임스페이스별 Prometheus + Grafana 배포
deploy_monitoring_stack() {
    local env=$1
    local namespace="monitoring-${env}"
    local values_file="kubernetes-manifests/prometheus-values-${env}.yaml"
    
    log_info "[$env] 환경의 모니터링 스택 배포 시작..."
    
    # 네임스페이스 생성
    log_info "[$env] 네임스페이스 '$namespace' 생성중..."
    kubectl create namespace $namespace --dry-run=client -o yaml | kubectl apply -f -
    
    # Prometheus + Grafana 배포
    log_info "[$env] Prometheus + Grafana 배포중..."
    helm upgrade --install prometheus-$env prometheus-community/kube-prometheus-stack \
        -f $values_file \
        -n $namespace \
        --wait \
        --timeout=10m
    
    log_success "[$env] 모니터링 스택 배포 완료"
    
    # 배포 상태 확인
    log_info "[$env] 배포 상태 확인중..."
    kubectl get pods -n $namespace
    
    # 서비스 정보 출력
    log_info "[$env] 서비스 정보:"
    kubectl get svc -n $namespace | grep -E "(prometheus|grafana|alertmanager)"
}

# lb-exporter 배포 (kustomize 사용)
deploy_lb_exporter() {
    local env=$1
    
    log_info "[$env] lb-exporter 배포중..."
    kubectl apply -k k8s-manifests/overlays/$env
    log_success "[$env] lb-exporter 배포 완료"
}

# 배포 상태 확인
check_deployment_status() {
    local env=$1
    local namespace="monitoring-${env}"
    
    log_info "[$env] 전체 배포 상태 확인..."
    
    echo -e "\n${BLUE}=== [$env] Pods Status ===${NC}"
    kubectl get pods -n $namespace
    
    echo -e "\n${BLUE}=== [$env] Services Status ===${NC}"
    kubectl get svc -n $namespace
    
    echo -e "\n${BLUE}=== [$env] Ingress Status ===${NC}"
    kubectl get ingress -n $namespace 2>/dev/null || echo "No ingress found"
    
    # Grafana 접속 정보 출력
    local grafana_service=$(kubectl get svc -n $namespace | grep grafana | grep -v headless | awk '{print $1}')
    if [ ! -z "$grafana_service" ]; then
        log_info "[$env] Grafana 접속 방법:"
        case $env in
            dev)
                echo "  URL: http://dev.grafana.devtron.click"
                ;;
            staging)
                echo "  URL: http://staging.grafana.devtron.click"
                ;;
            prod)
                echo "  URL: http://prod.grafana.devtron.click"
                ;;
        esac
        echo "  Port-forward: kubectl port-forward -n $namespace svc/$grafana_service 3000:80"
        echo "  ID: admin / PW: 각 환경별 values 파일 참조"
    fi
}

# 사용법 출력
usage() {
    echo "Usage: $0 [COMMAND] [ENVIRONMENT]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Deploy monitoring stack"
    echo "  status    - Check deployment status"
    echo "  delete    - Delete monitoring stack"
    echo "  help      - Show this help"
    echo ""
    echo "Environments:"
    echo "  dev       - Development environment (monitoring-dev)"
    echo "  staging   - Staging environment (monitoring-staging)"
    echo "  prod      - Production environment (monitoring-prod)"
    echo "  all       - All environments"
    echo ""
    echo "Examples:"
    echo "  $0 deploy dev"
    echo "  $0 deploy all"
    echo "  $0 status staging"
    echo "  $0 delete prod"
}

# 모니터링 스택 삭제
delete_monitoring_stack() {
    local env=$1
    local namespace="monitoring-${env}"
    
    log_warning "[$env] 모니터링 스택 삭제 확인"
    read -p "[$env] 환경의 모니터링 스택을 삭제하시겠습니까? (y/N): " confirm
    
    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
        log_info "[$env] lb-exporter 삭제중..."
        kubectl delete -k k8s-manifests/overlays/$env --ignore-not-found=true
        
        log_info "[$env] Prometheus + Grafana 삭제중..."
        helm uninstall prometheus-$env -n $namespace --ignore-not-found
        
        log_info "[$env] 네임스페이스 삭제중..."
        kubectl delete namespace $namespace --ignore-not-found=true
        
        log_success "[$env] 모니터링 스택 삭제 완료"
    else
        log_info "[$env] 삭제 취소됨"
    fi
}

# 메인 함수
main() {
    local command=$1
    local env=$2
    
    # 명령어 체크
    if [ -z "$command" ]; then
        usage
        exit 1
    fi
    
    # Helm 체크 (delete 명령어가 아닌 경우)
    if [ "$command" != "help" ] && [ "$command" != "delete" ]; then
        check_helm
        add_prometheus_repo
    fi
    
    case $command in
        deploy)
            if [ -z "$env" ]; then
                log_error "환경을 지정해주세요: dev, staging, prod, all"
                exit 1
            fi
            
            if [ "$env" == "all" ]; then
                for e in dev staging prod; do
                    deploy_monitoring_stack $e
                    deploy_lb_exporter $e
                    echo ""
                done
                log_success "모든 환경 배포 완료"
            else
                deploy_monitoring_stack $env
                deploy_lb_exporter $env
                check_deployment_status $env
            fi
            ;;
        status)
            if [ -z "$env" ]; then
                log_error "환경을 지정해주세요: dev, staging, prod, all"
                exit 1
            fi
            
            if [ "$env" == "all" ]; then
                for e in dev staging prod; do
                    check_deployment_status $e
                    echo ""
                done
            else
                check_deployment_status $env
            fi
            ;;
        delete)
            if [ -z "$env" ]; then
                log_error "환경을 지정해주세요: dev, staging, prod, all"
                exit 1
            fi
            
            if [ "$env" == "all" ]; then
                for e in dev staging prod; do
                    delete_monitoring_stack $e
                done
            else
                delete_monitoring_stack $env
            fi
            ;;
        help)
            usage
            ;;
        *)
            log_error "알 수 없는 명령어: $command"
            usage
            exit 1
            ;;
    esac
}

# 스크립트 실행
main "$@"