###############################################################################################
# 
# Copyright (c) 2024 kt cloud, All rights reserved.
#
# kcldx.py v0.5.2
# Released on 2025.6.17
# kt cloud DX존의 자원을 제어하기 위한 Python lib 제공
#
# ZoneManager : 제어할 존을 결정 (DX-M1, DX-Central, DX-DCN-CJ, DX-G, DX-G-YS)
# ComputResource : VM 생성 및 제어
# StorageResource : Volume, Image, Snapshot, NAS 등 생성 및 제어
# NetworkResource : Subnet, IP(port forward, static nat 포함), Firewall, LB 생성 및 제어
# ObjectStorage : object storage 3.0 기준으로 생성 및 제어
# VPC : json, csv 형식으로 대량 자원 생성 및 삭제
#
###############################################################################################

import kclutil as ku
import kclinstance as ki
import datetime
import requests
import json
import time
import logging
import os
from kclutil import FileSizeError
import inspect
import csv
import re
import copy
from collections import defaultdict

NET_JOB_INTERVAL = 2  # network_job의 완료 여부를 확인하는 주기
NET_JOB_MAX_COUNT = 10  # network_job 완료 여부 확인 최대 횟수
MULTIPART_UPLOAD_SIZE = 1024*1024*1024 # 1GB  # object sotrage에 file upload시 multipart 수행하는 최소 크기
MULTIPART_PART_SIZE = 1024*1024*200 # 200MB  # object sotrage의 multipart upload 시 part크기
MAX_VM_CREATE_COUNT = 4  # create_vms에서 동시에 생성할 수 있는 vm의 최대 개수

###################################################
#
# class ZoneManager
# open api를 이용하고자 하는 존을 지정, 존에 대한 인증 토큰 관리
#
###################################################

class ZoneManager:
    def __init__(self, id, passwd, zone_name):
        self._id = id
        self._passwd = passwd
        
        ku.validate_zone_name(zone_name)
        self._zone_name = zone_name
        self._zone, _ = self.get_zone()
            
        self._token = None
        self._token_expire = datetime.datetime.now() - datetime.timedelta(hours=1)
        self._project_id = ""
        self._create_token()
        self._logger = self._set_logger()
        self._external_id = self.get_external_id()
        
        if self._external_id == None:
            raise Exception("Can't get external_id of VPC!")
    
    # INFO 형태로 log 저장
    def info_log(self, message):
        self._logger.info(message)
    
    # ERROR 형태로 log 저장
    def error_log(self, message):
        self._logger.error(message)
     
    # log 저장 형식 지정
    def _set_logger(self):
        # 1. 공통 로깅 설정
        logging.basicConfig(
            level=logging.INFO,  # 로그 레벨 설정
            format='%(asctime)s - %(levelname)s : %(message)s',  # 포맷 설정
            filename=f"kcl_logs_{self._id}_{self._zone_name}.log",  # 파일에 로그 저장
            filemode='a'  # 추가 모드
        )

        # 2. 모듈 수준의 로거 생성
        return logging.getLogger('ktcloud')  # 공통 로거 이름 지정
         
    # token의 expire 여부를 확인, expire되면 True, 아니면 False
    def _check_token_expire(self):
        diff = datetime.datetime.now() - self._token_expire
              
        if diff >= datetime.timedelta(hours=0.95):
            return True
        return False
   
    # token을 새로 발급
    def _create_token(self):
        url = ku.get_request_url("make_token", zone=self._zone)
        body = ku.get_request_body("make_token", user_id=self._id, user_pw=self._passwd)
        response = requests.post(url, json=body)
        
        if(response.status_code == 201):
            self._token = response.headers.get("X-Subject-Token")
            self._token_expire = datetime.datetime.now()
            
            res = response.json()
            self._project_id = res["token"]["project"]["id"]            
        else:
            raise Exception("Authentication error")

        
    # token값을 return, token이 expire되면 새로 발급
    def _get_token(self):
        if self._check_token_expire():
            self._create_token()
        return self._token
      
    # X-Auth-Token 헤더에 token정보를 포함하여 return
    def get_auth_header(self):
        headers = {}
        headers["X-Auth-Token"] = self._get_token()
        return headers
    
    # zone 정보를 return
    def get_zone(self):
        zone = ""
        if self._zone_name == "DX-M1":
            zone = "d1"
        elif self._zone_name == "DX-Central":
            zone = "d2"
        elif self._zone_name == "DX-DCN-CJ":
            zone = "d3"
        elif self._zone_name == "DX-G":
            zone = "gd1"
        elif self._zone_name == "DX-G-YS":
            zone = "gd4"
        return zone, self._zone_name
    
    @property
    def project_id(self):
        return self._project_id
    
    @property
    def external_id(self):
        return self._external_id
    
    def compute_resource(self):
        return ComputeResource(self)
    
    def storage_resource(self):
        return StorageResource(self)
    
    def network_resource(self):
        return NetworkResource(self)
                
    def get_external_id(self):
        url = ku.get_request_url("list_subnet_info", zone=self._zone)
        headers = self.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self, params={"networkType":"UNTRUST"})
        
        res = response.json()
        
        if res["httpStatus"] == 200:
            for item in res["data"]:
                if item["networkName"] == "external":
                    return item["networkId"]
        
           
###################################################
#
# class ComputeResource
# VM 생성 및 제어하기 위한 api 제공
#
###################################################

