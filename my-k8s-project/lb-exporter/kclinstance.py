###############################################################################################
# 
# Copyright (c) 2024 kt cloud, All rights reserved.
#
# kclinstance.py v0.5.2
# Released on 2025.6.17
# Instance 단위로 제어하기 위한 class 제공
#
# VMInstance : 생성된 VM 제어
# VolumeInstance : 생성된 Volume 제어
# WaiterVMInstance : vm 생성에 시간이 소요되는 자원에 대해 생성 완료까지 대기하는 api제공
# WaiterVolumeInstance : volume 생성에 시간이 소요되는 자원에 대해 생성 완료까지 대기하는 api제공
# PublicIPInstance : 생성된 공인IP주소 제어, port forward, static nat 제어
# NASInstance : 생성된 NAS Volume 제어
# BoxInstance : object storage에서 생성된 box 제어, file upload/download 등
# LBInstance : 생성된 LB 제어
#
###############################################################################################

import kclutil as ku
from kclutil import FileSizeError

VM_STATE_LIST = ["vm_active", "vm_shutoff"]
VOLUME_STATE_LIST = ["volume_available", "volume_inuse", "nas_available"]
METRIC_LIST = ["CPUUtilization", "DiskReadBytes", "DiskWriteBytes", "NetworkInbound", "NetworkOutbound", "MemoryUsage", "MemoryTarget", "MemoryInternalFree"]
MAX_COUNT = 30

###################################################
#
# class VMInstance
# 생성된 VM instance에 대한 제어 및 관리를 위한 api 제공
#
###################################################

class VMInstance:
    def __init__(self, vm_id, compute):
        self._vm_id = vm_id
        self._compute = compute
        
    @property
    def id(self):
        return self._vm_id
    
    @property
    def info(self):
        return self._compute.get_vm_info(self._vm_id)
    
    # 정지된 vm 재기동
    def start(self):
        return self._compute.start_vm(self._vm_id)
    
    # 기동중인 vm 정지
    def stop(self):
        return self._compute.stop_vm(self._vm_id)
    
    # vm 삭제, 기동중인 상태에서도 가능
    def delete(self, forced=False):
        return self._compute.delete_vm(self._vm_id, forced)
    
    # vm의 스팩 정보 변경, 기동중인 상태에서도 가능
    def change(self, flavor_id):
        return self._compute.change_vm(self._vm_id, flavor_id)
    
    # 추가 Disk를 vm에 연결
    def attach_volume(self, volume_id):
        return self._compute.attach_volume(self._vm_id, volume_id)
    
    # vm에 연결된 추가 Disk를 연결 해제
    def detach_volume(self, volume_id):
        return self._compute.detach_volume(self._vm_id, volume_id)
    
    # vm에 연결되어 있는 vm의 목록 제공
    def get_attached_volume(self):
        return self._compute.get_attached_volume(self._vm_id)
    
    # vm의 private ip 제공
    # 처음 연결된 subnet의 private ip로 Private Subnet의 ip는 아님
    def get_privateip(self):
        info = self._compute.get_vm_info(self._vm_id)
        return info["subnets"][0]["privateip"]
    
    # ACTIVE(서버 기동)상태까지 기다림
    def wait_until_active(self):
        waiter = self._compute.waiter_instance("vm_active")
        waiter.wait([self._vm_id])
    
    # SHUTOFF(서버 정지) 상태까지 기다림
    def wait_until_shutoff(self):
        waiter = self._compute.waiter_instance("vm_shutoff")
        waiter.wait([self._vm_id])
        
    # Metric 조회
    def get_metric_info(self, metric_name, period, term):
        if metric_name not in METRIC_LIST:
            msg = f"""'{metric_name}은 잘못된 metric name입니다.'"""
            raise Exception(msg)
            
        if period != "1min" and period != "5min":
            msg = f"""period는 '1min', '5min'만 가능합니다.'"""
            raise Exception(msg)
            
        if term < 1 or term > 1440:
            msg = f"""term은 1~1440(min)만 가능합니다.'"""
            raise Exception(msg)
            
        params = {}
        params["namespace"] = "ucloudserver"
        params["metricName"] = metric_name
        params["statisticType"] = "Average" # average로 계산
        params["period"] = period
        params["term"] = f"{term}min"
        params["dimension.name"] = "id"
        params["dimension.value"] = self._vm_id
        
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        
        res = self._compute.get_metric_info(query_string)
        
        if res["status"] == "success":
            return res["data"]["result"][0]["values"]
        
        return None

