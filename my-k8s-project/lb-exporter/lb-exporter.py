#!/usr/bin/env python3

# kt Cloud LB Exporter
# Dev environment test - version 1.1.0 (Full CI/CD test)


import os
import time
import logging
import threading
import kcldx as kcl

# New feature: Version endpoint
VERSION = "1.4.0"
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge, Counter, Info
from prometheus_client.core import CollectorRegistry

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 KT Cloud 접속 정보 및 설정값 읽기
CLOUD_ID = os.getenv("CLOUD_ID")  # KT Cloud 계정 ID
CLOUD_PASSWORD = os.getenv("CLOUD_PASSWORD")  # KT Cloud 계정 비밀번호
CLOUD_ZONE = os.getenv("CLOUD_ZONE")  # KT Cloud 존 정보 (예: DX-M1)
EXPORTER_PORT = 9105  # Prometheus 메트릭 노출 포트
SCRAPE_INTERVAL = 60  # 메트릭 수집 주기 (초)

# 로깅 설정 - 시간, 로거명, 레벨, 메시지 형태로 출력
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(name)s-%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AtomicKTCloudLBExporter:
    """
    KT Cloud Load Balancer 정보를 수집하여 Prometheus 메트릭으로 노출하는 익스포터 클래스
    원자적 업데이트 방식을 사용하여 Prometheus 스크랩 중 데이터 일관성을 보장합니다.
    - 데이터 수집과 메트릭 업데이트를 분리
    - 스레드 안전성 보장
    - 메트릭 업데이트 중 충돌 감지 및 처리
    """

    def __init__(self):
        """익스포터 초기화 - 메트릭 정의 및 KT Cloud 연결 설정"""

        # Prometheus 메트릭 레지스트리 생성 (독립적인 메트릭 관리)
        self.registry = CollectorRegistry()

        # 스레드 안전성을 위한 재귀락 (Reentrant Lock)
        # 같은 스레드에서 여러 번 락을 획득할 수 있음
        self.update_lock = threading.RLock()
        # 현재 업데이트 상태 플래그
        self.is_updating = False
        # 메트릭 저장소 (현재 사용되지 않지만 확장성을 위해 유지)
        self.current_metrics = {}
        self.temp_metrics = {}

        # Prometheus 메트릭 정의
        # 1. 전체 LB 개수
        self.lb_count = Gauge(
            "ktcloud_lb_total_count",
            "Total number of load balancers",  # 전체 로드밸런서 개수
            registry=self.registry,
        )

        # 2. LB 기본 정보 (상태, IP, 포트 등)
        self.lb_info = Gauge(
            "ktcloud_lb_info",
            "Load balancer information (value: 1=UP, 0=DOWN)",  # LB 정보 (1=정상, 0=다운)
            [
                "lb_id",
                "lb_name",
                "service_ip",
                "service_port",
                "service_type",
                "lb_option",
                "healthcheck_type",
                "zone",
            ],  # 레이블들
            registry=self.registry,
        )

        # 3. LB별 연결된 서버 개수
        self.lb_server_count = Gauge(
            "ktcloud_lb_server_count",
            "Number of servers connected to load balancer",  # LB에 연결된 서버 수
            ["lb_id", "lb_name", "zone"],
            registry=self.registry,
        )

        # 4. LB 내 개별 서버 상태
        self.lb_server_state = Gauge(
            "ktcloud_lb_server_state",
            "Server state in load balancer (1=UP, 0=DOWN)",  # 서버 상태 (1=정상, 0=다운)
            ["lb_id", "lb_name", "server_ip", "server_port", "zone"],
            registry=self.registry,
        )

        # 서버 성능 메트릭들
        # 5. 서버별 현재 연결 수
        self.server_connections = Gauge(
            "ktcloud_server_current_connections",
            "Current number of connections to the server",  # 서버의 현재 연결 수
            ["lb_id", "lb_name", "server_ip", "server_port", "zone"],
            registry=self.registry,
        )

        # 6. 서버별 처리량 (KB/s)
        self.server_throughput_rate = Gauge(
            "ktcloud_server_throughput_rate_kbps",
            "Server throughput rate in KB/s",  # 서버 처리량 (KB/초)
            ["lb_id", "lb_name", "server_ip", "server_port", "zone"],
            registry=self.registry,
        )

        # 7. 서버별 평균 응답 시간 (TTFB-Time To First Byte)
        self.server_avg_ttfb = Gauge(
            "ktcloud_server_avg_ttfb_ms",
            "Average server Time To First Byte in milliseconds",  # 평균 첫 바이트 응답 시간 (ms)
            ["lb_id", "lb_name", "server_ip", "server_port", "zone"],
            registry=self.registry,
        )

        # 8. 서버별 초당 요청 처리량
        self.server_requests_rate = Gauge(
            "ktcloud_server_requests_rate_per_sec",
            "Server requests rate per second",  # 서버별 초당 요청 수
            ["lb_id", "lb_name", "server_ip", "server_port", "zone"],
            registry=self.registry,
        )

        # 9. 서비스 타입별 LB 개수 (HTTP, HTTPS, TCP 등)
        self.service_type_count = Gauge(
            "ktcloud_lb_service_type_count",
            "Count of load balancers by service type",  # 서비스 타입별 LB 개수
            ["service_type", "zone"],
            registry=self.registry,
        )

        # 익스포터 운영 메트릭들
        # 10. 메트릭 수집 소요 시간
        self.scrape_duration = Gauge(
            "ktcloud_lb_scrape_duration_seconds",
            "Time spent scraping KT Cloud LB metrics",  # 메트릭 수집에 걸린 시간(초)
            registry=self.registry,
        )

        # 11. 마지막 성공적인 수집 시간
        self.last_scrape_timestamp = Gauge(
            "ktcloud_lb_last_scrape_timestamp",
            "Timestamp of last successful scrape",  # 마지막 성공 수집 타임스탬프
            registry=self.registry,
        )

        # 12. 업데이트 충돌 발생 횟수 (Prometheus 스크랩과 충돌)
        self.update_conflicts = Counter(
            "ktcloud_lb_update_conflicts_total",
            "Number of times Prometheus scraped during metric updates",  # 업데이트 중 충돌 횟수
            registry=self.registry,
        )

        # 13. 성공적인 원자적 업데이트 횟수
        self.atomic_updates = Counter(
            "ktcloud_lb_atomic_updates_total",
            "Number of successful atomic metric updates",  # 성공적인 원자적 업데이트 횟수
            registry=self.registry,
        )

        # 14. 익스포터 정보 (버전, 설정 등)
        self.exporter_info = Info(
            "ktcloud_lb_exporter_info",
            "KT Cloud Load Balancer Exporter Information",  # 익스포터 정보
            registry=self.registry,
        )

        # KT Cloud 연결 초기화
        self.zone_mgr = None  # KT Cloud Zone Manager
        self.network = None  # Network Resource Manager
        self.init_ktcloud_connection()

    def init_ktcloud_connection(self):
        """
        KT Cloud 연결 초기화
        - Zone Manager 생성
        - Network Resource Manager 생성
        - 익스포터 정보 설정
        """
        try:
            logger.info("KT Cloud 연결 초기화 중...")

            # KT Cloud Zone Manager 생성 (인증 및 존 관리)
            self.zone_mgr = kcl.ZoneManager(CLOUD_ID, CLOUD_PASSWORD, CLOUD_ZONE)
            # Network Resource Manager 생성 (LB 관련 API 호출)
            self.network = self.zone_mgr.network_resource()

            # 존 정보 가져오기
            zone, zone_name = self.zone_mgr.get_zone()

            # 익스포터 정보 메트릭 설정
            self.exporter_info.info(
                {
                    "version": "2.6.0",  # 익스포터 버전
                    "zone": zone_name,  # KT Cloud 존 이름
                    "port": str(EXPORTER_PORT),  # 서비스 포트
                    "scrape_interval": str(SCRAPE_INTERVAL),  # 수집 주기
                    "data_source": "KT Cloud SDK Atomic",  # 데이터 소스
                    "description": "Atomic update version to prevent Prometheus scrape conflicts",
                }
            )
            logger.info(f"KT Cloud 연결 성공 - Zone: {zone_name}")
        except Exception as e:
            logger.error(f"KT Cloud 연결 실패: {e}")
            raise

    def collect_data_to_temp(self):
        """
        1단계: 데이터를 임시 저장소에 수집 (메트릭 업데이트 없음)
        KT Cloud API를 호출하여 LB 정보를 수집하지만,
        Prometheus 메트릭은 업데이트하지 않고 임시 저장소에만 보관합니다.
        이렇게 하면 데이터 수집 중에 Prometheus가 스크랩해도 일관된 데이터를 읽을 수 있습니다.
        Returns:
            dict: 수집된 데이터를 담은 딕셔너리
            - lb_list: LB 목록
            - lb_servers: LB별 서버 정보
            - service_type_counts: 서비스 타입별 개수
            - collection_time: 수집 시간
        """
        # 임시 데이터 저장소 초기화
        temp_data = {
            "lb_list": [],  # LB 기본 정보 목록
            "lb_servers": {},  # LB별 서버 상세 정보
            "service_type_counts": {},  # 서비스 타입별 카운트
            "collection_time": time.time(),  # 수집 시작 시간
        }
        logger.info("임시 저장소에 데이터 수집 시작")

        # 1. LB 목록 조회 (KT Cloud API 호출)
        lb_list = self.network.list_lb_info()
        if not lb_list:
            logger.warning("LB 목록이 비어있습니다.")
            return temp_data

        temp_data["lb_list"] = lb_list
        logger.info(f"LB {len(lb_list)}개 발견")

        # 2. 각 LB별 상세 정보 수집
        zone, zone_name = self.zone_mgr.get_zone()
        service_type_counts = {}

        # 각 LB에 대해 반복 처리
        for i, lb in enumerate(lb_list):
            try:
                lb_name = lb["lb_name"]  # LB 이름
                lb_id = lb["lb_id"]  # LB ID
                service_type = lb["service_type"]  # 서비스 타입 (HTTP, HTTPS, TCP 등)

                # 서비스 타입별 개수 카운트
                service_type_counts[service_type] = (
                    service_type_counts.get(service_type, 0) + 1
                )

                # 해당 LB에 연결된 서버 정보 조회
                servers = self.network.list_lb_server(lb_id)
                temp_data["lb_servers"][lb_id] = servers if servers else []
                logger.debug(
                    f"LB {i+1}/{len(lb_list)} '{lb_name}': {len(servers) if servers else 0}개 서버"
                )
            except Exception as e:
                # 특정 LB 처리 실패 시 빈 서버 목록으로 처리하고 계속 진행
                logger.error(f"LB {lb.get('lb_name', 'Unknown')} 데이터 수집 실패: {e}")
                temp_data["lb_servers"][lb_id] = []

        temp_data["service_type_counts"] = service_type_counts
        logger.info("임시 데이터 수집 완료")

        return temp_data

    def atomic_update_metrics(self, temp_data):
        """
        2단계: 수집된 데이터를 원자적으로 메트릭에 업데이트
        임시 저장소의 데이터를 실제 Prometheus 메트릭으로 업데이트합니다.
        락을 사용하여 업데이트 중에는 다른 스레드가 접근하지 못하도록 하고,
        모든 메트릭을 한 번에 업데이트하여 일관성을 보장합니다.
        Args:
            temp_data (dict): collect_data_to_temp()에서 수집된 데이터
        """
        update_start = time.time()

        # 락 획득 시도 (non-blocking)
        if not self.update_lock.acquire(blocking=False):
            # 락 획득 실패 시 (다른 스레드가 업데이트 중)
            logger.warning("메트릭 업데이트 중 충돌 감지 - 대기")
            self.update_conflicts.inc()  # 충돌 카운터 증가
            self.update_lock.acquire()  # 블로킹 모드로 대기

        try:
            self.is_updating = True
            logger.debug("메트릭 원자적 업데이트 시작")

            # 모든 메트릭 초기화 (이전 데이터 제거)
            self.lb_info.clear()
            self.lb_server_count.clear()
            self.lb_server_state.clear()
            self.server_connections.clear()
            self.server_throughput_rate.clear()
            self.server_avg_ttfb.clear()
            self.server_requests_rate.clear()
            self.service_type_count.clear()

            # 기본 메트릭 업데이트
            # 전체 LB 개수 설정
            self.lb_count.set(len(temp_data["lb_list"]))

            # 존 정보 가져오기
            zone, zone_name = self.zone_mgr.get_zone()

            # ===LB별 상세 정보 업데이트
            for lb in temp_data["lb_list"]:
                try:
                    # LB 기본 정보 추출
                    lb_id = str(lb["lb_id"])
                    lb_name = lb["lb_name"]
                    service_ip = lb["service_ip"]
                    service_port = str(lb["service_port"])
                    service_type = lb["service_type"]
                    lb_option = lb["lb_option"]  # 로드밸런싱 알고리즘
                    healthcheck_type = lb["healthcheck_type"]  # 헬스체크 방식

                    # LB 상태 변환 ('UP' -> 1, 'DOWN' -> 0)
                    state = 1 if lb["state"] == "UP" else 0

                    # LB 기본 정보 메트릭 설정
                    self.lb_info.labels(
                        lb_id=lb_id,
                        lb_name=lb_name,
                        service_ip=service_ip,
                        service_port=service_port,
                        service_type=service_type,
                        lb_option=lb_option,
                        healthcheck_type=healthcheck_type,
                        zone=zone_name,
                    ).set(state)

                    # 해당 LB의 서버 정보 처리
                    servers = temp_data["lb_servers"].get(lb["lb_id"], [])
                    server_count = len(servers)

                    # LB별 연결된 서버 개수 설정
                    self.lb_server_count.labels(
                        lb_id=lb_id, lb_name=lb_name, zone=zone_name
                    ).set(server_count)

                    # 서버별 상세 정보 처리
                    for server in servers:
                        try:
                            # 서버 기본 정보 추출
                            server_ip = server["vm_ip"]
                            server_port = str(server["vm_port"])

                            # 서버 상태 변환 ('UP' -> 1, 'DOWN' -> 0)
                            server_state = 1 if server["state"] == "UP" else 0

                            # 서버 상태 메트릭 설정
                            self.lb_server_state.labels(
                                lb_id=lb_id,
                                lb_name=lb_name,
                                server_ip=server_ip,
                                server_port=server_port,
                                zone=zone_name,
                            ).set(server_state)

                            # 성능 메트릭 처리
                            def safe_float(value):
                                """안전한 float 변환 함수
                                None, 빈 문자열, 잘못된 형식의 값을 0으로 처리"""
                                try:
                                    return (
                                        float(value)
                                        if value is not None and value != ""
                                        else 0
                                    )
                                except (ValueError, TypeError):
                                    return 0

                            # 성능 지표 추출 및 변환
                            connections = safe_float(
                                server.get("cursrvrconnections", 0)
                            )  # 현재 연결 수
                            throughput = safe_float(
                                server.get("throughputrate", 0)
                            )  # 처리량 (KB/s)
                            ttfb = safe_float(
                                server.get("avgsvrttfb", 0)
                            )  # 평균 TTFB (ms)
                            requests = safe_float(
                                server.get("requestsrate", 0)
                            )  # 초당 요청 수

                            # 성능 메트릭들 설정
                            self.server_connections.labels(
                                lb_id=lb_id,
                                lb_name=lb_name,
                                server_ip=server_ip,
                                server_port=server_port,
                                zone=zone_name,
                            ).set(connections)

                            self.server_throughput_rate.labels(
                                lb_id=lb_id,
                                lb_name=lb_name,
                                server_ip=server_ip,
                                server_port=server_port,
                                zone=zone_name,
                            ).set(throughput)

                            self.server_avg_ttfb.labels(
                                lb_id=lb_id,
                                lb_name=lb_name,
                                server_ip=server_ip,
                                server_port=server_port,
                                zone=zone_name,
                            ).set(ttfb)

                            self.server_requests_rate.labels(
                                lb_id=lb_id,
                                lb_name=lb_name,
                                server_ip=server_ip,
                                server_port=server_port,
                                zone=zone_name,
                            ).set(requests)

                        except Exception as e:
                            logger.error(
                                f"서버 {server.get('vm_ip', 'Unknown')} 메트릭 설정 실패: {e}"
                            )

                except Exception as e:
                    logger.error(
                        f"LB {lb.get('lb_name', 'Unknown')} 메트릭 설정 실패: {e}"
                    )

            # 서비스 타입별 카운트 메트릭 설정
            for service_type, count in temp_data["service_type_counts"].items():
                self.service_type_count.labels(
                    service_type=service_type, zone=zone_name
                ).set(count)

            # 익스포터 상태 메트릭 업데이트
            # 마지막 성공적인 수집 시간 기록
            self.last_scrape_timestamp.set(temp_data["collection_time"])

            # 성공적인 원자적 업데이트 카운터 증가
            self.atomic_updates.inc()

            # 업데이트 소요 시간 계산 및 로깅
            update_duration = time.time() - update_start
            logger.info(f"원자적 업데이트 완료 - 소요시간: {update_duration:.3f} 초")

        finally:
            # 락 해제 및 상태 플래그 초기화 (예외 발생 시에도 실행됨)
            self.is_updating = False
            self.update_lock.release()

    def collect_metrics(self):
        """
        메트릭 수집 메인 함수 - 2단계 프로세스로 구성
        1단계: 데이터 수집 (KT Cloud API 호출)
        2단계: 원자적 메트릭 업데이트 (Prometheus 메트릭 갱신)
        이렇게 분리함으로써 Prometheus 스크랩 중에도 일관된 데이터를 제공할 수 있습니다.
        """
        start_time = time.time()

        try:
            logger.info("메트릭 수집 시작")
            # 1단계: 데이터 수집 (메트릭 업데이트 없음)
            temp_data = self.collect_data_to_temp()

            # LB가 없는 경우 처리
            if not temp_data["lb_list"]:
                self.lb_count.set(0)
                return

            collection_duration = time.time() - start_time
            logger.info(f"데이터 수집 완료 - 소요시간: {collection_duration:.3f}초")

            # 2단계: 원자적 메트릭 업데이트
            self.atomic_update_metrics(temp_data)

            # 전체 소요 시간 기록 (메트릭으로 노출)
            total_duration = time.time() - start_time
            self.scrape_duration.set(total_duration)
            logger.info(f"전체 메트릭 처리 완료 - 총 소요시간: {total_duration:.3f} 초")

        except Exception as e:
            logger.error(f"메트릭 수집 중 오류: {e}")
            raise

    def run(self):
        """
        익스포터 메인 실행 루프
        - Prometheus HTTP 서버 시작
        - 주기적으로 메트릭 수집 및 업데이트
        - 예외 처리 및 재시도 로직
        """
        logger.info(
            f"KT Cloud LB Exporter (Atomic Version) 시작 - 포트: {EXPORTER_PORT}"
        )
        logger.info("원자적 메트릭 업데이트로 Prometheus 스크랩 충돌 방지")

        # Prometheus HTTP 서버 시작 (메트릭 노출용)
        start_http_server(EXPORTER_PORT, registry=self.registry)
        logger.info(f"메트릭 서버 시작: http://localhost:{EXPORTER_PORT}/metrics")

        # 메인 실행 루프
        while True:
            try:
                cycle_start = time.time()

                # 메트릭 수집 실행
                self.collect_metrics()

                # 다음 수집까지의 대기 시간 계산
                elapsed = time.time() - cycle_start
                sleep_time = max(0, SCRAPE_INTERVAL - elapsed)

                if sleep_time > 0:
                    logger.info(f"다음 수집까지 {sleep_time:.1f} 초 대기")
                    time.sleep(sleep_time)
                else:
                    # 수집 시간이 설정된 주기를 초과한 경우 경고
                    logger.warning(f"수집 시간이 수집 주기를 초과: {elapsed:.1f}초")

            except KeyboardInterrupt:
                # 사용자가 Ctrl+C로 중단한 경우
                logger.info("사용자 중단 요청")
                break
            except Exception as e:
                # 예상치 못한 오류 발생 시 10초 후 재시도
                logger.error(f"예상치 못한 오류: {e}")
                logger.info("10초 후 재시도...")
                time.sleep(10)


def main():
    """메인 함수 - 프로그램 진입점
    환경 변수 검증 후 익스포터 실행
    """
    # 필수 환경 변수 존재 여부 확인
    if not all([CLOUD_ID, CLOUD_PASSWORD, CLOUD_ZONE]):
        logger.error("환경 변수 누락: CLOUD_ID, CLOUD_PASSWORD, CLOUD_ZONE")
        return

    # 익스포터 인스턴스 생성 및 실행
    exporter = AtomicKTCloudLBExporter()
    exporter.run()


# 스크립트가 직접 실행될 때만 main() 함수 호출
if __name__ == "__main__":
    main()
# CI/CD 2nd Test - Full Pipeline Validation - 2025-07-12 01:35:00