class ComputeResource:
    def __init__(self, zone_mgr):
        self._zone_mgr = zone_mgr
        zone, zone_name = zone_mgr.get_zone()
        self._zone = zone
        self._zone_name = zone_name
        self._project_id = zone_mgr.project_id
     
    ################################################
    # vm functions
    ################################################
    
    # VM을 생성
    def create_vm(self, name, key, flavor_id, subnet_id, image_id, vol_size, vol_type, 
                  fixed_ip=None, disks=None, userdata=None):
        enc_userdata = ""
        if userdata:
            enc_userdata = ku.encode_to_base64(userdata)
            if len(enc_userdata) > 2048:
                raise Exception("Too long userdata : max size is 2048")
                
        ku.validate_volume_type(vol_type)
                    
        url = ku.get_request_url("create_vm", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_vm", 
                                vm_name=name, key_name=key, zone_name=self._zone_name, subnet_id=subnet_id,
                                flavor_id=flavor_id, image_id=image_id, vol_size=vol_size, 
                                   vol_type=vol_type, userdata=enc_userdata)
        
        # 고정 사설IP 지정
        if fixed_ip:
            body = ku.create_vm_fixed_ip(body, fixed_ip)
            
        # 추가 Disk 설정   
        if disks:
            body = ku.create_vm_add_disk_body(body, disks)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, vm_name=name)
        
        res = response.json()
        if(response.status_code == 202):
            vm_id = res["server"]["id"]
            return ki.VMInstance(vm_id, self)
        
    # VM 정보 조회
    def get_vm_info(self, vm_id):
        url = ku.get_request_url("get_vm_info", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header() 
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, vm_id=vm_id)
                
        if response.status_code == 200:
            res = response.json()
            return ku.parse_get_vm_info(res["server"])
    
    # vm_name 기반으로 vm_id 조회
    def get_vm_id(self, vm_name):
        vm_list = self.list_vm_info()
        
        if vm_list:
            for item in vm_list:
                if item["vm_name"] == vm_name:
                    return item["vm_id"]
    
    # VM들의 정보를 list형태로 return
    def list_vm_info(self):
        url = ku.get_request_url("list_vm_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()   
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
        
        if response.status_code == 200:
            return ku.parse_list_vm_info(response.json())
        
    # cnode에 속한 vm 목록 매핑 조회
    def get_cnode_vm_map(self):
        vm_list = self.list_vm_info()
        
        result = defaultdict(list)
        
        for vm in vm_list:
            if vm["host_id"] == "":
                # 정지된 vm
                continue
            result[vm["host_id"]].append(vm["vm_name"])

        # 일반 dict로 변환
        return dict(result)
                
    # VM 삭제
    def delete_vm(self, vm_id, forced=False):
        url = ku.get_request_url("delete_vm", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        if forced:
            body = ku.get_request_body("delete_vm_forced")
            response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, body=body, vm_id=vm_id)
        else:
            response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, vm_id=vm_id)
            
        if response.status_code == 204:
            return True
        return False
    
    # 정지된 VM 시작
    def start_vm(self, vm_id):
        url = ku.get_request_url("start_vm", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("start_vm")
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, vm_id=vm_id)
        
        if response.status_code == 202:
            return True
        return False
            
    # VM 정지
    def stop_vm(self, vm_id):
        url = ku.get_request_url("stop_vm", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("stop_vm")
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, vm_id=vm_id)
        
        if response.status_code == 202:
            return True
        return False
            
    # flavor 변경
    def change_vm(self, vm_id, flavor_id):
        url = ku.get_request_url("change_vm", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("change_vm", flavor_id=flavor_id)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, vm_id=vm_id)
        
        if response.status_code == 202:
            return True
        return False
    
    # 서버들이 생성될 때까지 기다림.
    def wait_until_active(self, vm_ids):
        waiter = self.waiter_instance("vm_active")
        return waiter.wait(vm_ids)
        
    # 서버들이 정지될 때까지 기다림.
    def wait_until_shutoff(self, vm_ids):        
        waiter = self.waiter_instance("vm_shutoff")
        return waiter.wait(vm_ids)
              
    # vm Instance를 return
    def vm_instance(self, vm_id):
        info = self.get_vm_info(vm_id)
        if info:
            return ki.VMInstance(vm_id, self)
    
    # Volume을 서버에 연결
    def attach_volume(self, vm_id, volume_id):
        url = ku.get_request_url("attach_volume", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("attach_volume", volume_id=volume_id)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, vm_id=vm_id)
        
        if response.status_code == 200:
            return True
        return False
    
    # Volume을 서버에서 해제
    def detach_volume(self, vm_id, volume_id):
        url = ku.get_request_url("detach_volume", vm_id=vm_id, volume_id=volume_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, vm_id=vm_id, volume_id=volume_id)
        
        if response.status_code == 202:
            return True
        return False
        
    # 서버에 연결된 volume정보
    def get_attached_volume(self, vm_id):
        url = ku.get_request_url("get_attached_volume", vm_id=vm_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, vm_id=vm_id)
        
        if response.status_code == 200:
            return ku.parse_attached_volume(response.json())
 
    ################################################
    # Flavor functions
    ################################################
    
    # flavor 정보(스팩 정보) 목록 제공
    def list_flavor_info(self):
        url = ku.get_request_url("list_flavor_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
        
        if response.status_code == 200:
            return ku.parse_flavor_info(response.json())
     
    # flavor_name에 매핑되는 id정보 조회
    def get_flavor_id(self, flavor_name):
        flavors = self.list_flavor_info()
        
        if flavors:
            for item in flavors:
                if item["flavor_name"] == flavor_name:
                    return item["flavor_id"]    
                
    # cpu/memory/intel서버 기준으로 매핑되는 id정보 조회
    def get_intel_flavor_id(self, cpu, mem):
        flavors = self.list_flavor_info()
        
        flavor_name = f"{cpu}x{mem}.itl"
        
        if flavors:
            for item in flavors:
                if item["flavor_name"] == flavor_name:
                    return item["flavor_id"]  
    
    ################################################
    # Waiter functions
    ################################################
    
    # Waiter Instance를 return
    def waiter_instance(self, dest_state):
        return ki.WaiterVMInstance(dest_state, self)
    
    ################################################
    # Metric
    ################################################
    
    # get_metric_info
    def get_metric_info(self, params):
        url = ku.get_request_url("get_metric_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params=params)
        
        if response.status_code == 200:
            return response.json()
            # return ku.parse_flavor_info(response.json())
            
    # list_metric_info
    def list_metric_info(self):
        url = ku.get_request_url("list_metric_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
        
        if response.status_code == 200:
            return response.json()
            # return ku.parse_flavor_info(response.json())
    
    
###################################################
#
# class StorageResource
# volume, image, snapshot, nas 등 볼륨 생성 및 관리
#
###################################################

class StorageResource:
    def __init__(self, zone_mgr):
        self._zone_mgr = zone_mgr
        zone, zone_name = zone_mgr.get_zone()
        self._zone = zone
        self._zone_name = zone_name
        self._project_id = zone_mgr.project_id
 
    ################################################
    # Snapshot functions
    ################################################
    
    # snapshot 생성
    def create_snapshot(self, name, volume_id, description=None):
        url = ku.get_request_url("create_snapshot", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_snapshot", snapshot_name=name, volume_id=volume_id,
                                  description=description)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, volume_id=volume_id)
        
        res = response.json()
        if response.status_code == 202:
            snapshot_id = res["snapshot"]["id"]
            return snapshot_id
    
    # snapshot 상세 정보 목록 조회
    def list_snapshot_info(self):
        url = ku.get_request_url("list_snapshot_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
    
        if response.status_code == 200:
            return ku.parse_list_snapshot_info(response.json())        
    
    # snapshot 삭제
    def delete_snapshot(self, snapshot_id):
        url = ku.get_request_url("delete_snapshot", project_id=self._project_id, 
                                 snapshot_id=snapshot_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, snapshot_id=snapshot_id)
        
        if response.status_code == 202:
            return True
        return False
    
    # snapshot 상세 정보 조회
    def get_snapshot_info(self, snapshot_id):
        url = ku.get_request_url("get_snapshot_info", project_id=self._project_id, 
                                 snapshot_id=snapshot_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, snapshot_id=snapshot_id)
    
        if response.status_code == 200:
            return ku.parse_get_snapshot_info(response.json())        
    
    ################################################
    # Image functions
    ################################################
    
    # image 생성
    def create_image(self, name, volume_id):
        url = ku.get_request_url("create_image", project_id=self._project_id, volume_id=volume_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_image", image_name=name)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, 
                                  img_name=name, volume_id=volume_id)
        
        if response.status_code == 202:
            res = response.json()
            return res["os-volume_upload_image"]["image_id"]
    
    # image 상세 정보 목록 조회 (전체 조회로 수정)
    def list_image_info(self):
        url = ku.get_request_url("list_image_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
    
        # 전체 이미지 조회
        url = url + "?limit=400"
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
    
        if response.status_code == 200:
            return ku.parse_list_image_info(response.json())  
        
    # image 상세 정보 목록 조회 (내부용)
    def _list_image_info(self):
        url = ku.get_request_url("list_image_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        # 전체 이미지 조회
        url = url + "?limit=400"
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
    
        if response.status_code == 200:
            return ku.parse_list_image_info(response.json())  
        
    # image_id 조회, open API에서 조회되는 name 기준으로 조회
    def _get_image_id_size(self, image_name):
        images = self._list_image_info()
        
        if images:
            for item in images:
                if item["image_name"] == image_name:
                    return item["image_id"], item["min_disk"]
                
    # os name을 기준으로 image_id 조회, 표준 이미지 name, 및 open API 기준 name 모두 가능
    def get_image_id_size(self, os_name):
#         if ku.check_os_name(os_name):
#             image_name = ku.get_image_name(os_name, self._zone_name)
#         else:
#             image_name = os_name
            
        image_name = os_name
            
        if image_name == None:
            zone = self._zone_name
            raise Exception(f"'{os_name}' in {zone} does not exist")
            
        return self._get_image_id_size(image_name)
    
    # image 삭제
    def delete_image(self, image_id):
        url = ku.get_request_url("delete_image", project_id=self._project_id, 
                                 image_id=image_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, image_id=image_id)
    
        if response.status_code == 204:
            return True
        return False
            
    
    # image 상세 정보 조회
    def get_image_info(self, image_id):
        url = ku.get_request_url("get_image_info", project_id=self._project_id, 
                                 image_id=image_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, image_id=image_id)
    
        if response.status_code == 200:
            return ku.parse_get_image_info(response.json()) 
    
    ################################################
    # Volume functions
    ################################################
    
    # volume 생성
    def create_volume(self, name, size, vol_type, snapshot_id=None):
        # volume type validation check
        ku.validate_volume_type(vol_type)
        
        url = ku.get_request_url("create_volume", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_volume", vol_name=name, 
                                   vol_size=size, zone_name=self._zone_name, vol_type=vol_type)
        
        if snapshot_id:
            body["volume"]["snapshot_id"] = snapshot_id
            
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, volume_name=name)
        
        if(response.status_code == 202):
            res = response.json()
            volume_id = res["volume"]["id"]    
            return ki.VolumeInstance(volume_id, False, self)

    # volume 정보 조회
    def get_volume_info(self, volume_id):
        url = ku.get_request_url("get_volume_info", 
                              volume_id=volume_id, project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, volume_id=volume_id)
                        
        if response.status_code == 200:
            res = response.json()
            return ku.parse_get_volume_info(res["volume"])
            
    # volume 삭제
    # available 상태일 때 삭제 가능 (in-use 에서는 삭제 안됨)
    def delete_volume(self, volume_id):
        url = ku.get_request_url("delete_volume", 
                              volume_id=volume_id, project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, volume_id=volume_id)

        if response.status_code == 202:
            return True
        return False
    
    # volume 목록 확인
    def list_volume_info(self):
        url = ku.get_request_url("list_volume_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
                
        if response.status_code == 200:
            return ku.parse_list_volume_info(response.json())
        
    # Volume Instance를 return
    def volume_instance(self, volume_id):
        info = self.get_volume_info(volume_id)
        if info:
            return ki.VolumeInstance(volume_id, info["bootable"], self)
    
    # volume들이 생성될 때까지 기다림.
    def wait_until_available(self, volume_ids):
        waiter = self.waiter_instance("volume_available")
        return waiter.wait(vm_ids)
        
    # volume들이 서버에 연결될 때까지 기다림.
    def wait_until_inuse(self, volume_ids):        
        waiter = self.waiter_instance("volume_inuse")
        return waiter.wait(vm_ids)
    
    ################################################
    # Waiter functions
    ################################################
    
    # Waiter Instance를 return
    def waiter_instance(self, dest_state):
        return ki.WaiterVolumeInstance(dest_state, self)

    ################################################
    # NAS functions
    ################################################
    
    # NAS의 목록 정보 제공
    def list_nas_info(self):
        url = ku.get_request_url("list_nas_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
        
        if response.status_code == 200:
            return ku.parse_list_nas_info(response.json())
    
    # nas_id에 매핑되는 NAS 정보 제공
    def get_nas_info(self, nas_id):
        url = ku.get_request_url("get_nas_info", project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, nas_id=nas_id)
        
        if response.status_code == 200:
            res = response.json()
            return ku.parse_get_nas_info(res["share"])
    
    # NAS 생성
    def create_nas(self, name, size, vol_type, network_id):
        ku.validate_volume_type(vol_type)
        
        if size > 10000:
            raise Exception("create_nas() : NAS volume max size = 10,000GB")
        
        url = ku.get_request_url("create_nas", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_nas", nas_name=name, nas_size=size, 
                                   nas_network_id=network_id, zone_name=self._zone_name, vol_type=vol_type)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, nas_name=name)
        
        if response.status_code == 200:
            res = response.json()
            nas_id = res["share"]["id"]
            return ki.NASInstance(nas_id, self)
        
    # NAS id 정보 return
    def get_nas_id(self, nas_name):
        info = self.list_nas_info()
        
        if info:
            for item in info:
                if item["nas_name"] == nas_name:
                    return item["nas_id"]
    
    # NASInstance return
    def nas_instance(self, nas_id):
        return ki.NASInstance(nas_id, self)
    
    # NAS 삭제
    def delete_nas(self, nas_id):
        url = ku.get_request_url("delete_nas", project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, nas_id=nas_id)
        
        if response.status_code == 202:
            return True
        return False
                
    # NAS network 정보 조회
    def list_nas_network_info(self):
        url = ku.get_request_url("list_nas_network_info", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr)
        
        if response.status_code == 200:
            res = response.json()
            return ku.parse_list_nas_network_info(res)
        
    # network_id에 매핑되는 nas network정보 조회
    def get_nas_network_info(self, network_id):
        url = ku.get_request_url("get_nas_network_info", 
                                 project_id=self._project_id, zone=self._zone, share_network_id=network_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, network_id=network_id)
        
        if response.status_code == 200:
            res = response.json()
            return ku.parse_get_nas_network_info(res["share_network"])
      
    # nas network 이름에 매핑되는 nas_network_id return
    def get_nas_network_id(self, name):
        nets = self.list_nas_network_info()
        
        if nets:
            for item in nets:
                if item["nas_network_name"] == name:
                    return item["nas_network_id"]
    
    # NAS network 생성, NAS network는 NAS를 연결할 수 있는 네트워크이며, 기존 subnet을 이용하여 생성
    def create_nas_network(self, name, subnet_id):
        url = ku.get_request_url("create_nas_network", project_id=self._project_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_nas_network", nas_name=name, subnet_id=subnet_id)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, 
                                  net_name=name, subnet_id=subnet_id)
        
        if response.status_code == 200:
            res = response.json()
            return res["share_network"]["id"]
             
    # NAS network 삭제
    def delete_nas_network(self, network_id):
        url = ku.get_request_url("delete_nas_network", 
                                 project_id=self._project_id, zone=self._zone, share_network_id=network_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, network_id=network_id)
        
        if response.status_code == 202:
            return True
        return False
    
    # NAS Volume 크기 변경, 최대 10TB
    def change_nas_size(self, nas_id, size):
        if size > 10000:
            raise Exception("Maximun NAS size is 10,000GB")
                            
        url = ku.get_request_url("change_nas_size", 
                                 project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("change_nas_size", nas_size=size)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, nas_id=nas_id)
        
        if response.status_code == 202:
            return True
        return False
    
    # NAS 접근 권한 제어
    def set_nas_access(self, nas_id, level, cidr):
        levels = ["rw", "ro"]
        level = level.lower()
        
        if level not in levels:
            raise Exception(f"{level} : syntax error!, ex) 'rw', 'ro'")
            
        if not ku.is_valid_cidr(cidr):
            raise Exception(f"{cidr} : syntax error!, ex) '10.0.0.0/24'")
            
        url = ku.get_request_url("set_nas_access", 
                                 project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_nas_access", access_level=level, access_cidr=cidr)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, nas_id=nas_id)
        
        if response.status_code == 200:
            res = response.json()
            return res["access"]["id"]
    
    # NAS 접근 권한 정보 조회
    def get_nas_access_info(self, nas_id):
        url = ku.get_request_url("get_nas_access_info", 
                                 project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("get_nas_access_info")
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, nas_id=nas_id)
        
        if response.status_code == 200:
            res = response.json()
            return ku.parse_get_nas_access_info(res)
    
    # NAS 접근 권한 정보 해제
    def unset_nas_access(self, nas_id, access_id):
        url = ku.get_request_url("unset_nas_access", 
                                 project_id=self._project_id, zone=self._zone, share_id=nas_id)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("unset_nas_access", access_id=access_id)
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body, 
                                  nas_id=nas_id, access_id=access_id)
        
        if response.status_code == 202:
            return True
        return False

###################################################
#
# class NetworkResource
# subnet, ip, portforward, staticnat, firewall, LB 제어
#
###################################################

class NetworkResource:
    def __init__(self, zone_mgr):
        self._zone_mgr = zone_mgr
        zone, zone_name = zone_mgr.get_zone()
        self._zone = zone
        self._zone_name = zone_name
        self._project_id = zone_mgr.project_id
        self._external_id = zone_mgr.external_id
        self._subnet_list = self.list_subnet_info()
                
    ################################################
    # IP Address functions
    ################################################
    
    # public ip address 생성
    def create_publicip(self):       
        url = ku.get_request_url("create_publicip", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr)
        
        res = response.json()
        if res["httpStatus"] == 201: # 문자인지 숫자인지 확인 필요
            ip_id = res["data"]["publicIpId"]
            info = self.get_publicip_info(ip_id)
            return ki.PublicIPInstance(ip_id, info["publicip"], self)
    
    # public ip address 목록 조회
    def list_publicip_info(self):
        url = ku.get_request_url("list_publicip_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"page":1, "size":2000})
        
        res = response.json()
        if res["httpStatus"] == 200: # 문자인지 숫자인지 확인 필요
            return ku.parse_list_publicip_info(res)
    
    # public ip address 삭제
    def delete_publicip(self, publicip_id):        
        url = ku.get_request_url("delete_publicip", publicip_id=publicip_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
  
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr)
        
        if response.status_code == 204:
            return True
        return False
    
    # public ip 정보 조회
    def get_publicip_info(self, publicip_id):
        url = ku.get_request_url("list_publicip_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"publicIpId": publicip_id})
        
        res = response.json()
        if res["httpStatus"] == 200: 
            ip_list = ku.parse_list_publicip_info(res)
            if len(ip_list) == 1:
                return ip_list[0]
        
    # public ip에 매핑되는 id return
    def get_publicip_id(self, publicip):
        ip_list = self.list_publicip_info()
        
        if ip_list:
            for item in ip_list:
                if item["publicip"] == publicip:
                    return item["publicip_id"]
    
    # PublicIPInstance return
    def publicip_instance(self, publicip_id):
        info = self.get_publicip_info(publicip_id)
        if info:
            return ki.PublicIPInstance(publicip_id, info["publicip"], self)
   
    ################################################
    # Port forwarding functions
    ################################################
    
    # port forward 상세 정보 목록 조회
    def list_portforward_info(self):
        url = ku.get_request_url("list_portforward_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"page":1, "size":2000})
        
        res = response.json()
        if res["httpStatus"] == 200:
            return ku.parse_list_portforward_info(res)
    
    # port forward 설정
    def set_portforward(self, privateip, publicip_id, private_port, public_port, protocol):        
        ku.validate_firewall_protocol(protocol)
        
        url = ku.get_request_url("set_portforward", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_portforward", privateip=privateip, publicip_id=publicip_id,
                                  private_port=private_port, public_port=public_port, protocol=protocol)
        
        func_name = inspect.currentframe().f_code.co_name        
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body)
        
        res = response.json()
        if res["httpStatus"] == 201: 
            pf_id = res["data"]["portForwardingId"]
            return pf_id       
    
    # port forward 설정 해제
    def unset_portforward(self, portforward_id):        
        url = ku.get_request_url("unset_portforward", portforward_id=portforward_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr)
        
        if response.status_code == 204:
            return True
        return False

    # portforward_id에 매핑되는 static nat 정보 조회
    def get_portforward_info(self, portforward_id):
        url = ku.get_request_url("list_portforward_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"portForwardingId": portforward_id})
        
        res = response.json()
        if res["httpStatus"] == 200:
            pf_list = ku.parse_list_portforward_info(res)
            if len(pf_list) == 1:
                return pf_list[0]
    
    # publicip를 이용하는 port forward 설정 정보 조회
    def get_portforward_info_of_publicip(self, publicip):
        pfs = self.list_portforward_info()
        pf_list = []
        
        if pfs:
            for item in pfs:
                if item["publicip"] == publicip:
                    pf_list.append(item)

            return pf_list
    
    ################################################
    # Staic NAT functions
    ################################################
 
    # staic nat설정
    def set_staticnat(self, privateip, publicip_id): # subnet_id는 불필요하여 삭제
        url = ku.get_request_url("set_staticnat", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_staticnat", privateip=privateip, publicip_id=publicip_id)
        
        func_name = inspect.currentframe().f_code.co_name        
        response = ku.request_api(func_name, "post", url, headers, self._zone_mgr, body=body)     

        res = response.json()
        if res["httpStatus"] == 201:
            return res["data"]["staticNatId"]
    
    # static nat 설정 정보 조회
    def list_staticnat_info(self):
        url = ku.get_request_url("list_staticnat_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"page":1, "size":2000})
    
        res = response.json()
        if res["httpStatus"] == 200:
            return ku.parse_list_staticnat_info(res)
    
    # static nat 설정 해제
    def unset_staticnat(self, staticnat_id):       
        url = ku.get_request_url("unset_staticnat", staticnat_id=staticnat_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr)
        
        if response.status_code == 204:
            return True
        return False
    
    # staticnat_id에 매핑되는 static nat 정보 조회
    def get_staticnat_info(self, staticnat_id):
        nats = self.list_staticnat_info()
        
        if nats:
            for item in nats:
                if item["staticnat_id"] == staticnat_id:
                    return item
    
    # publicip에 매핑되는 staticnat 정보 조회
    def get_staticnat_info_of_publicip(self, publicip):
        nats = self.list_staticnat_info()
        
        if nats:
            for item in nats:
                if item["publicip"] == publicip:
                    return item
    
    ################################################
    # Firewall functions
    ################################################
      
    # firewall 목록 정보 조회
    def list_firewall_info(self):
        url = ku.get_request_url("list_firewall_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"page":1, "size":2000})
    
        res = response.json()
        if res["httpStatus"] == 200:
            return ku.parse_list_firewall_info(res, self)
        
    # firewall 설정 정보 조회
    def get_firewall_info(self, acl_id):
        url = ku.get_request_url("list_firewall_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"policyId": acl_id})
    
        res = response.json()
        if res["httpStatus"] == 200:
            acl_list = ku.parse_list_firewall_info(res, self)
            if len(acl_list) == 1:
                return acl_list[0]
        
    # firewall ACL 설정 : network - network 연결
    # subnet -> subnet, subnet -> external
    def set_firewall_net2net(self, src_net_id, src_cidr, dst_net_id, dst_cidr, protocol, action, start_port=None, end_port=None):
        interval = NET_JOB_INTERVAL
        count = 0
        srcnat = "false"
        
        new_src_cidr = ku.validate_firewall_cidr(src_cidr)    
        new_dst_cidr = ku.validate_firewall_cidr(dst_cidr)  
        
        ku.validate_firewall_protocol(protocol)
        ku.validate_firewall_action(action)
        
        new_action = "true" if action == "allow" else "false"
        
        src_network_id = self._get_subnet_network_id(src_net_id)
        if src_network_id == None:
            raise Exception(f"set_firewall_net2net() : src_net_id('{src_net_id}') not found!")
        
        # 목적지가 external(internet)이면 external_id로 변경
        if dst_net_id == "external":
            dst_network_id = self._external_id
            srcnat = "true"
        else:
            dst_network_id = self._get_subnet_network_id(dst_net_id)
            if dst_network_id == None:
                raise Exception(f"set_firewall_net2net() : dst_net_id('{dst_net_id}') not found!")
    
        url = ku.get_request_url("set_firewall", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_firewall_net2net", src_net_id=src_network_id, src_cidr=src_cidr,
                                  dst_net_id=dst_network_id, dst_cidr=dst_cidr, protocol=protocol, action=new_action, srcnat=srcnat)
        
        # body의 post처리 필요, srcAddress, dstAddress를 수정
        body["srcAddress"] = new_src_cidr
        body["dstAddress"] = new_dst_cidr
        
        if start_port != None or end_port != None:
            body = ku.set_firewall_add_port_body(body, start_port, end_port)
        else:
            if protocol == "TCP" or protocol == "UDP":
                raise Exception("set_firewall_net2net() : if protocol is 'TCP' or 'UDP', start_port and end_port are mandatory")         
        
        func_name = inspect.currentframe().f_code.co_name
        job_id = ku.request_net_api(func_name, "post", url, headers, self._zone_mgr, body=body)
        
        # loop를 돌릴지 확인 필요
        if job_id:          
            while True:
                count += 1
                info = self._get_net_job_status("set_firewall", job_id)
                if info["job_status"] == "SUCCESS":
                    return info["acl_id"]
                elif info["job_status"] == "RUNNING":
                    time.sleep(interval)
                else:
                    return None
                if count > NET_JOB_MAX_COUNT:
                    return None
                
    
    # firewall ACL 설정 : port forward 연결
    # external -> portforward 설정된 vm
    def set_firewall_portforward(self, portforward_id, src_cidr):
        interval = NET_JOB_INTERVAL
        count = 0
        
        new_src_cidr = ku.validate_firewall_cidr(src_cidr) 
        
        info = self.get_portforward_info(portforward_id)
        if info == None:
            raise Exception(f'portforward id "{portforward_id}" not exist')
            
        url = ku.get_request_url("set_firewall", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_firewall_portforward", src_net_id=self._external_id, src_cidr=src_cidr,
                                  portforward_id=portforward_id)
        
        # body의 post처리 필요, srcAddress를 수정
        body["srcAddress"] = new_src_cidr
        
        pf_info = self.get_portforward_info(portforward_id)
        if pf_info:
            body["protocol"] = pf_info["protocol"]
            body["startPort"] = pf_info["private_port"]
            body["endPort"] = pf_info["private_end_port"]
        else:
            raise Exception(f"set_firewall_portforward() : portforward_id({portforward_id}) not found!")        
        
        func_name = inspect.currentframe().f_code.co_name
        job_id = ku.request_net_api(func_name, "post", url, headers, self._zone_mgr, body=body, pf_id=portforward_id)
        
        if job_id:          
            while True:
                count += 1
                info = self._get_net_job_status("set_firewall", job_id)
                if info["job_status"] == "SUCCESS":
                    return info["acl_id"]
                elif info["job_status"] == "RUNNING":
                    time.sleep(interval)
                else:
                    return None
                if count > NET_JOB_MAX_COUNT:
                    return None
    
    # firewall ACL 설정 : static nat 연결
    # external -> staticnat 설정된 vm
    def set_firewall_staticnat(self, staticnat_id, src_cidr, protocol, start_port=None, end_port=None):
        interval = NET_JOB_INTERVAL
        count = 0
        
        new_src_cidr = ku.validate_firewall_cidr(src_cidr) 
        
        ku.validate_firewall_protocol(protocol)
            
        url = ku.get_request_url("set_firewall", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("set_firewall_staticnat", src_net_id=self._external_id, src_cidr=src_cidr,
                                  staticnat_id=staticnat_id, protocol=protocol)
        
        if start_port != None or end_port != None:
            body = ku.set_firewall_add_port_body(body, start_port, end_port)
        else:
            if protocol == "TCP" or protocol == "UDP":
                raise Exception("set_firewall_staticnat() : if protocol is 'TCP' or 'UDP', start_port and end_port are mandatory") 
            
        # body의 post처리 필요, srcAddress를 수정
        body["srcAddress"] = new_src_cidr
            
        func_name = inspect.currentframe().f_code.co_name
        job_id = ku.request_net_api(func_name, "post", url, headers, self._zone_mgr, body=body, nat_id=staticnat_id)
        
        if job_id:
            while True:
                count += 1
                info = self._get_net_job_status("set_firewall", job_id)
                if info["job_status"] == "SUCCESS":
                    return info["acl_id"]
                elif info["job_status"] == "RUNNING":
                    time.sleep(interval)
                else:
                    return None
                if count > NET_JOB_MAX_COUNT:
                    return None
    
    # ACL 설정 해제
    def unset_firewall(self, acl_id):
        url = ku.get_request_url("unset_firewall", zone=self._zone, firewall_id=acl_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "delete", url, headers, self._zone_mgr, acl_id=acl_id)
        
        if response.status_code == 204:
            return True
        return False      
    
    ################################################
    # subnet functions
    ################################################
    
    # subnet 생성, 동기 호출로 시간이 좀 걸림
    def create_subnet(self, name, cidr, startip, endip, lbstartip, lbendip, bmstartip, bmendip, iscsistartip, iscsiendip, gatewayip):
        # parameter validation check
        if not ku.is_valid_cidr(cidr):
            raise Exception(f"{cidr} : syntax error!, ex) '10.0.0.0/24'")
        
        url = ku.get_request_url("create_subnet", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        body = ku.get_request_body("create_subnet", subnet_name=name, zone_name=self._zone_name,
                               cidr_range=cidr, start_ip=startip, end_ip=endip,
                               lb_start_ip=lbstartip, lb_end_ip=lbendip,
                               bm_start_ip=bmstartip, bm_end_ip=bmendip, 
                               iscsi_start_ip=iscsistartip, iscsi_end_ip=iscsiendip, gateway_ip=gatewayip)
        
        func_name = inspect.currentframe().f_code.co_name
        
        job_id = ku.request_net_api(func_name, "post", url, headers, self._zone_mgr, body=body, subnet_name=name)
        
        count = 0
        interval = NET_JOB_INTERVAL
        network_id = None
        if job_id:
            while True:
                count += 1
                info = self._get_net_job_status("create_subnet", job_id)
                if info["job_status"] == "SUCCESS":
                    network_id = info["subnet_network_id"]
                elif info["job_status"] == "RUNNING":
                    time.sleep(interval)
                else:
                    break
                if count > NET_JOB_MAX_COUNT:
                    break
                
        if network_id:
            subnet_list = self._get_subnet_id_of_network_id(network_id)
            if len(subnet_list) == 1:
                return subnet_list[0]["subnet_id"]     
          
    def _get_subnet_id_of_network_id(self, network_id):
        url = ku.get_request_url("list_subnet_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"networkId": network_id})
        
        res = response.json()
        if res["httpStatus"] == 200:
            return ku.parse_list_subnet(res)
        
    # subnet 목록 조회
    def list_subnet_info(self):
        url = ku.get_request_url("list_subnet_info", zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response = ku.request_api(func_name, "get", url, headers, self._zone_mgr, params={"page":1, "size":2000})
        
        res = response.json()
        if res["httpStatus"] == 200:
            return ku.parse_list_subnet(res)
            
    # subnet_name에 따른 subnet 정보 return
    def get_subnet_info(self, subnet_name):
        subnets = self.list_subnet_info()
        
        if subnets:
            for item in subnets:
                if item["subnet_name"] == subnet_name:
                    return item
 
    # subnet_name에 따른 subnet_id return
    def get_subnet_id(self, subnet_name):
        info = self.get_subnet_info(subnet_name)
        
        if info:
            return info["subnet_id"]
        
    # subnet_name에 따른 subnet_id return
    def get_subnet_network_id(self, subnet_name):
        info = self.get_subnet_info(subnet_name)
        
        if info:
            return info["subnet_network_id"]
    
    # privateip가 속한 subnet_id return
#     def get_subnet_id_of_privateip(self, privateip):
#         subnets = self.list_subnet_info()
        
#         if subnets:
#             for item in subnets:
#                 if ku.is_in_cidr(privateip, item["cidr"]):
#                     return item["subnet_id"]
                
    def _get_subnet_info(self, key, id_value):
        for item in self._subnet_list:
            if item[key] == id_value:
                return item

            
    # subnet_id에 속한 subnet_network_id return
    def _get_subnet_network_id(self, subnet_id):
        subnet = self._get_subnet_info("subnet_id", subnet_id)
        
        if subnet:
            return subnet["subnet_network_id"]
        else:
            self._subnet_list = self.list_subnet_info()
            subnet = self._get_subnet_info("subnet_id", subnet_id)
            if subnet:
                return subnet["subnet_network_id"]
            
    # subnet_network_id에 속한 subnet_id return
    def _get_subnet_id(self, subnet_network_id):
        subnet = self._get_subnet_info("subnet_network_id", subnet_network_id)
        
        if subnet:
            return subnet["subnet_id"]
        else:
            self._subnet_list = self.list_subnet_info()
            subnet = self._get_subnet_info("subnet_network_id", subnet_network_id)
            if subnet:
                return subnet["subnet_id"]
        
    # network_id가 key이고, subnet_id가 value인 dict return
    def _get_subnet_id_map_dict(self):
        map_dict = {}
        
        self._subnet_list = self.list_subnet_info()
        for item in self._subnet_list:
            map_dict[item["subnet_network_id"]] = item["subnet_id"]
            
        map_dict[self._external_id] = None
        
        return map_dict
    
    # subnet 삭제, 동기함수, 시간이 오래 소요됨
    # DMZ, Private subnet는 삭제 안됨.
    def delete_subnet(self, subnet_id):   
        network_id = self._get_subnet_network_id(subnet_id)
        
        if network_id == None:
            raise Exception(f"subnet_id not found. subnet_id={subnet_id}")
        
        url = ku.get_request_url("delete_subnet", network_id=network_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        job_id = ku.request_net_api(func_name, "delete", url, headers, self._zone_mgr, subnet_id=subnet_id)

        # 왠만하면 삭제되기 때문에 별도로 job_id 검사하지 않음.
        if job_id:
            return True
        return False
        
    ################################################
    # etc functions
    ################################################
    
    # 비동기 network job의 상태 확인
    def _get_net_job_status(self, job_type, job_id):
        url = ku.get_request_url("get_net_job_status", job_id=job_id, zone=self._zone)
        headers = self._zone_mgr.get_auth_header()
        time.sleep(1)
        response = requests.get(url, headers=headers)

        return ku.parse_net_job_status(job_type, response.json(), self._zone_mgr)
    
    # Waiter Instance를 return
    def waiter_instance(self, dest_state):
        return WaiterVoumeInstance(dest_state, self)
    
    ################################################
    # Load Balancer functions
    ################################################
    
    # 전체 LB정보의 목록 제공
    # lb_name, service_ip, lb_id로 특정 LB의 정보만 조회도 가능, 
    def list_lb_info(self, lb_name=None, service_ip=None, lb_id=None):
        url = ku.get_lb_request_url("list_lb_info", zone=self._zone, 
                                    name=lb_name, serviceip=service_ip, loadbalancerid=lb_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                              "listloadbalancersresponse")
        
        if success:
            return ku.parse_list_lb_info(response.json())
    
    # LB 생성
    # service_ip는 private_ip로 동일한 private_ip에 port만 추가하는 경우에만 기존 LB로 생성된 private_ip정보를 입력
    def create_lb(self, lb_name, lb_option, service_port, service_type, healthcheck_type, subnet_id, 
                  healthcheck_url=None, service_ip=None, ciphergroup_name=None, tlsv1=None, tlsv11=None, tlsv12=None):
        # 입력 paramter에 따라 필수 parameter가 있기 때문에 이를 확인
        ku.check_parameter_validation(lb_option, service_type, healthcheck_type,healthcheck_url, 
                                      ciphergroup_name, tlsv1, tlsv11, tlsv12)
        
        url = ku.get_lb_request_url("create_lb", zone=self._zone, zoneid=self._zone_name, name=lb_name,
                                    loadbalanceroption=lb_option, serviceip=service_ip, 
                                    serviceport=service_port, servicetype=service_type, 
                                    healthchecktype=healthcheck_type, healthcheckurl=healthcheck_url,
                                    ciphergroupname=ciphergroup_name, tlsv1=tlsv1, tlsv11=tlsv11, tlsv12=tlsv12,
                                    networkid=subnet_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "createloadbalancerresponse", lb_name=lb_name)
        
        if success:
            res = response.json()
            lb_id = res["createloadbalancerresponse"]["loadbalancerid"]
            return ki.LBInstance(lb_id, self)

    # LB usage 조회s
    def get_lb_usage(self, lb_name, start_date, end_date):
        url = ku.get_lb_request_url("get_lb_usage", zone=self._zone, name=lb_name, startdt=start_date, enddt=end_date)
        headers = self._zone_mgr.get_auth_header()

        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "usageloadbalancerserviceresponse", lb_name=lb_name)

        if success:
            return ku.parse_get_lb_usage(response.json())
        
       
    # LB 수정, lb_option, healthcheck_type 등
    def update_lb(self, lb_id, lb_option=None, healthcheck_type=None, healthcheck_url=None, ciphergroup_name=None,
                 tlsv1=None, tlsv11=None, tlsv12=None):
        # parameter validation check
        if healthcheck_type != None:
            ku.check_healthcheck_type_validation(healthcheck_type, healthcheck_url)
        if lb_option !=None:
            ku.check_lb_option_validation(lb_option)
            
        lb_info_list = self.list_lb_info(lb_id=lb_id)
        if len(lb_info_list) != 1:
            return False
        lb_info = lb_info_list[0]
        
        if lb_info["service_type"].lower() == "https":
            if ciphergroup_name == None:
                ciphergroup_name = lb_info["ciphergroup_name"]
            if tlsv1 == None:
                tlsv1 = lb_info["tlsv1"]
            if tlsv11 == None:
                tlsv11 = lb_info["tlsv11"]
            if tlsv12 == None:
                tlsv12 = lb_info["tlsv12"]
                                
            ku.check_parameter_validation(lb_option, "https", healthcheck_type,healthcheck_url, 
                                      ciphergroup_name, tlsv1, tlsv11, tlsv12)
                                           
            # https 관련한 update는 에러가 발생함.
            url = ku.get_lb_request_url("update_lb", zone=self._zone, 
                                    loadbalancerid=lb_id, loadbalanceroption=lb_option, 
                                    healthchecktype=healthcheck_type, healthcheckurl=healthcheck_url,
                                    ciphergroupname=ciphergroup_name, tlsv1=tlsv1, tlsv11=tlsv11, tlsv12=tlsv12)            
        else: 
            service_type = lb_info["service_type"].lower()
            url = ku.get_lb_request_url("update_lb", zone=self._zone,
                                        loadbalancerid=lb_id, loadbalanceroption=lb_option,
                                        healthchecktype=healthcheck_type, healthcheckurl=healthcheck_url)
            
        headers = self._zone_mgr.get_auth_header()
                
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "updateloadbalancerresponse", lb_id=lb_id)
        return success
        
    # LB 삭제
    def delete_lb(self, lb_id):
        url = ku.get_lb_request_url("delete_lb", zone=self._zone, loadbalancerid=lb_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "deleteloadbalancerresponse", lb_id=lb_id)  
        return success
    
    # LB에 부하분산할 서버 추가
    def add_lb_server(self, lb_id, vm_id, vm_ip, vm_port):
        url = ku.get_lb_request_url("add_lb_server", zone=self._zone, loadbalancerid=lb_id,
                                   virtualmachineid=vm_id, ipaddress=vm_ip, publicport=vm_port)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "addloadbalancerwebserverresponse", lb_id=lb_id)  
        
        if success:
            res = response.json()
            return res["addloadbalancerwebserverresponse"]["serviceid"]
    
    # LB가 부하분산할 서버의 목록 정보 제공
    def list_lb_server(self, lb_id):
        url = ku.get_lb_request_url("list_lb_server", zone=self._zone, loadbalancerid=lb_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "listloadbalancerwebserversresponse", lb_id=lb_id)
        
        if success:
            return ku.parse_list_lb_server(response.json())
    
    # LB가 부하분산할 서버 대상 삭제
    # service_id는 add_lb_server()의 response로 받은 serviceid값
    def remove_lb_server(self, service_id):
        url = ku.get_lb_request_url("remove_lb_server", zone=self._zone, serviceid=service_id)
        headers = self._zone_mgr.get_auth_header()
        
        func_name = inspect.currentframe().f_code.co_name
        response, success = ku.request_lb_api(func_name, "get", url, headers, self._zone_mgr, 
                                  "removeloadbalancerwebserverresponse", service_id=service_id)
        return success
    
    # lb_name에 매핑되는 lb_id 조회
    def get_lb_id(self, lb_name):
        lb_info = self.list_lb_info(lb_name=lb_name)
        
        if len(lb_info) == 0:
            return None
        
        return lb_info[0]["lb_id"]
        
    
    # LBInstance return
    def lb_instance(self, lb_id):
        return ki.LBInstance(lb_id, self)    
        

###################################################
#
# class ObjectStorage
# Box 생성 및 관리, file upload/download 수행
#
###################################################

class ObjectStorage:
    def __init__(self, access_key, secret_key):
        self._access_key = access_key
        self._secret_key = secret_key
    
    # box 목록 정보 제공
    def list_box(self):
        path = ku.get_object_path("list_box")
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "GET", "", path)
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return ku.parse_list_filebox(response.text)
    
    # box 생성
    def create_box(self, box_name):
        path = ku.get_object_path("create_box", box_name=box_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "PUT", "", path)
        response = requests.put(url, headers=headers)

        if response.status_code == 200:
            return ki.BoxInstance(box_name, self)
    
    # box 삭제
    def delete_box(self, box_name):
        path = ku.get_object_path("delete_box", box_name=box_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "DELETE", "", path)
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:
            return True
        return False
    
    # file upload 수행, 지정한 크기 이하의 file만 upload 가능
    def upload_box_file(self, box_name, file_path, key_name):
        try:
            # file 유효성 및 크기 제약 check
            file_size = os.path.getsize(file_path)
            if file_size >= MULTIPART_UPLOAD_SIZE:
                max_size = MULTIPART_UPLOAD_SIZE/1024/1024/1024
                raise FileSizeError(f'"{file_path}" size is too big, smaller than {max_size}GB')
        except FileNotFoundError:
            raise Exception(f'"{file_path}" not exist')
            
        with open(file_path, 'rb') as file:
            path = ku.get_object_path("upload_box_file", box_name=box_name, key_name=key_name)
            url = ku.get_object_url(path)
            headers = ku.get_auth_header(self._access_key, self._secret_key, 
                                         "PUT", "application/octet-stream", path)
            response = requests.put(url, headers=headers, data=file)
            
            if response.status_code == 200:
                return True
            return False
        
    # box에 속한 file 목록 정보 제공
    def list_box_file(self, box_name):
        path = ku.get_object_path("list_box_file", box_name=box_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "GET", "", path)
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return ku.parse_list_box_file(response.text)
    
    # box에 속한 특정 파일 삭제
    def delete_box_file(self, box_name, key_name):
        path = ku.get_object_path("delete_box_file", box_name=box_name, key_name=key_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "DELETE", "", path)
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:
            return True
        return False
        
    # file download 수행
    def download_box_file(self, box_name, key_name):
        path = ku.get_object_path("download_box_file", box_name=box_name, key_name=key_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "GET", "", path)
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            file_name = os.path.basename(key_name)
            with open(file_name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            return True
        return False     
    
    # multipart upload를 수행하기 위한 작업 생성
    # 특정 크기 이상인 file만 multipart upload 수행
    def create_multipart_upload(self, box_name, key_name):
        path = ku.get_object_path("create_multipart_upload", box_name=box_name, key_name=key_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "POST", "", path)
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            return ku.parse_create_multipart_upload(response.text)
     
    # mulitipart upload 수행 작업
    # 분할된 part를 업로드 수행
    def upload_part(self, box_name, key_name, part_number, upload_id, data):
        path = ku.get_object_path("upload_part", box_name=box_name, 
                                 key_name=key_name, upload_id=upload_id, number=part_number)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, 
                                     "PUT", "application/octet-stream", path)
        response = requests.put(url, headers=headers, data=data)
        
        if response.status_code == 200:
            res_headers = response.headers
            etag = res_headers["ETag"]
            clean_etag = etag.replace('"', '')
            return clean_etag     
        
    # multipart upload 작업 정보 조회
    def list_multipart_upload_info(self, box_name):
        path = ku.get_object_path("list_multipart_upload_info", box_name=box_name)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key, "GET", "", path)
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return ku.parse_list_multipart_upload_info(response.text)
        
    # multipart upload 작업 종료
    # 모든 part 정보 upload가 완료되면 수행
    def complete_multipart_upload(self, box_name, key_name, upload_id, parts):
        path = ku.get_object_path("complete_multipart_upload", box_name=box_name, 
                                 key_name=key_name, upload_id=upload_id)
        url = ku.get_object_url(path)
        headers = ku.get_auth_header(self._access_key, self._secret_key,"POST", "application/xml", path)
        body = ku.get_body_multipart_upload(parts)
        response = requests.post(url, headers=headers, data=body)
        
        if response.status_code == 200:
            return True
        return False
    
    # multipart upload 수행
    # create_multipart_upload(), upload_part(), complete_multipart_upload() 등을 활용하여 작업 수행
    def multipart_upload(self, box_name, file_path, key_name):
        try:
            # file 유효성 및 크기 제약 check
            file_size = os.path.getsize(file_path)
            if file_size < MULTIPART_UPLOAD_SIZE:
                max_size = MULTIPART_UPLOAD_SIZE/1024/1024/1024
                raise FileSizeError(f'"{file_path}" size is too small, bigger than {max_size}GB')
        except FileNotFoundError:
            raise Exception(f'"{file_path}" not exist')
            
        upload_id = self.create_multipart_upload(box_name, key_name)
        if upload_id == None:
            return False
        
        parts_list = []
        part_size = MULTIPART_PART_SIZE
        with open(file_path, 'rb') as f:
            part_number = 1
            while True:
                data = f.read(part_size)
                if not data:
                    break
                # 각 Part 업로드
                etag = self.upload_part(box_name, key_name, part_number, upload_id, data)

                part = {"PartNumber": part_number, "ETag": etag}
                part_dict = {"Part" : part}
                parts_list.append(part_dict)
                part_number += 1
        
        multipartupload = {"CompleteMultipartUpload" : parts_list}
        
        if self.complete_multipart_upload(box_name, key_name, upload_id, multipartupload):
            return True
        return False
    
    # BoxInstance return
    def box_instance(self, box_name):
        return ki.BoxInstance(box_name, self)
    
###################################################
#
# class VPC
# csv파일 등을 이용하여 대용량으로 자원을 생성
#
###################################################

class VPC:
    def __init__(self, zone_mgr):
        self.flavor_list = []
        self.subnet_list = []
        self.image_list = []
        self.snapshot_list = []
        self.vm_list = []
        self.pf_list = []
        self.sn_list = []
        self.vm_list = []
        self.lb_list = []
        self.ip_list = []
        self.compute = zone_mgr.compute_resource()
        self.storage = zone_mgr.storage_resource()
        self.network = zone_mgr.network_resource()
        
        zone, zone_name = zone_mgr.get_zone()
        self._zone = zone
        self._zone_name = zone_name
        self._external_id = zone_mgr.external_id
              
    # flavor_list, subnet_list, image_list, snapshot_list 등을 list형태로 저장
    # VM생성 시마다 open API query를 하지 않도록 하기 위해 실행함.
    def _init_query(self, query_type):    
        if query_type == "for_vm":
            self.flavor_list = self.compute.list_flavor_info()
            self.subnet_list = self.network.list_subnet_info()
            self.image_list = self.storage._list_image_info()
            self.snapshot_list = self.storage.list_snapshot_info()
            self.vm_list = self.compute.list_vm_info()
            
        elif query_type == "for_lb":
            self.subnet_list = self.network.list_subnet_info()
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            
        elif query_type == "for_fw":
            self.subnet_list = self.network.list_subnet_info()
            self.pf_list = self.network.list_portforward_info()
            self.sn_list = self.network.list_staticnat_info()
            self.fw_list = self.network.list_firewall_info()
            
        elif query_type == "for_ip":
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            self.ip_list = self.network.list_publicip_info()
            
        elif query_type == "for_delete":
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            self.ip_list = self.network.list_publicip_info()
            self.pf_list = self.network.list_portforward_info()
            self.sn_list = self.network.list_staticnat_info()
            self.fw_list = self.network.list_firewall_info()
            
        elif query_type == "for_validate":
            self.flavor_list = self.compute.list_flavor_info()
            self.subnet_list = self.network.list_subnet_info()
            self.image_list = self.storage._list_image_info()
            self.snapshot_list = self.storage.list_snapshot_info()
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            self.ip_list = self.network.list_publicip_info()
            self.pf_list = self.network.list_portforward_info()
            self.sn_list = self.network.list_staticnat_info()
            self.fw_list = self.network.list_firewall_info()
            
        elif query_type == "for_validate_change":
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            self.flavor_list = self.compute.list_flavor_info()
            
        elif query_type == "for_change":
            self.vm_list = self.compute.list_vm_info()
            self.lb_list = self.network.list_lb_info()
            self.flavor_list = self.compute.list_flavor_info()            
            
    def _get_vm_id(self, vm_name):
        return next((item["vm_id"] for item in self.vm_list if item["vm_name"] == vm_name), None)
    
    def _get_vm_status(self, vm_id):
        return next((item["status"] for item in self.vm_list if item["vm_id"] == vm_id), None)
    
    def _get_vm_privateip(self, vm_name):
        return next((item["subnets"][0]["privateip"] for item in self.vm_list if item["vm_name"] == vm_name), None)
    
    def _get_lb_id(self, lb_name):
        return next((item["lb_id"] for item in self.lb_list if item["lb_name"] == lb_name), None)
    
    def _get_lb_privateip(self, lb_name):
        return next((item["service_ip"] for item in self.lb_list if item["lb_name"] == lb_name), None)
    
    def _get_publicip_id(self, publicip):
        return next((item["publicip_id"] for item in self.ip_list if item["publicip"] == publicip), None)
        
    def _get_flavor_id(self, flavor_name):
        for item in self.flavor_list:
            if item["flavor_name"] == flavor_name:
                return item["flavor_id"]
            
    def _get_subnet_id(self, subnet_name):
        for item in self.subnet_list:
            if item["subnet_name"] == subnet_name:
                return item["subnet_id"]
            
    def _get_image_id_size(self, os_name):        
        # if ku.check_os_name(os_name):
        #     image_name = ku.get_image_name(os_name, self._zone_name)
        # else:
        #     image_name = os_name
            
        image_name = os_name
         
        if image_name == None:
            zone = self._zone_name
            raise Exception(f"'{os_name}' in {zone} does not exist")
            
        for item in self.image_list:
            if item["image_name"] == image_name:
                return item["image_id"], item["min_disk"]
            
    def _get_snapshot_id(self, snapshot_name):
        for item in self.snapshot_list:
            if item["snapshot_name"] == snapshot_name:
                return item["snapshot_id"]
            
    def _get_portforward_id(self, pf_name):
        for item in self.pf_list:
            if item["name"] == pf_name:
                return item["portforward_id"]
            
    def _get_portforward_publicip(self, pf_name):
        for item in self.pf_list:
            if item["name"] == pf_name:
                return item["publicip"]
            
    def _get_portforward_info(self, ipaddr, option):
        pf_list = []
        
        if option == "public":
            key = "publicip"
        else:
            key = "privateip"
        
        for item in self.pf_list:
            if item[key] == ipaddr:
                pf_list.append(item)

        return pf_list
            
    def _get_staticnat_id(self, sn_name):
        for item in self.sn_list:
            if item["name"] == sn_name:
                return item["staticnat_id"]
            
    def _get_staticnat_publicip(self, sn_name):
        for item in self.sn_list:
            if item["name"] == sn_name:
                return item["publicip"]
            
    def _get_staticnat_info(self, ipaddr, option):
        if option == "public":
            key = "publicip"
        else:
            key = "privateip"
            
        for item in self.sn_list:
            if item[key] == ipaddr:
                return item
            
    def _read_vm_list(self, csv_file):
        result = True
        msg = ""
        vm_list = []
        
        try:
            with open(csv_file, mode="r", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 특정 key(userdata)는 예외 처리, 나머지는 공백, 탭, 줄바꿈 제거
                    cleaned_row = {
                        key: value if key == "userdata" else re.sub(r"\s+", " ", value) if isinstance(value, str) else value
                        for key, value in row.items()
                    }
                    no_quota_row = ku.remove_quotes_from_dict_values(cleaned_row)
                    vm_list.append(no_quota_row)  
        except FileNotFoundError:
            result = False
            msg = f"Error: File '{csv_file}' not found."
        except PermissionError:
            result = False
            msg = f"Error: Permission denied for file '{csv_file}'."
        except Exception as e:
            result = False
            msg = f"Unexpected error while processing '{csv_file}': {e}"
                
        return vm_list, result, msg
    
    # chunk_list의 vm 생성
    def _create_vm_chunk_list(self, chunk_list):
        result = True
        msg_list = []
        chunk_ids = []
        key_list = []
        vm_name_list = []
        vm_inst_list = []
        error_vm_list = []
        
        for key_vm in chunk_list:
            key = key_vm["key"]
            vm = key_vm["params"]
            state = key_vm["state"]

            if state == "created":
                msg = f"""'{vm["name"]}'은 기존에 생성된 VM입니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                vm_inst = self._create_vm(vm)
                vm_inst_list.append(vm_inst)
                chunk_ids.append(vm_inst.id)
                key_list.append(key)
                vm_name_list.append(vm["name"])
                time.sleep(1)
                msg = f"""'{vm["name"]}' VM을 생성합니다."""
                ku.append_msg_list(msg_list, key, msg)

        result_tmp = self.compute.wait_until_active(chunk_ids)

        if result_tmp == True:
            for j, key in enumerate(key_list):
                msg = f"""'{vm_name_list[j]}' VM을 생성 완료했습니다."""
                ku.append_msg_list(msg_list, key, msg)
        else:
            self.vm_list = self.compute.list_vm_info()
            for j, vm_id in enumerate(chunk_ids):
                status = self._get_vm_status(vm_id)
                if status == None:
                    msg = f"""'{vm_name_list[j]}' VM 생성을 실패했습니다.(None)"""
                    ku.append_msg_list(msg_list, key_list[j], msg)
                    result = False
                else:
                    if status == "ACTIVE":
                        msg = f"""'{vm_name_list[j]}' VM 생성을 성공했습니다."""
                        ku.append_msg_list(msg_list, key_list[j], msg)
                    else:
                        msg = f"""'{vm_name_list[j]}' VM 생성을 실패했습니다.({status})"""
                        ku.append_msg_list(msg_list, key_list[j], msg)      
                        if vm_inst_list[j].delete() == True:
                            msg = f"""'{vm_name_list[j]}' VM 생성을 실패로 오류 VM을 삭제했습니다."""
                            ku.append_msg_list(msg_list, key_list[j], msg)  
                            error_vm_list.append(chunk_list[j])
                        else:
                            msg = f"""'{vm_name_list[j]}' 오류 VM을 삭제를 실패했습니다."""
                            ku.append_msg_list(msg_list, key_list[j], msg) 
                            result = False
                        time.sleep(1)
                        
        return result, msg_list, error_vm_list
            
    # list 형태의 VM 생성 정보를 기반으로 VM 생성
    def _create_vm_from_list(self, key_vm_list):      
        result = True
        msg_list = []
        
        chunk_size = MAX_VM_CREATE_COUNT
                
        chunk_list = []
        for key_vm in key_vm_list:   
            key = key_vm["key"]
            vm = key_vm["params"]
            state = key_vm["state"]

            if state == "created":
                msg = f"""'{vm["name"]}'은 기존에 생성된 VM입니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                chunk_list.append(key_vm)  
                    
            if len(chunk_list) == chunk_size:
                while(True):
                    result, msgs, error_vm_list = self._create_vm_chunk_list(chunk_list)
                    msg_list = msg_list + msgs
                    if len(error_vm_list) == 0:
                        chunk_list = []
                    else:
                        chunk_list = error_vm_list
                        
                    if result == False:
                        return False, msg_list
                    
                    if len(chunk_list) < chunk_size:
                        break  
                
        if len(chunk_list) != 0:
            while(True):
                result, msgs, error_vm_list = self._create_vm_chunk_list(chunk_list)
                chunk_list = error_vm_list
                msg_list = msg_list + msgs
                if result == False:
                    return False, msg_list
                if len(chunk_list) == 0:
                    break
                     
        return result, msg_list
        
    def _create_vm(self, vm_info):
        # 원본 데이터 조작이 있어 copy하여 사용
        vm = copy.deepcopy(vm_info)

        flavor = self._get_flavor_id(vm["flavor"])
        subnet = self._get_subnet_id(vm["subnet"])
        image_id, image_size = self._get_image_id_size(vm["image"])
        
        if "disks" in vm:
            for disk in vm["disks"]:
                if disk["source_type"] == "snapshot":
                    snapshot_name = disk["snapshot_name"]
                    disk["snapshot_id"] = self._get_snapshot_id(snapshot_name)
                
        # 추가 Disk 설정 정보 조회
        disks = vm["disks"] if "disks" in vm else None
        userdata = vm["userdata"] if "userdata" in vm else None
        fixed_ip = vm["fixed_ip"] if "fixed_ip" in vm else None
            
        return self.compute.create_vm(vm["name"], vm["key"], flavor, subnet, image_id, image_size,
                                      vm["root_vol_type"],fixed_ip, disks, userdata)
    
    def _read_res_list(self, csv_file):
        result = True
        msg = ""
        vm_list = []
        
        try:
            with open(csv_file, mode="r", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 특정 key(userdata)는 예외 처리, 나머지는 공백, 탭, 줄바꿈 제거
                    cleaned_row = {
                        key: re.sub(r"\s+", " ", value) if isinstance(value, str) else value
                        for key, value in row.items()
                    }
                    no_quota_row = ku.remove_quotes_from_dict_values(cleaned_row)
                    vm_list.append(no_quota_row)  
        except FileNotFoundError:
            result = False
            msg = f"Error: File '{csv_file}' not found."
        except PermissionError:
            result = False
            msg = f"Error: Permission denied for file '{csv_file}'."
        except Exception as e:
            result = False
            msg = f"Unexpected error while processing '{csv_file}': {e}"
                
        return vm_list, result, msg
    
    # list형식의 생성 정보를 기반으로 LB 설정 변경
    def _change_lb_from_list(self, key_lb_list):
        new_ip_list = []
        result = True
        msg_list = []
        
        old_lb_list = self.lb_list
            
        for key_lb in key_lb_list:
            key = key_lb["key"]
            lb = key_lb["params"]
                        
            for old_lb in old_lb_list:
                if lb["name"] == old_lb["lb_name"]:
                    lb_update = ku.check_lb_update(lb, old_lb)
                    if lb_update:                        
                        if "healthcheck_url" in lb:
                            healthcheck_url = lb["healthcheck_url"]
                        else:
                            healthcheck_url = None
                            
                        if old_lb["service_type"].lower() == "https":
                            ret = self.network.update_lb(old_lb["lb_id"], lb["option"], lb["healthcheck_type"], healthcheck_url,
                                                        lb["ciphergroup_name"], lb["tlsv1"], lb["tlsv11"], lb["tlsv12"])
                        else:
                            ret = self.network.update_lb(old_lb["lb_id"], lb["option"], lb["healthcheck_type"], healthcheck_url)
                        
                        if ret:
                            msg = f"""'{lb["name"]}' 설정을 변경합니다."""
                            ku.append_msg_list(msg_list, key, msg)
                        else:
                            msg = f"""'{lb["name"]}' 설정을 변경을 실패했습니다."""
                            ku.append_msg_list(msg_list, key, msg)
                            result = False
                        time.sleep(1)
                        
                    server_list = None if "server_list" not in lb else lb["server_list"]
                    # 연결 서버의 유효성 검증 및 정보 조회
                    
                    vm_info_list = []
                    if server_list != None:
                        vm_info_list = self._get_vm_info(server_list)
                    old_server_list = self.network.list_lb_server(old_lb["lb_id"])
                    
                    lb_update = ku.check_lb_server_update(vm_info_list, old_server_list)
                    
                    if lb_update:
                        result_tmp = True
                        for old_vm in old_server_list:
                            result_tmp = self.network.remove_lb_server(old_vm["service_id"])
                            if result_tmp == False:
                                result = False
                                msg = f"""'{lb["name"]}'에서 server_list server({server_list})삭제 실패했습니다."""
                                ku.append_msg_list(msg_list, key, msg)
                                return False, msg_list
                            
                        for vm_info in vm_info_list:
                            result_tmp = self.network.add_lb_server(old_lb["lb_id"], vm_info["id"], 
                                                                  vm_info["privateip"], lb["server_port"])
                            if result_tmp == False:
                                result = False
                                msg = f"""'{lb["name"]}'에서 server_list server({server_list})추가 실패했습니다."""
                                ku.append_msg_list(msg_list, key, msg)
                                return False, msg_list

                        msg = f"""'{lb["name"]}'에서 server_list server({server_list}) 업데이트 수행했습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                                
        return result, msg_list
    
    # list형식의 생성 정보를 기반으로 LB 생성
    def _create_lb_from_list(self, key_lb_list):
        new_ip_list = []
        result = True
        msg_list = []
            
        for key_lb in key_lb_list:
            key = key_lb["key"]
            lb = key_lb["params"]
            state = key_lb["state"]
            
            if state == "created":
                msg = f"""'{lb["name"]}'은 기존에 생성된 LB입니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                lb_inst = self._create_lb(lb, new_ip_list)
                if lb_inst == None:
                    msg = f"""'{lb["name"]}' LB 생성을 실패했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                    result = False
                else:
                    msg = f"""'{lb["name"]}' LB를 생성했습니다."""
                    ku.append_msg_list(msg_list, key, msg)             

                time.sleep(2)
            
        return result, msg_list
        
    def _get_vm_info(self, server_list):        
        server_info_list = []
        for server in server_list:
            server_exist = False
            for vm in self.vm_list:
                if vm["vm_name"] == server:
                    server_info = {}
                    server_info["id"] = vm["vm_id"]
                    server_info["privateip"] = vm["subnets"][0]["privateip"]
                    server_info_list.append(server_info)
                    server_exist = True
                    break
            if server_exist == False:
                raise Exception(f"'{server}' does not exist")
                
        return server_info_list
                    
    def _create_lb(self, lb, new_ip_list):
        subnet_id = self._get_subnet_id(lb["subnet"])
        
        ciphergroup_name = None if "ciphergroup_name" not in lb else lb["ciphergroup_name"]
        tlsv1 = None if "tlsv1" not in lb else lb["tlsv1"]
        tlsv11 = None if "tlsv11" not in lb else lb["tlsv11"]
        tlsv12 = None if "tlsv12" not in lb else lb["tlsv12"]
        service_ip_tmp = None if "service_ip" not in lb else lb["service_ip"]
        healthcheck_url = None if "healthcheck_url" not in lb else lb["healthcheck_url"]
        server_list = None if "server_list" not in lb else lb["server_list"]
        server_port = None if "server_port" not in lb else lb["server_port"]
        
        ku.check_parameter_validation(lb["option"], lb["service_type"], lb["healthcheck_type"],
                                      healthcheck_url, ciphergroup_name, tlsv1, tlsv11, tlsv12)
        
        if service_ip_tmp.startswith("new_"):
            match_item = next((item for item in new_ip_list if item["new"] == service_ip_tmp), None)
            if match_item == None:
                service_ip = None
            else:
                service_ip = match_item["ip"]
        else:
            service_ip = service_ip_tmp
            
        # 연결 서버의 유효성 검증 및 정보 조회
        if server_list != None:
            vm_info_list = self._get_vm_info(server_list)
        
        lb_inst =  self.network.create_lb(lb["name"], lb["option"], lb["service_port"], lb["service_type"],
                                      lb["healthcheck_type"], subnet_id, healthcheck_url, service_ip,
                                      ciphergroup_name, tlsv1, tlsv11, tlsv12)
        
        if lb_inst == None:
            return None
        
        # LB 생성 완료를 위한 1초 대기
        time.sleep(1)
        
        if service_ip == None:
            new_item = {}
            lb_info = lb_inst.info
            new_item["new"] = service_ip_tmp
            new_item["ip"] = lb_info["service_ip"]
            new_ip_list.append(new_item)
            
        # 하위 서버 연결
        if server_list != None:
            if server_port == None:
                raise Exception("if you want to add vm to lb, you have to define server_port")
                
            for vm_info in vm_info_list:
                lb_inst.add_server(vm_info["id"], vm_info["privateip"], server_port)
    
        return lb_inst
        
    # list 형식의 설정 정보를 기반으로 Firewall 설정
    def _set_firewall_from_list(self, key_fw_list, action):
        result = True
        msg_list = []

        for key_fw in key_fw_list:
            key = key_fw["key"]
            for i, fw in enumerate(key_fw["params"]):
                acl_id = ku.search_acl(fw, self.fw_list)
                if acl_id != None:
                    msg = f"""'{i+1}'번째 ACL은 기존에 생성되어 있습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
                else:
                    acl_id = self._set_firewall(fw)
                    msg = f"""'{i+1}'번째 ACL이 설정되었습니다."""
                    ku.append_msg_list(msg_list, key, msg) 
                    time.sleep(1)
            
        return result, msg_list
    
    def _set_firewall(self, fw):
        start_port = None
        end_port = None
        
        if fw["type"] == "net2net":
            src_net_id = self._get_subnet_id(fw["src_net"])
            if fw["dst_net"] == "external":
                dst_net_id = "external"
            else:
                dst_net_id = self._get_subnet_id(fw["dst_net"])
             
            if "start_port" in fw:
                start_port = str(fw["start_port"]) if isinstance(fw["start_port"], int) else fw["start_port"]
            if "end_port" in fw:
                end_port = str(fw["end_port"]) if isinstance(fw["end_port"], int) else fw["end_port"]
                  
                                                                    
            return self.network.set_firewall_net2net(src_net_id, fw["src_cidr"], dst_net_id, fw["dst_cidr"],
                                              fw["protocol"], fw["action"], start_port, end_port)
            
        elif fw["type"] == "port_forward":
            portforward_id = self._get_portforward_id(fw["dst_cidr"])
            return self.network.set_firewall_portforward(portforward_id, fw["src_cidr"])
            
        elif fw["type"] == "static_nat":
            staticnat_id = self._get_staticnat_id(fw["dst_cidr"])
            
            if "start_port" in fw:
                start_port = str(fw["start_port"]) if isinstance(fw["start_port"], int) else fw["start_port"]
            if "end_port" in fw:
                end_port = str(fw["end_port"]) if isinstance(fw["end_port"], int) else fw["end_port"]  
            
            return self.network.set_firewall_staticnat(staticnat_id, fw["src_cidr"], 
                                                fw["protocol"], start_port, end_port)
        
    # firewall 설정 정보를 CSV 형태로 저장
    def firewall_info_to_csv(self, csv_file):
        acl_list = self.network.list_firewall_info()
        data = ku.parse_firewall_info_to_csv(acl_list)
        
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            # CSV의 필드명 추출 (딕셔너리 키)
            fieldnames = data[0].keys()

            # DictWriter 객체 생성
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            # 헤더 작성
            writer.writeheader()

            # 데이터 작성
            for row in data:
                writer.writerow(row)
    
    # list 형식의 설정 정보를 기반으로 ip 생성 및 설정
    def _create_ip_from_list(self, key_ip_list, action):
        new_ip_list = []
        result = True
        msg_list = []
        
        for key_ip in key_ip_list:
            key = key_ip["key"]
            ip = key_ip["params"]
            state = key_ip["state"]
            setting = key_ip["set"]
            
            if setting != "none":
                new_item = {}
                new_item["new"] = ip["public_ip"]
                new_item["ip"] = setting
                new_item["id"] = self._get_publicip_id(setting)
                new_ip_list.append(new_item)
            
        for key_ip in key_ip_list:
            key = key_ip["key"]
            ip = key_ip["params"]
            state = key_ip["state"]
            setting = key_ip["set"]
                                   
            if state == "created":
                msg = f"""'{ip["public_ip"]}' IP는 기존에 생성된 IP가 있습니다."""
                ku.append_msg_list(msg_list, key, msg)
                if action == "all":
                    result = False
            else:     
                result_tmp, msgs = self._create_ip(ip, key, new_ip_list, state, setting)
                if result_tmp == False:
                    result = False
                    
                msg_list = msg_list + msgs
                time.sleep(1)
            
        return result, msg_list
    
    def _create_ip(self, ip, key, new_ip_list, state, setting):
        start_port = None
        end_port = None
        ip_inst = None
        result = True
        msg_list = []
            
        public_ip = ip["public_ip"]
        if public_ip.startswith("new_"):
            if setting == "none":
                match_item = next((item for item in new_ip_list if item["new"] == public_ip), None)
                if match_item == None:
                    new_item = {}
                    ip_inst = self.network.create_publicip()
                    if ip_inst == None:
                        msg = f"""'{ip["public_ip"]}' IP 생성이 실패했습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                        return False, msg_list
                    else:
                        msg = f"""'{ip["public_ip"]}' IP 생성을 성공했습니다."""
                        ku.append_msg_list(msg_list, key, msg)

                    time.sleep(1)
                    new_item["new"] = public_ip
                    new_item["ip"] = ip_inst.ip
                    new_item["id"] = ip_inst.id
                    new_ip_list.append(new_item)
                else:
                    ip_inst = self.network.publicip_instance(match_item["id"])
            else:
                publicip_id = self._get_publicip_id(setting)
                ip_inst = self.network.publicip_instance(publicip_id)
        else:
            publicip_id = self._get_publicip_id(public_ip)
            ip_inst = self.network.publicip_instance(publicip_id)
                             
        if ip["target"] == "vm":
            private_ip = self._get_vm_privateip(ip["target_name"])
        elif ip["target"] == "lb":
            private_ip = self._get_lb_privateip(ip["target_name"])    
            
        if ip["type"] == "port_forward":
            if setting == "none":
                ret = ip_inst.set_portforward(private_ip, ip["private_port"], ip["public_port"], ip["protocol"])
                time.sleep(1)
                if ret == None:
                    msg = f"""'{ip["public_ip"]}' port forward설정을 실패했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                    result = False
                else:
                    msg = f"""'{ip["public_ip"]}' port forward설정을 성공했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                
        elif ip["type"] == "static_nat":
            if setting == "none":
                ret = ip_inst.set_staticnat(private_ip)
                time.sleep(1)
                if ret == None:
                    msg = f"""'{ip["public_ip"]}' static nat설정을 실패했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                    result = False
                else:
                    msg = f"""'{ip["public_ip"]}' static nat설정을 성공했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
            
        return result, msg_list
        
    def validate_create_res_from_dict(self, json_form, action="all"):
        result_tot = True
        msg_list = []
        
        if action != "all" and action != "remain":
            msg = "action 필드는 'all'과 'remain'만 가능합니다."
            ku.append_msg_list(msg_list, "param_error", msg) 
            return False, msg_list
                
        keys_list = list(json_form["resources"].keys())      
        
        key_vm_list = []
        key_lb_list = []
        key_ip_list = []
        key_fw_list = []
        
        # 아래 형식으로 변환
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            json_form["resources"][key]["key"] = key
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
            elif res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
            elif res_type == "publicip":
                key_ip_list.append(json_form["resources"][key])
            elif res_type == "firewall":
                key_fw_list.append(json_form["resources"][key])
            else:
                msg = f"""'type'값 '{res_type}'은 유효하지 않습니다. options : vm, lb, publicip, firewall"""
                ku.append_msg_list(msg_list, key, msg) 
                return False, msg_list
         
        self._init_query("for_validate")
        
        if len(key_vm_list) > 0:
            result, msgs = ku.validate_vm_list(key_vm_list, self.flavor_list, self.subnet_list, 
                                              self.image_list, self.snapshot_list, self.vm_list, self._zone_name, action)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
        
        if len(key_lb_list) > 0:
            result, msgs = ku.validate_lb_list(key_lb_list, self.subnet_list, self.vm_list, self.lb_list, action)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
            
        if len(key_ip_list) > 0:
            result, msgs = ku.validate_ip_list(key_ip_list, self.vm_list, self.lb_list, self.ip_list, self.pf_list, self.sn_list, action)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
                
            self._set_nat_name(json_form)
            
        if len(key_fw_list) > 0:
            result, msgs = ku.validate_firewall_list(key_fw_list, self.subnet_list, self.pf_list, self.sn_list, self.fw_list, action)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
                            
        # "@res"의 유효성 검증
        result, msgs = ku.validate_res_name(keys_list, json_form)   
        msg_list = msg_list + msgs
        if result == False:
            result_tot = False
                    
        return result_tot, msg_list
      
    def validate_create_res_from_json(self, json_file, action="all"):
        result = True
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
            
        if "resources" not in json_form:
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
        
        return self.validate_create_res_from_dict(json_form, action)
    
    # publicip의 nat_name을 가져온다.
    def _set_nat_name(self, json_form):
        keys_list = list(json_form["resources"].keys()) 
                
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            params = json_form["resources"][key]["params"]
            
            if res_type == "publicip":
                json_form["resources"][key]["state"] = "none"
                json_form["resources"][key]["nat_name"] = "none"
                if params["type"] == "static_nat":
                    if params["target"] == "vm":
                        private_ip = self._get_vm_privateip(params["target_name"])
                    else:
                        private_ip = self._get_lb_privateip(params["target_name"])
                        
                    if private_ip == None:
                        continue
                    else:
                        nat_info = self._get_staticnat_info(private_ip, "private")
                        if nat_info:
                            json_form["resources"][key]["nat_name"] = nat_info["name"]
                            json_form["resources"][key]["state"] = "created"
                        
                else:
                    private_ip = self._get_vm_privateip(params["target_name"])
                        
                    if private_ip == None:
                        continue
                    else:
                        nat_info_list = self._get_portforward_info(private_ip, "private")
                        for nat_info in nat_info_list:
                            if ku.str_to_int(params["private_port"]) == ku.str_to_int(nat_info["private_port"]):
                                json_form["resources"][key]["nat_name"] = nat_info["name"]
                                json_form["resources"][key]["state"] = "created"
                                break
                            
    def create_res_from_dict(self, json_form, action="all"):
        result = True
        msg_list = []
        
        # validation 검사 수행, 여기서 init_query 수행
        result_tmp, msgs = self.validate_create_res_from_dict(json_form, action)
        if result_tmp == False:
            return False, msgs
        
        keys_list = list(json_form["resources"].keys()) 
        
        key_vm_list = []
        key_lb_list = []
        key_ip_list = []
        key_fw_list = []
        
        # 아래 형식으로 변환하여 수행
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        
        # vm 생성
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
                
        result_tmp, msgs = self._create_vm_from_list(key_vm_list)
        msg_list = msg_list + msgs
        if result_tmp == False:
            # VM 생성을 실패하면 이후 생성 작업을 수행하지 않음.
            return False, msg_list
            
        # vm_list update
        time.sleep(1)
        self.vm_list = self.compute.list_vm_info()
                                   
        # lb parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="lb")
        
        # lb 생성
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
                
        result_tmp, msgs = self._create_lb_from_list(key_lb_list)
        msg_list = msg_list + msgs
        if result_tmp == False:
            # LB 생성을 실패하면 이후 생성 작업을 수행하지 않음.
            return False, msg_list
        
        # lb_list update
        time.sleep(1)
        self.lb_list = self.network.list_lb_info()
    
        # ip parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="publicip")
        
        # ip 생성
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "publicip":
                key_ip_list.append(json_form["resources"][key])
                
        result_tmp, msgs = self._create_ip_from_list(key_ip_list, action)
        msg_list = msg_list + msgs
        if result_tmp == False:
            result = False
        
        # nat_name 가져오기
        time.sleep(1)
        self._init_query("for_fw")
        self._set_nat_name(json_form)
        
        # firewall parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="firewall")
                
        # firewall 설정
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "firewall":
                key_fw_list.append(json_form["resources"][key])
                    
        result_tmp, msgs = self._set_firewall_from_list(key_fw_list, action)
        msg_list = msg_list + msgs
        if result_tmp == False:
            result = False
        
        return result, msg_list
        
    def create_res_from_json(self, json_file, action="all"):
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
        
        if "resources" not in json_form:
            result = False
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return result, msg_list
        
        return self.create_res_from_dict(json_form, action)
    
    def validate_delete_res_from_dict(self, json_form, action="all"):
        result = True
        msg_list = []
        
        if action != "all" and action != "remain":
            msg = "action 필드는 'all'과 'remain'만 가능합니다."
            ku.append_msg_list(msg_list, "param_error", msg) 
            return False, msg_list
                
        keys_list = list(json_form["resources"].keys()) 
        
        key_vm_list = []
        key_lb_list = []
        key_ip_list = []
        key_fw_list = []
        
        # 아래 형식으로 변환
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            json_form["resources"][key]["key"] = key
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
            elif res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
            elif res_type == "publicip":
                key_ip_list.append(json_form["resources"][key])
            elif res_type == "firewall":
                continue
            else:
                msg = f"""'{key}' 항목의 'type'값 '{res_type}'은 유효하지 않습니다. options : vm, lb, publicip, firewall"""
                ku.append_msg_list(msg_list, key, msg)
                return False, msg_list
                
        self._init_query("for_delete")
        
        if len(key_vm_list) > 0:
            result_tmp, msgs = ku.validate_delete_vm_list(key_vm_list, self.vm_list, action)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
        
        if len(key_lb_list) > 0:
            result_tmp, msgs = ku.validate_delete_lb_list(key_lb_list, self.lb_list, action)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
                
        # ip parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="publicip")
        
        # nat_name 가져오기
        self._set_nat_name(json_form)
            
        if len(key_ip_list) > 0:
            result_tmp, msgs = ku.validate_delete_ip_list(key_ip_list, self.ip_list, self, action)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
        
        # firewall parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="firewall")
        
        # firewall list가져오기
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "firewall":
                key_fw_list.append(json_form["resources"][key])
                    
        if len(key_fw_list) > 0:
            result_tmp, msgs = ku.validate_delete_firewall_list(key_fw_list, self.fw_list, action)  
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        return result, msg_list
        
    def validate_delete_res_from_json(self, json_file, action="all"):
        result = True
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
            
        if "resources" not in json_form:
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
        
        return self.validate_delete_res_from_dict(json_form, action)      
    
    # fw_list를 삭제합니다.
    def _unset_firewall_list(self, key_fw_list, action):
        result = True
        msg_list = []
                  
        for key_fw in key_fw_list:
            key = key_fw["key"]
            fw_list = key_fw["params"]
            
            for i, fw in enumerate(fw_list):
                acl_id = ku.search_acl(fw, self.fw_list)

                if acl_id == None:
                    msg = f"""{i+1}번째 acl이 검색되지 않습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
                else:
                    res = self.network.unset_firewall(acl_id)
                    if res:
                        msg = f"""{i+1}번째 acl이 삭제되었습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                    else:
                        result = False
                        msg = f"""{i+1}번째 acl 삭제가 실패했습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                    time.sleep(1)
                    
        return result, msg_list
    
    # ip_list를 삭제합니다.
    def _delete_ip_list(self, key_ip_list):
        result = True
        msg_list = []

        for key_ip in key_ip_list:
            key = key_ip["key"]
            state = key_ip["state"]
            ip = key_ip["params"]
            setting = key_ip["set"]
            
            if key_ip["nat_name"] == "none":
                continue
            
            if ip["type"] == "static_nat":
                sn_id = self._get_staticnat_id(key_ip["nat_name"])                
                res = self.network.unset_staticnat(sn_id)
                if res:
                    msg = f"""'{key_ip["nat_name"]}'static nat 설정이 삭제되었습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                else:
                    result = False
                    msg = f"""'{key_ip["nat_name"]}'static nat 설정 삭제가 실패했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                
                if ip["public_ip"].startswith("new_"):
                    time.sleep(1)
                    public_ip = self._get_staticnat_publicip(key_ip["nat_name"])
                else:
                    public_ip = ip["public_ip"]
                    
                ip_id = self._get_publicip_id(public_ip)
                res = self.network.delete_publicip(ip_id)
                if res:
                    msg = f"""'{public_ip}'IP주소가 삭제되었습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                else:
                    result = False
                    msg = f"""'{public_ip}'IP주소 삭제가 실패했습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                
            elif ip["type"] == "port_forward":
                pf_id = self._get_portforward_id(key_ip["nat_name"])
                res = self.network.unset_portforward(pf_id)
                if res:
                    msg = f"""'{key_ip["nat_name"]}'port forward 설정이 삭제되었습니다."""
                    ku.append_msg_list(msg_list, key, msg)
                else:
                    if setting != "none":
                        result = False
                        msg = f"""'{key_ip["nat_name"]}'port forward 설정 삭제가 실패했습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                    
                if ip["public_ip"].startswith("new_"):
                    time.sleep(1)
                    public_ip = self._get_portforward_publicip(key_ip["nat_name"])
                else:
                    public_ip = ip["public_ip"]
                    
                pf_list = self.network.get_portforward_info_of_publicip(public_ip)
                if len(pf_list) == 0:
                    ip_id = self._get_publicip_id(public_ip)
                    res = self.network.delete_publicip(ip_id)
                    if res:
                        msg = f"""'{public_ip}' IP주소가 삭제되었습니다."""
                        ku.append_msg_list(msg_list, key, msg)
                    else:
                        if state != "none":
                            result = False
                            msg = f"""'{public_ip}' IP주소 삭제가 실패했습니다."""
                            ku.append_msg_list(msg_list, key, msg)
            time.sleep(1)
                    
        return result, msg_list
    
    # lb_list를 삭제합니다.
    def _delete_lb_list(self, key_lb_list):
        result = True
        msg_list = []
        
        for key_lb in key_lb_list:
            key = key_lb["key"]
            lb = key_lb["params"]
            state = key_lb["state"]
            
            if state == "none":
                continue
            
            lb_id = self._get_lb_id(lb["name"])
            res = self.network.delete_lb(lb_id)
            
            if res:
                msg = f"""'{lb["name"]}' LB가 삭제되었습니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                msg = f"""'{lb["name"]}' LB 삭제가 실패했습니다."""
                ku.append_msg_list(msg_list, key, msg)
                result = False
            time.sleep(1)
                
        return result, msg_list
    
    # vm_list를 삭제합니다.
    def _delete_vm_list(self, key_vm_list):
        result = True
        msg_list = []
        
        for key_vm in key_vm_list:
            key = key_vm["key"]
            vm = key_vm["params"]
            state = key_vm["state"]
            
            if state == "none":
                continue
            
            vm_id = self._get_vm_id(vm["name"])
            res = self.compute.delete_vm(vm_id)
            
            if res:
                msg = f"""'{vm["name"]}' VM이 삭제되었습니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                result = False
                msg = f"""'{vm["name"]}' VM 삭제가 실패했습니다."""
                ku.append_msg_list(msg_list, key, msg)
            time.sleep(1)
                
        return result, msg_list
        
    def delete_res_from_dict(self, json_form, action="all"):
        result = True
        msg_list = []
        
        # validation 검사 수행, 여기서 init_query 수행
        result_tmp, msgs = self.validate_delete_res_from_dict(json_form, action)
        if result_tmp == False:
            msg_list = msg_list + msgs
            return False, msg_list
        
        print("delete processing...")
                
        keys_list = list(json_form["resources"].keys()) 
        
        key_vm_list = []
        key_lb_list = []
        key_ip_list = []
        key_fw_list = []
        
        # 아래 형식으로 변환
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            json_form["resources"][key]["key"] = key
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
            elif res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
            elif res_type == "publicip":
                key_ip_list.append(json_form["resources"][key])
            elif res_type == "firewall":
                key_fw_list.append(json_form["resources"][key])
            else:
                msg = f"""'type'값 '{res_type}'은 유효하지 않습니다. options : vm, lb, publicip, firewall"""
                ku.append_msg_list(msg_list, key, msg) 
                return False, msg_list
        
        ######### 삭제 수행 #################

        if len(key_fw_list) > 0:
            result_tmp, msgs = self._unset_firewall_list(key_fw_list, action)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        if len(key_ip_list) > 0:
            result_tmp, msgs = self._delete_ip_list(key_ip_list)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        if len(key_lb_list) > 0:
            result_tmp, msgs = self._delete_lb_list(key_lb_list)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        if len(key_vm_list) > 0:
            result_tmp, msgs = self._delete_vm_list(key_vm_list)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        return result, msg_list
        
    # json 정의 resource를 삭제
    def delete_res_from_json(self, json_file, action="all"):
        result = True
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
            
        if "resources" not in json_form:
            result = False
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return result, msg_list
        
        return self.delete_res_from_dict(json_form, action)
    
    # csv file을 기반으로 json form 생성
    def _csv_to_json_form(self, vm_csv, lb_csv, ip_csv, fw_csv):
        result = True
        msg_list = []
        
        new_vm_list = []
        new_lb_list = []
        new_ip_list = []
        new_fw_list = []
        
        if vm_csv:
            vm_list, result_tmp, msg = self._read_vm_list(vm_csv)
            if result_tmp == False:
                ku.append_msg_list(msg_list, vm_csv, msg)
                result = False
            else:
                new_vm_list, result_tmp, msgs = ku.change_vm_list_shape(vm_list, vm_csv)
                if result_tmp == False:
                    msg_list = msg_list + msgs
                    result = False
            
        if lb_csv:
            lb_list, result_tmp, msg = self._read_res_list(lb_csv)
            if result_tmp == False:
                ku.append_msg_list(msg_list, lb_csv, msg)
                result = False
            else:
                new_lb_list, result_tmp, msgs = ku.change_lb_list_shape(lb_list, lb_csv)
                if result_tmp == False:
                    msg_list = msg_list + msgs
                    result = False
            
        if ip_csv:
            ip_list, result_tmp, msg = self._read_res_list(ip_csv)
            if result_tmp == False:
                ku.append_msg_list(msg_list, ip_csv, msg)
                result = False
            else:
                new_ip_list, result_tmp, msgs = ku.change_ip_list_shape(ip_list, ip_csv)
                if result_tmp == False:
                    msg_list = msg_list + msgs
                    result = False
            
        if fw_csv:
            fw_list, result_tmp, msg = self._read_res_list(fw_csv)
            if result_tmp == False:
                ku.append_msg_list(msg_list, fw_csv, msg)
                result = False
            else:
                new_fw_list = ku.change_fw_list_shape(fw_list)
                
        if vm_csv == None and lb_csv == None and ip_csv == None and fw_csv == None:
            result = False
            msg = "csv파일은 1개 이상이어야 합니다."
            ku.append_msg_list(msg_list, "csv_error", msg)
                    
        if result == False:
            return None, False, msg_list
        
        # json_form 만들기
        json_form = {
            "ktcformversion" : "2025-02-11",
            "description" : "json form from csv files",
            "resources" : {}
        }
        
        if len(new_vm_list) != 0:
            for vm in new_vm_list:
                if len(vm["res_name"]) == 0:
                    res_name = ku.random_res_name("vm_res_")
                else:
                    res_name = vm["res_name"]
                del vm["res_name"]
                vm_value = {}
                vm_value["type"] = "vm"
                vm_value["params"] = vm
                json_form["resources"][res_name] = vm_value
        
        if len(new_lb_list) != 0:
            for lb in new_lb_list:
                if len(lb["res_name"]) == 0:
                    res_name = ku.random_res_name("lb_res_")
                else:
                    res_name = lb["res_name"]
                del lb["res_name"]
                lb_value = {}
                lb_value["type"] = "lb"
                lb_value["params"] = lb
                json_form["resources"][res_name] = lb_value
                
        if len(new_ip_list) != 0:
            for ip in new_ip_list:
                if len(ip["res_name"]) == 0:
                    res_name = ku.random_res_name("ip_res_")
                else:
                    res_name = ip["res_name"]
                del ip["res_name"]
                ip_value = {}
                ip_value["type"] = "publicip"
                ip_value["params"] = ip
                json_form["resources"][res_name] = ip_value
            
        if len(new_fw_list) != 0:
            res_name = ku.random_res_name("fw_res_")
            fw_value = {}
            fw_value["type"] = "firewall"
            fw_value["params"] = new_fw_list
            json_form["resources"][res_name] = fw_value
            
        return json_form, result, msg_list
    
    # list 형태의 VM 생성 정보를 기반으로 VM spec변경
    def _change_vm_from_list(self, key_vm_list):      
        result = True
        msg_list = []
                        
        old_vm_list = self.vm_list
        chunk_size = MAX_VM_CREATE_COUNT
        
        change_vm_list = []
        for key_vm in key_vm_list:   
            vm = key_vm["params"]
            key = key_vm["key"]
            
            for old_vm in old_vm_list:
                if vm["name"] == old_vm["vm_name"]:
                    if vm["flavor"] != old_vm["flavor_name"]:
                        key_vm["old_vm_id"] = old_vm["vm_id"]
                        change_vm_list.append(key_vm)
        
        chunk_list = []
        for key_vm in change_vm_list:   
            vm = key_vm["params"]
            key = key_vm["key"]
            
            chunk_list.append(key_vm)  
            
            if len(chunk_list) == chunk_size:
                result, msgs = self._change_vm_chunk_list(chunk_list)
                msg_list = msg_list + msgs
                chunk_list = []

                if result == False:
                    return False, msg_list
                        
        if len(chunk_list) != 0:
            result, msgs = self._change_vm_chunk_list(chunk_list)
            msg_list = msg_list + msgs
            if result == False:
                return False, msg_list
                    
        return result, msg_list
    
    def _change_vm_chunk_list(self, chunk_list):
        result = True
        msg_list = []
        chunk_ids = []
        key_list = []
        vm_name_list = []
        
        for key_vm in chunk_list:
            key = key_vm["key"]
            vm = key_vm["params"]
            vm_id = key_vm["old_vm_id"]
            chunk_ids.append(vm_id)
            key_list.append(key)
            vm_name_list.append(vm["name"])
            
            flavor_id = self._get_flavor_id(vm["flavor"])
            ret = self.compute.change_vm(vm_id, flavor_id)

            if ret == True:
                msg = f"""'{vm["name"]}' 스팩 변경을 진행합니다."""
                ku.append_msg_list(msg_list, key, msg)
            else:
                msg = f"""'{vm["name"]}' 스팩 변경을 실패했습니다."""
                ku.append_msg_list(msg_list, key, msg)
                result = False
            time.sleep(1)

        result_tmp = self.compute.wait_until_active(chunk_ids)

        if result_tmp == True:
            for j, key in enumerate(key_list):
                msg = f"""'{vm_name_list[j]}' VM 변경을 완료했습니다."""
                ku.append_msg_list(msg_list, key, msg)
        else:
            result = False
            
        return result, msg_list
    
    def validate_change_res_from_dict(self, json_form):
        result_tot = True
        msg_list = []
                
        keys_list = list(json_form["resources"].keys())      
        
        key_vm_list = []
        key_lb_list = []
        
        # 아래 형식으로 변환
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            json_form["resources"][key]["key"] = key
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
            elif res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
            elif res_type == "publicip":
                continue
            elif res_type == "firewall":
                continue
            else:
                msg = f"""'type'값 '{res_type}'은 유효하지 않습니다. options : vm, lb, publicip, firewall"""
                ku.append_msg_list(msg_list, key, msg) 
                return False, msg_list
         
        self._init_query("for_validate_change")
        
        if len(key_vm_list) > 0:
            result, msgs = ku.validate_change_vm_list(key_vm_list, self.flavor_list, self.vm_list)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
        
        if len(key_lb_list) > 0:
            result, msgs = ku.validate_change_lb_list(key_lb_list, self.lb_list, self.vm_list)
            
            msg_list = msg_list + msgs
            if result == False:
                result_tot = False
                
        # "@res"의 유효성 검증
        result, msgs = ku.validate_res_name(keys_list, json_form)   
        msg_list = msg_list + msgs
        if result == False:
            result_tot = False
                    
        return result_tot, msg_list
    
    def change_res_from_dict(self, json_form):
        result = True
        msg_list = []
        
        # validation 검사 수행, 여기서 init_query 수행
        result_tmp, msgs = self.validate_change_res_from_dict(json_form)
        if result_tmp == False:
            return False, msgs
        
        keys_list = list(json_form["resources"].keys()) 
        
        key_vm_list = []
        key_lb_list = []
        
        # 아래 형식으로 변환하여 수행
        """
        {
            "key" : xxx,
            "type" : xxx,
            "params" : {}
        }
        """
        
        # lb parameter 업데이트
        ku.update_res_name(keys_list, json_form, res_key_type="lb")
        
        # vm 생성
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            
            if res_type == "vm":
                key_vm_list.append(json_form["resources"][key])
            elif res_type == "lb":
                key_lb_list.append(json_form["resources"][key])
                
        self._init_query("for_change")
                
        if len(key_vm_list) > 0:
            result_tmp, msgs = self._change_vm_from_list(key_vm_list)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
            
        if len(key_lb_list) > 0:
            result_tmp, msgs = self._change_lb_from_list(key_lb_list)
            msg_list = msg_list + msgs
            if result_tmp == False:
                result = False
        
        return result, msg_list
    
    def validate_change_res_from_json(self, json_file):
        result = True
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
            
        if "resources" not in json_form:
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
        
        return self.validate_change_res_from_dict(json_form, action)
    
    def change_res_from_json(self, json_file):
        msg_list = []
        
        result, msg, json_form = ku.read_json_form(json_file)
        if result == False:
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return False, msg_list
        
        if "resources" not in json_form:
            result = False
            msg = "'resources' not found"
            ku.append_msg_list(msg_list, "syntax_error", msg)
            return result, msg_list
        
        return self.change_res_from_dict(json_form, action)
                
                
    def create_res_from_csv(self, vm_csv=None, lb_csv=None, ip_csv=None, fw_csv=None, action="all"):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, lb_csv, ip_csv, fw_csv)
        
        if result == True:
            return self.create_res_from_dict(json_form, action)
  
        return result, msgs
    
    def validate_create_res_from_csv(self, vm_csv=None, lb_csv=None, ip_csv=None, fw_csv=None, action="all"):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, lb_csv, ip_csv, fw_csv)
    
        if result == True:
            return self.validate_create_res_from_dict(json_form, action)
        
        return result, msgs
    
    def delete_res_from_csv(self, vm_csv=None, lb_csv=None, ip_csv=None, fw_csv=None, action="all"):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, lb_csv, ip_csv, fw_csv)
        
        if result == True:
            return self.delete_res_from_dict(json_form, action)
        
        return result, msgs
    
    def validate_delete_res_from_csv(self, vm_csv=None, lb_csv=None, ip_csv=None, fw_csv=None, action="all"):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, lb_csv, ip_csv, fw_csv)
    
        if result == True:
            return self.validate_delete_res_from_dict(json_form, action)
        
        return result, msgs
    
    def change_res_from_csv(self, vm_csv):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, None, None, None)
        
        if result == True:
            return self.change_res_from_dict(json_form)
  
        return result, msgs
            
    def validate_change_res_from_csv(self, vm_csv):
        json_form, result, msgs = self._csv_to_json_form(vm_csv, None, None, None)
    
        if result == True:
            return self.validate_change_res_from_dict(json_form)
        
        return result, msgs
        
        
        
        
            
        
        

            
            