###################################################
#
# class VolumeInstance
# 생성된 Volume instance의 제어 및 관리 수행
# 
###################################################

class VolumeInstance:
    def __init__(self, volume_id, bootable, storage):
        self._volume_id = volume_id
        self._storage = storage
        self._bootable = bootable
        
    @property
    def id(self):
        return self._volume_id
    
    @property
    def info(self):
        return self._storage.get_volume_info(self._volume_id)
    
    # vloume 삭제
    def delete(self):
        return self._storage.delete_volume(self._volume_id)
    
    # volume 기반으로 image 생성, bootable volume만 가능
    def create_image(self, name):
        if self._bootable:
            return self._storage.create_image(name, self._volume_id)
     
    # volume 기반으로 snapshot 생성
    def create_snapshot(self, name, description=None):
        return self._storage.create_snapshot(name, self._volume_id, description)
    
    # available(볼륨 생성 또는 서버 연결 해제)상태까지 기다림
    def wait_until_available(self):
        waiter = self._storage.waiter_instance("volume_available")
        waiter.wait([self._volume_id])
    
    # in-use(서버에 연결) 상태까지 기다림
    def wait_until_inuse(self):
        waiter = self._storage.waiter_instance("volume_inuse")
        waiter.wait([self._volume_id])

###################################################
#
# class WaiterVMInstance
# VM 생성 등 상태 변경에 시간이 오래 소요되는 자원에 대한 waiting
#
###################################################

class WaiterVMInstance:
    def __init__(self, dest_state, compute):
        self._compute = compute
        self._dest_state = ""
        self.set_dest_state(dest_state)
          
    # 목적 상태 지정
    def set_dest_state(self, dest_state):
        self._dest_state = dest_state
        
        if dest_state in VM_STATE_LIST:
            return None
        else:
            raise Exception(f"'{dest_state}' is incorrect state")
        
    # 자원의 상태가 목적 상태가 될 때까지 waiting
    # 대상을 list 형태로 제공
    def wait(self, instance_ids):
        count = 0
        
        while True:
            count += 1
            vm_list = self._compute.list_vm_info()
            state = ku.wait_vm_state(instance_ids, vm_list, self._dest_state)
            if state == "SUCCESS":
                return True
            elif state == "ERROR":
                return False 
            if count > MAX_COUNT:
                return False
            
###################################################
#
# class WaiterVolumeInstance
# Volume, NAS 생성 등 상태 변경에 시간이 오래 소요되는 자원에 대한 waiting
#
###################################################

class WaiterVolumeInstance:
    def __init__(self, dest_state, storage):
        self._storage = storage
        self._dest_state = ""
        self.set_dest_state(dest_state)
          
    # 목적 상태 지정
    def set_dest_state(self, dest_state):
        self._dest_state = dest_state
        
        if dest_state in VOLUME_STATE_LIST:
            return None
        else:
            raise Exception(f"'{dest_state}' is incorrect state")
    
    # 자원의 상태가 목적 상태가 될 때까지 waiting
    # 대상을 list 형태로 제공
    def wait(self, instance_ids):
        count = 0
        
        while True:
            count += 1
            volume_list = []
            if self._dest_state == "nas_available":
                volume_list = self._storage.list_nas_info()
            else:
                volume_list = self._storage.list_volume_info()
            if ku.wait_volume_state(instance_ids, volume_list, self._dest_state):
                return True
                
            if count > MAX_COUNT:
                return False
            
###################################################
#
# class PublicIPInstance
# 생성된 공인IP의 제어 및 관리 수행
#
###################################################

class PublicIPInstance:
    def __init__(self, publicip_id, publicip, network):
        self._network = network
        self._publicip_id = publicip_id
        self._publicip = publicip
    
    @property
    def id(self):
        return self._publicip_id
    
    @property
    def ip(self):
        return self._publicip
    
    @property
    def info(self):
        return self._network.get_publicip_info(self._publicip_id)
    
    # 공인ip 삭제
    # portforward, static nat 설정되어 있는 경우 삭제되지 않음
    def delete(self):
        return self._network.delete_publicip(self._publicip_id)
    
    # port forward 설정
    def set_portforward(self, privateip, private_port, public_port, protocol):
        return self._network.set_portforward(privateip, self._publicip_id, private_port, public_port, protocol)
    
    # port forward 설정 해제
    def unset_portforward(self, portforward_id):
        return self._network.unset_portforward(portforward_id)
    
    # port forward 설정 정보 조회
    def get_portforward_info(self):
        return self._network.get_portforward_info_of_publicip(self._publicip)
    
    # static nat 설정
    def set_staticnat(self, privateip):
        # subnet_id = self._network.get_subnet_id_of_privateip(privateip)
        return self._network.set_staticnat(privateip, self._publicip_id)
    
    # static nat 설정 해제
    def unset_staticnat(self, staticnat_id):
        return self._network.unset_staticnat(staticnat_id)
    
    # static nat 설정 정보 조회
    def get_staticnat_info(self):
        return self._network.get_staticnat_info_of_publicip(self._publicip)
        
