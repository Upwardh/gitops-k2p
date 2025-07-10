import os
from dotenv import load_dotenv
import kcldx as kcl
import json
import argparse # argparse 모듈 임포트

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 KT Cloud 인증 정보 가져오기
cloud_id = os.getenv("CLOUD_ID")
cloud_password = os.getenv("CLOUD_PASSWORD")
cloud_zone = os.getenv("CLOUD_ZONE")

def get_lb_information(lb_name=None, service_ip=None, lb_id=None):
    """
    KT Cloud 로드밸런서 정보를 조회합니다.
    :param lb_name: 조회할 LB 이름 (선택 사항)
    :param service_ip: 조회할 LB 서비스 IP (선택 사항)
    :param lb_id: 조회할 LB ID (선택 사항)
    """
    try:
        print(f"KT Cloud {cloud_zone} 존에 연결 중...")
        zone_manager = kcl.ZoneManager(cloud_id, cloud_password, cloud_zone)
        network_resource = zone_manager.network_resource()
        print("연결 성공!")

        print("\n로드밸런서 정보 조회 중...")
        # 인자로 받은 값들을 list_lb_info에 전달
        lb_list = network_resource.list_lb_info(lb_name=lb_name, service_ip=service_ip, lb_id=lb_id)

        if not lb_list:
            print("조회 가능한 로드밸런서가 없습니다.")
            return

        print(f"\n총 {len(lb_list)}개의 로드밸런서가 조회되었습니다:")
        for lb in lb_list:
            print(json.dumps(lb, indent=2))
            print("-" * 50) # 구분선

    except Exception as e:
        print(f"오류 발생: {e}")
        print("인증 정보 또는 네트워크 연결을 확인해주세요.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KT Cloud 로드밸런서 정보를 조회합니다.")
    parser.add_argument('--lb_id', type=int, help='조회할 로드밸런서의 ID')
    parser.add_argument('--lb_name', type=str, help='조회할 로드밸런서의 이름')
    # service_ip도 추가할 수 있지만, 여기서는 lb_id와 lb_name에 집중합니다.
    # parser.add_argument('--service_ip', type=str, help='조회할 로드밸런서의 서비스 IP')

    args = parser.parse_args()

    # 인자가 제공되었는지 확인하고 함수 호출
    if args.lb_id:
        print(f"--- LB ID {args.lb_id} 로드밸런서 정보 조회 ---")
        get_lb_information(lb_id=args.lb_id)
    elif args.lb_name:
        print(f"--- LB 이름 '{args.lb_name}' 로드밸런서 정보 조회 ---")
        get_lb_information(lb_name=args.lb_name)
    else:
        print("--- 모든 로드밸런서 정보 조회 (인자 없음) ---")
        get_lb_information() # 인자 없이 호출하여 모든 LB 조회
        
#인자를 통해 호출하는 방법
#LB_ID로 호출 : python get_lb_info.py --lb_id {lb_id 값}
#LB_Name으로 호출 : python get_lb_info.py --lb_name {lb_name 값}