###################################################
#
# class NASInstance
# 생성된 NAS Volume의 제어 및 관리 수행
#
###################################################

class NASInstance:
    def __init__(self, nas_id, storage):
        self._nas_id = nas_id
        self._storage = storage
        
    @property
    def id(self):
        return self._nas_id
    
    @property
    def info(self):
        return self._storage.get_nas_info(self._nas_id)
    
    # NAS volume 삭제
    def delete(self):
        return self._storage.delete_nas(self._nas_id)
    
    # NAS volume 크기 변경, 최대 10TB, 기존보다 크기를 줄이는 것은 안됨
    def change_size(self, size):
        return self._storage.change_nas_size(self._nas_id, size)
    
    # NAS volume에 접근 가능한 네트워크 및 권한 설정
    def set_access(self, level, cidr):
        return self._storage.set_nas_access(self._nas_id, level, cidr)
    
    # NAS Volume 접근 권한 및 네트워크 정보 조회
    def get_access_info(self):
        return self._storage.get_nas_access_info(self._nas_id)
    
    # NAS Volume 접근 권한 및 네트워크 설정 해제
    def unset_access(self, access_id):
        return self._storage.unset_nas_access(self._nas_id, access_id)
    
    # available(볼륨 생성 또는 서버 연결 해제)상태까지 기다림
    def wait_until_available(self):
        waiter = self._storage.waiter_instance("nas_available")
        waiter.wait([self._nas_id])

###################################################
#
# class BoxInstance
# 생성된 box의 제어 및 관리 수행
#
###################################################

class BoxInstance:
    def __init__(self, box_name, object_storage):
        self._box_name = box_name
        self._object = object_storage
        
    @property
    def name(self):
        return self._box_name
    
    # box 삭제
    def delete(self):
        return self._object.delete_box(self._box_name)
    
    # box내 file 목록 조회
    def list_file(self):
        return self._object.list_box_file(self._box_name)
    
    # box내 대상 file 삭제
    def delete_file(self, key_name):
        return self._object.delete_box_file(self._box_name, key_name)
    
    # box내 대상 file 다운로드
    def download_file(self, key_name):
        return self._object.download_box_file(self._box_name, key_name)
    
    # box로 파일 업로드 (일정 크기를 넘으면 multipart upload 수행)
    def upload_file(self, file_path, key_name):
        try:
            self._object.multipart_upload(self._box_name, file_path, key_name)
        except FileSizeError:
            self._object.upload_box_file(self._box_name, file_path, key_name)
            

###################################################
#
# class LBInstance
# 생성된 LB instance의 제어 및 관리 수행
#
###################################################

class LBInstance:
    def __init__(self, lb_id, network):
        self._lb_id = lb_id
        self._network = network
        
    @property
    def id(self):
        return self._lb_id
    
    @property
    def info(self):
        res = self._network.list_lb_info(lb_id=self._lb_id)
        if res:
            return res[0]

    def get_usage(self, start_date, end_date):
        info = self.info
        if info:
            lb_name = info["lb_name"]
            usage = self._network.get_lb_usage(lb_name, start_date, end_date)
            if usage:
                return usage
    
    # LB의 private ip (service ip) return
    def get_privateip(self):
        info = self.info
        if info:
            return info["service_ip"]
    
    # LB 삭제
    def delete(self):
        return self._network.delete_lb(self._lb_id)
    
    # LB 설정 정보 업데이트
    def update(self, lb_option=None, healthcheck_type=None, healthcheck_url=None):
        return self._network.update_lb(self._lb_id, lb_option, healthcheck_type, healthcheck_url)
    
    # LB가 부하분산할 서버 추가
    def add_server(self, vm_id, vm_ip, vm_port):
        return self._network.add_lb_server(self._lb_id, vm_id, vm_ip, vm_port)
    
    # LB 부하분산 서버 목록 제공
    def list_server(self):
        return self._network.list_lb_server(self._lb_id)
    
    # LB 부하분산 서버 목록에서 대상 서버 제거
    def remove_server(self, service_id):
        return self._network.remove_lb_server(service_id)
    
    
    
    
        