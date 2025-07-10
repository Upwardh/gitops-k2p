###############################################################################################
#
# Copyright (c) 2024 kt cloud, All rights reserved.
#
# kclutil.py v0.5.2
# Released on 2025.6.17
# ktcloud open API 제어를 위한 low level 함수 제공
#
###############################################################################################

import json
import yaml
import base64
import time
import random
import string
import ipaddress
from urllib.parse import urlencode
from datetime import datetime
import hmac
import hashlib
import xmltodict
import xml.etree.ElementTree as ET
import requests
import re
from collections import Counter, defaultdict
import copy

VM_ACTIVE_INTERVAL = 20
VM_SHUTOFF_INTERVAL = 10
NAS_AVAILABLE_INTERVAL = 10
VOLUME_AVAILABLE_INTERVAL = 5
VOLUME_INUSE_INTERVAL = 5

# LB 설정 관련 옵션 사항
lb_options_list = [
    "roundrobin",
    "leastconnection",
    "leastresponse",
    "sourceiphash",
    "srcipsrcporthash",
]
service_type_list = ["https", "http", "sslbridge", "tcp", "ftp"]
healthcheck_type_list = ["http", "https", "tcp"]
tls_options_list = ["ENABLED", "DISABLED"]
ciphergroup_list = [
    "Default",
    "Recommend-2016-12",
    "PCI-DSS-3.2-2016-12",
    "2018-2Q-Cisco-REC-B",
    "Recommend-2025-05",
]
firewall_type_list = ["net2net", "port_forward", "static_nat"]
firewall_protocol_list = ["TCP", "UDP", "ICMP", "FTP", "ALL"]
nat_ip_type_list = ["port_forward", "static_nat"]

# firewall ACL 설정이 가능한 protocol
firewall_protocol = ["TCP", "UDP", "ICMP", "FTP", "ALL"]

# firewall ACL 설정이 가능한 action
firewall_action = ["allow", "deny"]

# volume생성이 가능한 volume type
volume_types = ["HDD", "SSD"]

# open API 이용이 가능한 존
zone_list = ["DX-M1", "DX-Central", "DX-DCN-CJ", "DX-G", "DX-G-YS"]

# disk_sourde_type
disk_source_type_list = ["blank", "snapshot"]


# multipart upload 관련 Exception
class FileSizeError(Exception):
    """사용자 정의 예외 클래스"""

    def __init__(self, message):
        # Exception 클래스의 __init__ 메서드를 호출하여 예외 메시지 전달
        super().__init__(message)


#########################################################
# image list : OS에 따른 이미지 이름 매핑
#########################################################
# image_list_dict = {
#       "ubuntu-24.04-64bit" : {
#         "DX-M1": "ubuntu-24.04-64bit-240503",
#         "DX-Central": "ubuntu-24.04-64bit-240503",
#         "DX-DCN-CJ": None,
#         "DX-G": "ubuntu-24.04-64bit-240503",
#         "DX-G-YS": "ubuntu-24.04-64bit-240503"
#       },
#       "ubuntu-22.04-64bit" : {
#         "DX-M1": "ubuntu-22.04-64bit-240405",
#         "DX-Central": "ubuntu-22.04-64bit-240405",
#         "DX-DCN-CJ": "ubuntu-22.04-64bit-231016",
#         "DX-G": "ubuntu-22.04-64bit-240405",
#         "DX-G-YS": "ubuntu-22.04-64bit-240405"
#       },
#       "ubuntu-20.04-64bit" : {
#         "DX-M1": "ubuntu-20.04-64bit-240405",
#         "DX-Central": "ubuntu-20.04-64bit-240405",
#         "DX-DCN-CJ": "ubuntu-20.04-64bit_240320",
#         "DX-G": "ubuntu-20.04-64bit-240405",
#         "DX-G-YS": "ubuntu-20.04-64bit-240405"
#       },
#       "ubuntu-18.04-64bit" : {
#         "DX-M1": "ubuntu-18.04-64bit-230309",
#         "DX-Central": "ubuntu-18.04-64bit-230309",
#         "DX-DCN-CJ": None,
#         "DX-G": "ubuntu-18.04-64bit-230309",
#         "DX-G-YS": "ubuntu-18.04-64bit-230309"
#       },
#       "rhel-9.4-64bit" : {
#         "DX-M1": "rhel-9.4-64bit-240514",
#         "DX-Central": "rhel-9.4-64bit-240514",
#         "DX-DCN-CJ": None,
#         "DX-G": "rhel-9.4-64bit-240514",
#         "DX-G-YS": "rhel-9.4-64bit-240514"
#       },
#       "rhel-8.10-64bit" : {
#         "DX-M1": "rhel-8.10-64bit-240603",
#         "DX-Central": "rhel-8.10-64bit-240603",
#         "DX-DCN-CJ": None,
#         "DX-G": "rhel-8.10-64bit-240603",
#         "DX-G-YS": "rhel-8.10-64bit-240603"
#       },
#       "rhel-8.8-64bit" : {
#         "DX-M1": "rhel-8.8-64bit-240514",
#         "DX-Central": "rhel-8.8-64bit-240514",
#         "DX-DCN-CJ": None,
#         "DX-G": "rhel-8.8-64bit-240514",
#         "DX-G-YS": "rhel-8.8-64bit-240514"
#       },
#       "rhel-8.4-64bit" : {
#         "DX-M1": "rhel-8.4-64bit-240405",
#         "DX-Central": "rhel-8.4-64bit-240405",
#         "DX-DCN-CJ": None,
#         "DX-G": "rhel-8.4-64bit-240405",
#         "DX-G-YS": "rhel-8.4-64bit-240405"
#       },
#       "rhel-8.3-64bit" : {
#         "DX-M1": "rhel-8.3-64bit-230315",
#         "DX-Central": "rhel-8.3-64bit-230315",
#         "DX-DCN-CJ": None,
#         "DX-G": "rhel-8.3-64bit-230315",
#         "DX-G-YS": "rhel-8.3-64bit-230315"
#       },
#       "rocky-9.4-64bit" : {
#         "DX-M1": "rocky-9.4-64bit-240603",
#         "DX-Central": "rocky-9.4-64bit-240603",
#         "DX-DCN-CJ": "rocky-9.4-64bit-240603",
#         "DX-G": "rocky-9.4-64bit-240603",
#         "DX-G-YS": "rocky-9.4-64bit-240603"
#       },
#       "rocky-9.2-64bit" : {
#         "DX-M1": "rocky-9.2-64bit-240405",
#         "DX-Central": "rocky-9.2-64bit-240405",
#         "DX-DCN-CJ": "rocky-9.2-64bit-231023",
#         "DX-G": "rocky-9.2-64bit-240405",
#         "DX-G-YS": "rocky-9.2-64bit-240405"
#       },
#       "rocky-8.10-64bit" : {
#         "DX-M1": "rocky-8.10-64bit-240603",
#         "DX-Central": "rocky-8.10-64bit-240603",
#         "DX-DCN-CJ": "rocky-8.10-64bit-202414",
#         "DX-G": "rocky-8.10-64bit-240603",
#         "DX-G-YS": "rocky-8.10-64bit-240603"
#       },
#       "rocky-8.9-64bit" : {
#         "DX-M1": "rocky-8.9-64bit-240513",
#         "DX-Central": "rocky-8.9-64bit-240513",
#         "DX-DCN-CJ": None,
#         "DX-G": "rocky-8.9-64bit-240513",
#         "DX-G-YS": "rocky-8.9-64bit-240513"
#       },
#       "rocky-8.8-64bit" : {
#         "DX-M1": "rocky-8.8-64bit-231023",
#         "DX-Central": "rocky-8.8-64bit-231023",
#         "DX-DCN-CJ": "rocky-8.8-64bit-231023",
#         "DX-G": "rocky-8.8-64bit-231023",
#         "DX-G-YS": "rocky-8.8-64bit-231023"
#       },
#       "win2022std-64bit" : {
#         "DX-M1": "windows-2022-std-64bit-240402",
#         "DX-Central": "windows-2022-std-64bit-240402",
#         "DX-DCN-CJ": "windows-2022-std-64bit-230816",
#         "DX-G": "windows-2022-std-64bit-240402",
#         "DX-G-YS": "windows-2022-std-64bit-240402"
#       },
#       "win2019std-64bit" : {
#         "DX-M1": "windows-2019-std-64bit-230816",
#         "DX-Central": "windows-2019-std-64bit-230816",
#         "DX-DCN-CJ": None,
#         "DX-G": "windows-2019-std-64bit-230816",
#         "DX-G-YS": "windows-2019-std-64bit-230816"
#       },
#       "win2016std-64bit" : {
#         "DX-M1": "windows-2016-std-64bit-240402",
#         "DX-Central": "windows-2016-std-64bit-240402",
#         "DX-DCN-CJ": None,
#         "DX-G": "windows-2016-std-64bit-240402",
#         "DX-G-YS": "windows-2016-std-64bit-240402"
#       },
#       "centos-7.9-64bit" : {
#         "DX-M1": "centos-7.9-64bit-230309",
#         "DX-Central": "centos-7.9-64bit-230309",
#         "DX-DCN-CJ": None,
#         "DX-G": "centos-7.9-64bit-230309",
#         "DX-G-YS": "centos-7.9-64bit-230309"
#       },
#       "centos-7.8-64bit" : {
#         "DX-M1": "centos-7.8-64bit-230309",
#         "DX-Central": "centos-7.8-64bit-230309",
#         "DX-DCN-CJ": None,
#         "DX-G": "centos-7.8-64bit-230309",
#         "DX-G-YS": "centos-7.8-64bit-230309"
#       },
#       "centos-7.6-64bit" : {
#         "DX-M1": "centos-7.6-64bit-230309",
#         "DX-Central": "centos-7.6-64bit-230309",
#         "DX-DCN-CJ": None,
#         "DX-G": "centos-7.6-64bit-230309",
#         "DX-G-YS": "centos-7.6-64bit-230309"
#       },
#       "centos-7.2-64bit" : {
#         "DX-M1": "centos-7.2-64bit-230309",
#         "DX-Central": "centos-7.2-64bit-230309",
#         "DX-DCN-CJ": None,
#         "DX-G": "centos-7.2-64bit-230309",
#         "DX-G-YS": "centos-7.2-64bit-230309"
#       }
# }

# # VM 생성 가능한 표준 OS 목록
# os_list = [
#     "ubuntu-24.04-64bit",
#     "ubuntu-22.04-64bit",
#     "ubuntu-20.04-64bit",
#     "ubuntu-18.04-64bit",
#     "rhel-9.4-64bit",
#     "rhel-8.10-64bit",
#     "rhel-8.8-64bit",
#     "rhel-8.4-64bit",
#     "rhel-8.3-64bit",
#     "rocky-9.4-64bit",
#     "rocky-9.2-64bit",
#     "rocky-8.10-64bit",
#     "rocky-8.9-64bit",
#     "rocky-8.8-64bit",
#     "win2022std-64bit",
#     "win2019std-64bit",
#     "win2016std-64bit",
#     "centos-7.9-64bit",
#     "centos-7.8-64bit",
#     "centos-7.6-64bit",
#     "centos-7.2-64bit"
# ]

#################################################################
# request Body 형식
#################################################################

# make_token_body
# user_id, user_pw
make_token_body = """ 
    {
      "auth": {
        "identity": {
          "methods": [
            "password"
          ],
          "password": {
            "user": {
              "domain": {
                "id": "default"
              },
              "name": "{user_id}",
              "password": "{user_pw}"
            }
          }
        },
        "scope": {
          "project": {
            "domain": {
              "id": "default"
            },
            "name": "{user_id}"
          }
        }
      }
    }
"""
# create_vm_body
# vm_name, key_name, zone_name, subnet_id, flavor_id, image_id, vol_size, vol_type, userdata
create_vm_body = """
    {
      "server": {
        "name": "{vm_name}",
        "key_name": "{key_name}",
        "flavorRef": "{flavor_id}",
        "availability_zone": "{zone_name}",
        "networks": [
          {
            "uuid": "{subnet_id}"
          }
        ],
        "block_device_mapping_v2": [
          {
            "destination_type": "volume",
            "boot_index": "0",
            "source_type": "image",
            "volume_size": "{vol_size}",
            "uuid": "{image_id}",
            "volume_type": "{vol_type}"
          }
        ],
        "user_data" : "{userdata}"
      }
    }
"""

# delete_vm_forced_body
delete_vm_forced_body = """
    {
      "forceDelete": null
    }
"""

# start_vm_body
start_vm_body = """
    {
      "unshelve": null
    }
"""

# stop_vm_body
stop_vm_body = """
    {
      "shelve": null
    }
"""

# change_vm_body
# flavor_id
change_vm_body = """
    {
      "resize": {
        "flavorRef": "{flavor_id}"
      }
    }
"""

# set_portforward_body
# privateip, publicip_id, private_port, public_port, protocol
# set_portforward_body = """
#     {
#       "vmguestip": "{privateip}",
#       "entpublicipid": "{publicip_id}",
#       "privateport": "{private_port}",
#       "publicport": "{public_port}",
#       "protocol": "{protocol}"
#     }
# """

set_portforward_body = """
    {
      "mappedIp": "{privateip}",
      "publicIpId": "{publicip_id}",
      "startPrivatePort": "{private_port}",
      "endPrivatePort": "{private_port}",
      "startPublicPort": "{public_port}",
      "endPublicPort": "{public_port}",
      "protocol": "{protocol}"
    }
"""

# set_staticnat_body
# privateip, subnet_id, publicip_id
# set_staticnat_body = """
#     {
#       "vmguestip": "{privateip}",
#       "vmnetworkid": "{subnet_id}",
#       "entpublicipid": "{publicip_id}"
#     }
# """

set_staticnat_body = """
    {
      "mappedIp": "{privateip}",
      "publicIpId": "{publicip_id}"
    }
"""

# create_subnet_body
# subnet_name, zone_name, cidr_range, start_ip, end_ip, lb_start_ip, lb_end_ip, bm_start_ip, bm_end_ip, gateway_ip
# iSCSI용 ip대역도 필요한지 확인 필요
# create_subnet_body = """
#     {
#       "name": "{subnet_name}",
#       "zone": "{zone_name}",
#       "type": "tier",
#       "usercustom": "y",
#       "detail": {
#         "cidr": "{cidr_range}",
#         "startip": "{start_ip}",
#         "endip": "{end_ip}",
#         "lbstartip": "{lb_start_ip}",
#         "lbendip": "{lb_end_ip}",
#         "bmstartip": "{bm_start_ip}",
#         "bmendip": "{bm_end_ip}",
#         "gateway": "{gateway_ip}"
#       }
#     }
# """

create_subnet_body = """
    {
      "name": "{subnet_name}",
      "type": "tier",
      "isCustom": true,
      "detail": {
        "cidr": "{cidr_range}",
        "startIp": "{start_ip}",
        "endIp": "{end_ip}",
        "lbStartIp": "{lb_start_ip}",
        "lbEndIp": "{lb_end_ip}",
        "bmStartIp": "{bm_start_ip}",
        "bmEndIp": "{bm_end_ip}",
        "iscsiStartIp": "{iscsi_start_ip}",
        "iscsiEndIp": "{iscsi_end_ip}",
        "gatewayIp": "{gateway_ip}"
      }
    }
"""

# create_volume_body
# zone_name, vol_size, vol_name
create_volume_body = """
    {
      "volume": {
        "availability_zone": "{zone_name}",
        "size": "{vol_size}",
        "usage_plan_type": "hourly",
        "name": "{vol_name}",
        "bootable": false,
        "volume_type" : "{vol_type}"
      }
    }
"""

# attach_volume_body
# volume_id
attach_volume_body = """
    {
      "volumeAttachment": {
        "volumeId": "{volume_id}",
        "device": "/dev/vdb"
      }
    }
"""

# create_image_body
# image_name
create_image_body = """
    {
      "os-volume_upload_image": {
        "force": true,
        "image_name": "{image_name}",
        "container_format": "bare",
        "disk_format": "qcow2"
      }
    }
"""

# create_snapshot_body
# snapshot_name, volume_id, description
create_snapshot_body = """
    {
      "snapshot": {
        "name": "{snapshot_name}",
        "volume_id": "{volume_id}",
        "force": true,
        "description": "{description}"
      }
    }
"""

# create_keypair_body
# key_name
create_keypair_body = """
    {
      "keypair": {
        "name": "key_name"
      }
    }
"""

# create_nas_body
# share_network_id,nas_name,nas_size,zone_name, vol_type
create_nas_body = """
    {
      "share": {
        "share_proto": "nfs",
        "share_network_id": "{nas_network_id}",
        "name": "{nas_name}",
        "is_public": false,
        "size": "{nas_size}",
        "availability_zone": "{zone_name}",
        "share_type": "{vol_type}"
      }
    }
"""

# change_nas_size_body
# nas_size
change_nas_size_body = """
    {
      "os-extend": {
        "new_size": "{nas_size}"
      }
    }
"""

# create_nas_network_body
# subnet_id, nams_name
create_nas_network_body = """
    {
      "share_network": {
        "neutron_net_id": "{subnet_id}",
        "name": "{nas_name}"
      }
    }
"""

# set_nas_access_body
# access_level, access_cidr
set_nas_access_body = """
    {
      "os-allow_access": {
        "access_level": "{access_level}",
        "access_type": "ip",
        "access_to": "{access_cidr}"
      }
    }
"""

# get_nas_access_info_body
get_nas_access_info_body = """
    {
      "os-access_list": null
    }
"""

# unset_nas_access_body
# access_id
unset_nas_access_body = """
    {
      "os-deny_access": {
        "access_id": "{access_id}"
      }
    }
"""

# set_firewall_net2net_body
# src_net_id, src_cidr, dst_net_id, dest_cidr, protocol, start_port, end_port, action
# set_firewall_net2net_body = """
#     {
#       "protocol": "{protocol}",
#       "srcip": "{src_cidr}",
#       "action": "{action}",
#       "srcnetworkid": "{src_net_id}",
#       "dstip": "{dst_cidr}",
#       "dstnetworkid": "{dst_net_id}"
#     }
# """

set_firewall_net2net_body = """
    {
      "srcNat" : "{srcnat}",
      "protocol": "{protocol}",
      "srcAddress": [ "{src_cidr}" ],
      "action": "{action}",
      "srcNetwork": [ "{src_net_id}" ],
      "dstAddress": [ "{dst_cidr}" ],
      "dstNetwork": [ "{dst_net_id}" ]
    }
"""

# set_firewall_virtualid_body
# src_net_id, src_cidr, dst_net_id, dest_cidr, protocol, start_port, end_port, action
# set_firewall_virtualid_body = """
#     {
#       "protocol": "{protocol}",
#       "srcip": "{src_cidr}",
#       "action": "{action}",
#       "srcnetworkid": "{src_net_id}",
#       "virtualipid": "{virtualip_id}",
#       "dstnetworkid": "{dst_net_id}"
#     }
# """

set_firewall_staticnat_body = """
    {
      "srcNat" : "false",
      "protocol": "{protocol}",
      "srcAddress": "{src_cidr}",
      "srcNetwork": [ "{src_net_id}" ],
      "staticNatId": "{staticnat_id}",
      "action" : "true"
    }
"""

set_firewall_portforward_body = """
    {
      "srcNat" : "false",
      "srcAddress": "{src_cidr}",
      "srcNetwork": [ "{src_net_id}" ],
      "portForwardingId": "{portforward_id}",
      "action" : "true"
    }
"""

request_body_dict = {
    "make_token": make_token_body,
    "create_vm": create_vm_body,
    "delete_vm_forced": delete_vm_forced_body,
    "start_vm": start_vm_body,
    "stop_vm": stop_vm_body,
    "change_vm": change_vm_body,
    "set_portforward": set_portforward_body,
    "set_staticnat": set_staticnat_body,
    "set_firewall_net2net": set_firewall_net2net_body,
    "set_firewall_staticnat": set_firewall_staticnat_body,
    "set_firewall_portforward": set_firewall_portforward_body,
    "create_subnet": create_subnet_body,
    "create_volume": create_volume_body,
    "attach_volume": attach_volume_body,
    "create_image": create_image_body,
    "create_snapshot": create_snapshot_body,
    "create_keypair": create_keypair_body,
    "create_nas": create_nas_body,
    "change_nas_size": change_nas_size_body,
    "create_nas_network": create_nas_network_body,
    "set_nas_access": set_nas_access_body,
    "get_nas_access_info": get_nas_access_info_body,
    "unset_nas_access": unset_nas_access_body,
}


#################################################################
# request url 형식
#################################################################

# make_token_url : zone
make_token_url = "https://api.ucloudbiz.olleh.com/{zone}/identity/auth/tokens"

# create_vm_url : zone
create_vm_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers"

# get_vm_info_url : vm_id, zone
get_vm_info_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}"

# list_vm_info_url : zone
list_vm_info_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/detail"

# delete_vm_url : vm_id, zone
delete_vm_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}"

# delete_vm_forced_url : vm_id, zone
delete_vm_forced_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/action"
)

# list_flavor_info_url : zone
list_flavor_info_url = "https://api.ucloudbiz.olleh.com/{zone}/server/flavors/detail"

# start_vm_url : vm_id, zone
start_vm_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/action"

# stop_vm_url : vm_id, zone
stop_vm_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/action"

# change_vm_url : vm_id, zone
change_vm_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/action"

# create_publicip_url : zone
create_publicip_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/publicIp"

# list_publicip_info_url : zone
list_publicip_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/publicIp"

# delete_ip_url : publicip_id, zone
delete_publicip_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/publicIp/{publicip_id}"
)

# set_portforward_url : zone
set_portforward_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/portforwarding"

# list_portforward_info_url : zone
list_portforward_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/portforwarding"
)

# unset_portforward_url : portforward_id, zone
unset_portforward_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/portforwarding/{portforward_id}"
)

# set_staticnat_url : zone
set_staticnat_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/staticNat"

# list_staticnat_info_url : zone
list_staticnat_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/staticNat"

# unset_staticnat_url : staticnat_id, zone
unset_staticnat_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/staticNat/{staticnat_id}"
)

# set_firewall_url : zone
set_firewall_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/firewall/policy"

# list_firewall_info_url : zone
list_firewall_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/firewall/policy"

# unset_firewall_url : firewall_id, zone
unset_firewall_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/firewall/policy/{firewall_id}"
)

# get_vpc_info_url : zone
get_vpc_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/vpc"

# get_net_job_status_url : job_id, zone
get_net_job_status_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/job/status/{job_id}"
)

# create_subnet_url : zone
create_subnet_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/network"

# list_subnet_info_url : zone
list_subnet_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/network"

# delete_subnet_url : subnet_id, zone
delete_subnet_url = "https://api.ucloudbiz.olleh.com/{zone}/nsm/v1/network/{network_id}"

# create_volume_url : project_id, zone
create_volume_url = "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/volumes"

# get_volume_info_url : project_id, volume_id, zone
get_volume_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/volumes/{volume_id}"
)

# list_volume_info_url : project_id, zone
list_volume_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/volumes/detail"
)

# delete_volume_url : project_id, volume_id, zone
delete_volume_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/volumes/{volume_id}"
)

# attach_volume_url : vm_id, zone
attach_volume_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/os-volume_attachments"

# get_attached_volume_url : vm_id, zone
get_attached_volume_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/os-volume_attachments"

# detach_volume_url : vm_id, volume_id, zone
detach_volume_url = "https://api.ucloudbiz.olleh.com/{zone}/server/servers/{vm_id}/os-volume_attachments/{volume_id}"

# create_image_url : project_id, volume_id, zone
create_image_url = "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/volumes/{volume_id}/action"

# get_image_info_url : image_id, zone
get_image_info_url = "https://api.ucloudbiz.olleh.com/{zone}/image/images/{image_id}"

# list_image_info_url : zone
list_image_info_url = "https://api.ucloudbiz.olleh.com/{zone}/image/images"

# delete_image_url : image_id, zone
delete_image_url = "https://api.ucloudbiz.olleh.com/{zone}/image/images/{image_id}"

# create_snapshot_url : project_id, zone
create_snapshot_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/snapshots"
)

# get_snapshot_info_url : project_id, snapshot_id, zone
get_snapshot_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/snapshots/{snapshot_id}"
)

# list_snapshot_info_url : project_id, zone
list_snapshot_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/snapshots/detail"
)

# delete_snapshot_url : project_id, snapshot_id, zone
delete_snapshot_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/volume/{project_id}/snapshots/{snapshot_id}"
)

# create_keypair_url : zone
create_keypair_url = "https://api.ucloudbiz.olleh.com/{zone}/server/os-keypairs"

# list_keyapir_url : zone
list_keypair_url = "https://api.ucloudbiz.olleh.com/{zone}/server/os-keypairs"

# delete_keypair_url : key_name, zone
delete_keypair_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/server/os-keypairs/{key_name}"
)

# create_lb_url : zone, request_parameters
create_lb_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=createLoadBalancer{request_parameters}&response=json"

# get_lb_usage_url : zone, request_parameters
get_lb_usage_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=usageLoadBalancerService{request_parameters}&response=json"

# list_lb_info_url : zone, request_parameters
list_lb_info_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=listLoadBalancers{request_parameters}&response=json"

# update_lb_url : zone, request_parameters
update_lb_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=updateLoadBalancer{request_parameters}&response=json"

# check_lb_name_url : zone, request_parameters
check_lb_name_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=checkLoadBalancerName{request_parameters}&response=json"

# delete_lb_url : zone, request_parameters
delete_lb_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=deleteLoadBalancer{request_parameters}&response=json"

# add_lb_server_url : zone, request_parameters
add_lb_server_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=addLoadBalancerWebServer{request_parameters}&response=json"

# list_lb_server_url : zone, request_parameters
list_lb_server_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=listLoadBalancerWebServers{request_parameters}&response=json"

# remove_lb_server_url : zone, request_parameters
remove_lb_server_url = "https://api.ucloudbiz.olleh.com/{zone}/loadbalancer/client/api?command=removeLoadBalancerWebServer{request_parameters}&response=json"

# create_nas_url : zone, project_id
create_nas_url = "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares"

# get_nas_info_url : zone, project_id, share_id
get_nas_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}"
)

# list_nas_info_url : zone, project_id
list_nas_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/detail"
)

# delete_nas_url : zone, project_id, share_id
delete_nas_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}"
)

# change_nas_size_url : zone, project_id, share_id
change_nas_size_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}/action"
)

# create_nas_network_url : zone, project_id
create_nas_network_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/share-networks"
)

# get_nas_network_info_url : zone, project_id, share_network_id
get_nas_network_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/share-networks/{share_network_id}"

# list_nas_network_info_url : zone, project_id
list_nas_network_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/share-networks/detail"
)

# delete_nas_network_url : zone, project_id, share_network_id
delete_nas_network_url = "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/share-networks/{share_network_id}"

# set_nas_access_url : zone, project_id, share_id
set_nas_access_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}/action"
)

# get_nas_access_url : zone, project_id, share_id
get_nas_access_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}/action"
)

# unset_nas_access_url : zone, project_id, share_id
unset_nas_access_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/nas/{project_id}/shares/{share_id}/action"
)

# get_vpc_info_url : zone
get_vpc_info_url = "https://api.ucloudbiz.olleh.com/{zone}/nc/VPC"

# get_metric_info_url : zone
get_metric_info_url = "https://api.ucloudbiz.olleh.com/{zone}/watch/v3/metrics"

# list_metric_info_url : zone
list_metric_info_url = (
    "https://api.ucloudbiz.olleh.com/{zone}/watch/v3/metrics/metadata"
)

request_url_dict = {
    "make_token": make_token_url,
    "create_vm": create_vm_url,
    "get_vm_info": get_vm_info_url,
    "list_vm_info": list_vm_info_url,
    "delete_vm": delete_vm_url,
    "delete_vm_forced": delete_vm_forced_url,
    "list_flavor_info": list_flavor_info_url,
    "start_vm": start_vm_url,
    "stop_vm": stop_vm_url,
    "change_vm": change_vm_url,
    "create_publicip": create_publicip_url,
    "list_publicip_info": list_publicip_info_url,
    "delete_publicip": delete_publicip_url,
    "set_portforward": set_portforward_url,
    "list_portforward_info": list_portforward_info_url,
    "unset_portforward": unset_portforward_url,
    "set_staticnat": set_staticnat_url,
    "list_staticnat_info": list_staticnat_info_url,
    "unset_staticnat": unset_staticnat_url,
    "set_firewall": set_firewall_url,
    "list_firewall_info": list_firewall_info_url,
    "unset_firewall": unset_firewall_url,
    "get_vpc_info": get_vpc_info_url,
    "get_net_job_status": get_net_job_status_url,
    "create_subnet": create_subnet_url,
    "list_subnet_info": list_subnet_info_url,
    "delete_subnet": delete_subnet_url,
    "create_volume": create_volume_url,
    "get_volume_info": get_volume_info_url,
    "list_volume_info": list_volume_info_url,
    "delete_volume": delete_volume_url,
    "attach_volume": attach_volume_url,
    "get_attached_volume": get_attached_volume_url,
    "detach_volume": detach_volume_url,
    "create_image": create_image_url,
    "get_image_info": get_image_info_url,
    "list_image_info": list_image_info_url,
    "delete_image": delete_image_url,
    "create_snapshot": create_snapshot_url,
    "get_snapshot_info": get_snapshot_info_url,
    "list_snapshot_info": list_snapshot_info_url,
    "delete_snapshot": delete_snapshot_url,
    "create_keypair": create_keypair_url,
    "list_keypair": list_keypair_url,
    "delete_keypair": delete_keypair_url,
    "create_lb": create_lb_url,
    "get_lb_usage": get_lb_usage_url,
    "list_lb_info": list_lb_info_url,
    "update_lb": update_lb_url,
    "check_lb_name": check_lb_name_url,
    "delete_lb": delete_lb_url,
    "add_lb_server": add_lb_server_url,
    "list_lb_server": list_lb_server_url,
    "remove_lb_server": remove_lb_server_url,
    "create_nas": create_nas_url,
    "get_nas_info": get_nas_info_url,
    "list_nas_info": list_nas_info_url,
    "delete_nas": delete_nas_url,
    "change_nas_size": change_nas_size_url,
    "create_nas_network": create_nas_network_url,
    "get_nas_network_info": get_nas_network_info_url,
    "list_nas_network_info": list_nas_network_info_url,
    "delete_nas_network": delete_nas_network_url,
    "set_nas_access": set_nas_access_url,
    "get_nas_access_info": get_nas_access_info_url,
    "unset_nas_access": unset_nas_access_url,
    "get_vpc_info": get_vpc_info_url,
    "get_metric_info": get_metric_info_url,
    "list_metric_info": list_metric_info_url,
}

#################################################################
# object storage 관련 path 형식
#################################################################

# list_box_path
list_box_path = "/"

# create_box_path : box_name
create_box_path = "/{box_name}"

# delete_box_path : box_name
delete_box_path = "/{box_name}"

# upload_box_file_path : box_name, key_name
upload_box_file_path = "/{box_name}/{key_name}"

# list_box_file_path : box_name
list_box_file_path = "/{box_name}"

# delete_box_file_path : box_name, key_name
delete_box_file_path = "/{box_name}/{key_name}"

# download_box_file_path : box_name, key_name
download_box_file_path = "/{box_name}/{key_name}"

# create_multipart_upload_path : box_name, key_name
create_multipart_upload_path = "/{box_name}/{key_name}?uploads"

# list_multipart_upload_info_path : box_name,
list_multipart_upload_info_path = "/{box_name}?uploads"

# upload_part_path : box_name, key_name, number, upload_id
upload_part_path = "/{box_name}/{key_name}?partNumber={number}&uploadId={upload_id}"

# complete_multipart_upload_path : box_name, key_name, upload_id
complete_multipart_upload_path = "/{box_name}/{key_name}?uploadId={upload_id}"

object_storage_url = "https://ss1.cloud.kt.com:1000"

object_path_dict = {
    "list_box": list_box_path,
    "create_box": create_box_path,
    "delete_box": delete_box_path,
    "upload_box_file": upload_box_file_path,
    "list_box_file": list_box_file_path,
    "delete_box_file": delete_box_file_path,
    "download_box_file": download_box_file_path,
    "create_multipart_upload": create_multipart_upload_path,
    "list_multipart_upload_info": list_multipart_upload_info_path,
    "upload_part": upload_part_path,
    "complete_multipart_upload": complete_multipart_upload_path,
}

#################################################################
# low level functions
#################################################################


# openapi command에 따른 url return
def get_request_url(command, **kwargs):
    url = request_url_dict[command]
    return url.format(**kwargs)


# openapi command에 따른 LB url return
def get_lb_request_url(command, zone, **kwargs):
    url = request_url_dict[command]

    # value가 None인 항목 삭제
    for key in list(kwargs.keys()):
        if kwargs[key] is None:
            del kwargs[key]

    arg_dict = {}

    params = urlencode(kwargs)
    if len(params) > 0:
        params = "&" + params
    arg_dict["zone"] = zone
    arg_dict["request_parameters"] = params

    return url.format(**arg_dict)


# object storage API 호출을 위한 path
def get_object_path(command, **kwargs):
    path = object_path_dict[command]
    return path.format(**kwargs)


# object storage를 위한 request url
def get_object_url(path):
    return object_storage_url + path


# openapi command에 따른 html body return
def get_request_body(command, **kwargs):
    body_txt = request_body_dict[command]
    body_json = json.loads(body_txt)
    body_yaml = yaml.dump(
        body_json, default_flow_style=False, sort_keys=False
    )  # dict --> yaml 문자열
    formatted_body_yaml = body_yaml.format(**kwargs)
    formatted_body_json = yaml.safe_load(formatted_body_yaml)
    return formatted_body_json


# text를 base64로 인코딩
def encode_to_base64(input_string):
    # 문자열을 바이트로 인코딩
    input_bytes = input_string.encode("utf-8")
    # Base64 인코딩
    base64_bytes = base64.b64encode(input_bytes)
    # Base64 바이트를 문자열로 디코딩
    base64_string = base64_bytes.decode("utf-8")

    return base64_string


# get_vm_info() response 정보 파싱
"""
{
  "vm_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
  "status" : "ACTIVE",
  "key_name" : "key123",
  "vm_name" : "vm1",
  "flavor_name" : "1x1.itl",
  "zone_name" : "DX-M1",
  "host_id" : "9616ef4c43ba1b8f2d5afaa8e9cee1eb647bae27c274992c7fe47238",
  "volume_ids" : [ 
    "volume_id1", 
    "volume_id2" 
  ]
  "subnets" : [
    {
      "subnet_name" : "DMZ",
      "privateip" : "10.0.0.6"
    }
  ]
}
"""


def parse_get_vm_info(res):
    info = {}

    # status : BUILD(생성중), ACTIVE, SHUTOFF(정지), RESIZE(flavor변경)
    info["vm_id"] = res["id"]
    info["status"] = res["status"]
    info["key_name"] = res["key_name"]
    info["vm_name"] = res["name"]
    info["flavor_name"] = res["flavor"]["original_name"]
    info["zone_name"] = res["OS-EXT-AZ:availability_zone"]
    info["host_id"] = res["hostId"]

    vol_list = []
    subnets_list = []
    for item in res["os-extended-volumes:volumes_attached"]:
        vol_list.append(item["id"])

    info["volume_ids"] = vol_list

    if info["status"] == "BUILD":
        info["subnets"] = []
    else:
        subnets = res["addresses"]
        subnets_key = list(subnets.keys())
        index = 0

        for key in subnets_key:
            item = {}
            item["subnet_name"] = key
            item["privateip"] = subnets[key][index]["addr"]
            subnets_list.append(item)
        info["subnets"] = subnets_list

    return info


# list_vm_info response 정보 파싱
"""
[
    {vm info1},
    {vm info2}
]
"""


def parse_list_vm_info(res):
    info_list = []

    for item in res["servers"]:
        info = parse_get_vm_info(item)
        info_list.append(info)

    return info_list


# list_flavor() response 정보 파싱
"""
[
    {
      "flavor_name" : "flavor1",
      "flavor_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
      "cpu" : "1",
      "memory" : "16384",
    }
]
"""


def parse_flavor_info(res):
    flavor_list = []

    for item in res["flavors"]:
        flavor = {}
        flavor["flavor_name"] = item["name"]
        flavor["flavor_id"] = item["id"]
        flavor["cpu"] = item["vcpus"]
        flavor["memory"] = item["ram"]
        flavor_list.append(flavor)

    return flavor_list


# list_subnet() response 정보 파싱
"""
[
    {
      "subnet_name" : "DMZ",
      "subnet_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
      "subnet_network_id" : "775a0948-3834-455d-9dca-56dbfe3b1799"
      "cidr" : "10.0.0.0/24",
      "startip" : "10.0.0.6",
      "endip" : "10.0.0.100",
      "lb_startip" : "10.0.0.101",
      "lb_endip" : "10.0.0.110",
      "bm_startip" : "10.0.0.111",
      "bm_endip" : "10.0.0.120",
      "iscsi_startip" : "10.0.0.121",
      "iscsi_endip" : "10.0.0.130",
      "gateway" : "10.0.0.1"
    }
]
"""


def parse_list_subnet(res):
    subnet_list = []

    for item in res["data"]:
        subnet = {}
        subnet["subnet_name"] = item["refName"]
        subnet["subnet_id"] = item["refId"]
        subnet["subnet_network_id"] = item["networkId"]
        subnet["cidr"] = item["cidr"]
        subnet["startip"] = item["startIp"]
        subnet["endip"] = item["endIp"]
        subnet["bm_startip"] = item["bmStartIp"]
        subnet["bm_endip"] = item["bmEndIp"]
        subnet["lb_startip"] = item["lbStartIp"]
        subnet["lb_endip"] = item["lbEndIp"]
        subnet["iscsi_startip"] = item["iscsiStartIp"]
        subnet["iscsi_endip"] = item["iscsiEndIp"]
        subnet["gateway"] = item["gatewayIp"]
        subnet_list.append(subnet)

    return subnet_list


# def parse_create_subnet(res):
#     return res["nc_createosnetworkresponse"]["network_id"]

# get_volume_info() response 파싱
"""
{
  "status" : "available",
  "volume_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
  "size" : "10",
  "volume_name" : "my_vol1",
  "snapshot_id" : "06ef8bfe-4c24-48f5-9390-46355c30f57e",
  "bootable" : False,
  "zone_name" : "DX-M1",
  "vm_id" : "",
  "device" : "",
  "volume_type" : "HDD"
}
"""


def parse_get_volume_info(res):
    info = {}

    # status : creating(생성중), available(사용가능), in-use(서버에 연결)
    info["status"] = res["status"]
    info["volume_id"] = res["id"]
    info["size"] = res["size"]
    info["volume_name"] = res["name"]
    info["snapshot_id"] = res["snapshot_id"]
    info["bootable"] = res["bootable"]
    info["zone_name"] = res["availability_zone"]
    info["volume_type"] = res["volume_type"]
    info["vm_id"] = ""
    info["device"] = ""

    if info["status"] == "in-use":
        info["vm_id"] = res["attachments"][0]["server_id"]
        info["device"] = res["attachments"][0]["device"]

    return info


# list_volume_info() response 정보 파싱
"""
[
    {
      "status" : "available",
      "volume_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
      "size" : "10",
      "volume_name" : "my_vol1",
      "snapshot_id" : "06ef8bfe-4c24-48f5-9390-46355c30f57e",
      "bootable" : False,
      "zone_name" : "DX-M1",
      "vm_id" : ""
      "device" : ""
    }
]
"""


def parse_list_volume_info(res):
    info_list = []

    for item in res["volumes"]:
        info = parse_get_volume_info(item)
        info_list.append(info)

    return info_list


# get_attached_volume() response 정보 파싱
"""
[
    "volume_id1",
    "volume_id2"
]
"""


def parse_attached_volume(res):
    info_list = []

    for item in res["volumeAttachments"]:
        info_list.append(item["volumeId"])

    return info_list


# 서버가 설정한 상태가 될 때까지 대기함.
# 모두 dest_state에 도달하면 SUCCESS
# vm 1대라도 에러가 발생하면 ERROR
# dest state에 도달하지 못했으면 BUILDING
def wait_vm_state(instance_ids, vm_list, dest_state):
    result = "SUCCESS"

    if dest_state == "vm_active":
        state = "ACTIVE"
        interval = VM_ACTIVE_INTERVAL
    elif dest_state == "vm_shutoff":
        state = "SHUTOFF"
        interval = VM_SHUTOFF_INTERVAL

    for item in vm_list:
        if item["vm_id"] in instance_ids:
            # vm list에서 한개라도 ERROR가 발생하면 ERROR 리턴
            if item["status"] == "ERROR":
                result = "ERROR"
                break
            if item["status"] != state:
                result = "BUILDING"
                break

    if result == "BUILDING":
        time.sleep(interval)

    return result


# Volume이 설정한 상태가 될 때까지 대기함.
def wait_volume_state(instance_ids, volume_list, dest_state):
    result = True

    if dest_state == "volume_available":
        state = "available"
        interval = VOLUME_AVAILABLE_INTERVAL
    elif dest_state == "volume_inuse":
        state = "in-use"
        interval = VOLUME_INUSE_INTERVAL
    elif dest_state == "nas_available":
        state = "available"
        interval = NAS_AVAILABLE_INTERVAL

    if dest_state == "nas_available":
        for item in volume_list:
            if item["nas_id"] in instance_ids:
                if item["status"] != state:
                    result = False
                    break
    else:
        for item in volume_list:
            if item["volume_id"] in instance_ids:
                if item["status"] != state:
                    result = False
                    break

    if result == False:
        time.sleep(interval)

    return result


def parse_net_job_status(job_type, res, zone_mgr):
    info = {}
    # info["success"] = False
    info["job_status"] = "RUNNING"

    # res["data"]에 뭔가 추가로 정보가 올 거 같은데,
    # return은 id값이 가야하는데...

    # print(json.dumps(res, indent=2))

    if res["httpStatus"] == 200:
        if res["jobStatus"] == "SUCCESS":
            info["job_status"] = "SUCCESS"

            if job_type == "create_subnet":
                info["subnet_network_id"] = res["data"]["networkId"]
            elif job_type == "set_firewall":
                info["acl_id"] = res["data"]["policyId"]

        elif res["jobStatus"] == "RUNNING":
            info["job_status"] = "RUNNING"

        elif res["jobStatus"] == "FAIL":
            info["job_status"] = "FAIL"
    else:
        info["job_status"] = "FAIL"

    return info


# list_publicip_info() 함수의 response 파싱
"""
[
    {
        "publicip_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
        "zone_name" : "DX-M1",
        "publicip" : "147.6.44.44",
        "type" : "STATICNAT"
    }
]
"""


def parse_list_publicip_info(res):
    publicip_list = []

    for item in res["data"]:
        publicip = {}
        publicip["publicip_id"] = item["publicIpId"]
        publicip["zone_name"] = item["portalZoneId"]
        publicip["publicip"] = item["publicIp"]
        publicip["type"] = item["type"]

        publicip_list.append(publicip)

    return publicip_list


# list_staticnat_info() 함수의 response 파싱
"""
[
    {
      "privateip": "172.25.0.11",
      "publicip": "211.62.99.34",
      "name": "SN_211.62.99.34",
      "staticnat_id" : "06ef8bfe-4c24-48f5-9390-46355c30f57e",
      "publicip_id" : "565a0948-3834-455d-9dca-56dbfe3b1745"
    }
]
"""


def parse_list_staticnat_info(res):
    nat_list = []

    for item in res["data"]:
        nat = {}
        nat["privateip"] = item["mappedIp"]
        nat["publicip"] = item["publicIp"]
        nat["name"] = item["name"]
        nat["staticnat_id"] = item["staticNatId"]
        # nat["subnet_id"] = item["networkid"]  # 변경된 API에 없어 삭제
        nat["publicip_id"] = item["publicIpId"]

        nat_list.append(nat)

    return nat_list


def _parse_acl_network(nets, map_dict):
    net_list = []

    for item in nets:
        net = {}
        net["name"] = item["name"]
        net["network_id"] = item["networkId"]

        if net["network_id"] == None:
            net["subnet_id"] = None
        else:
            net["subnet_id"] = map_dict[net["network_id"]]

        net_list.append(net)

    return net_list


# list_firewall_info() 함수의 response 파싱
"""
[
    {
      "src_nets": [
        {
          "name": "connecthub_mvp06-M-Chub_Sub",
          "network_id": "6d30753d-655b-421f-907a-9c495d64a4c6",
          "subnet_id" : "68e60a77-0828-43de-828a-cb2362f6ef14"
        }
      ],
      "dst_nets": [
        {
          "name": "mvp06-private_Sub",
          "network_id": "68e60a77-0828-43de-828a-cb2362f6ef14",
          "subnet_id" : "6d30753d-655b-421f-907a-9c495d64a4c6"
        }
      ],
      "src_addrs": [
        {
          "name": "172.26.210.0/24"
        }
      ],
      "dst_addrs": [
        {
          "name": "172.25.110.0/24"
        }
      ],
      "services": [
        {
          "protocol": "TCP",
          "startPort": "1001",
          "endPort": "1005"
        }
      ],
      "action": "allow",
      "acl_id": "a8e365f0-66a0-45d9-91dc-a487b2c7b8f2",
      "priority" : 1,
      "comments": "central \uc5f0\ub3d9"
    }
]
"""


def parse_list_firewall_info(res, network):
    acl_list = []
    map_dict = network._get_subnet_id_map_dict()

    for item in res["data"]:
        acl = {}
        acl["src_nets"] = _parse_acl_network(item["srcInterface"], map_dict)
        acl["dst_nets"] = _parse_acl_network(item["dstInterface"], map_dict)
        acl["src_addrs"] = item["srcAddress"]
        acl["dst_addrs"] = item["dstAddress"]
        acl["services"] = item["services"]
        acl["action"] = "allow" if item["action"] == "accept" else "deny"
        acl["acl_id"] = item["policyId"]
        acl["comments"] = item["comment"]
        acl["priority"] = item["priority"]
        acl_list.append(acl)

    return acl_list


def parse_multi_cidr(cidr_list):
    cidr_str = ""

    for index, cidr in enumerate(cidr_list):
        if index == 0:
            cidr_str = cidr["name"]
        else:
            cidr_str += ",\n" + cidr["name"]

    # 여러개의 cidr인 경우 따옴표 추가
    if len(cidr_list) > 1:
        cidr_str = '"' + cidr_str + '"'

    return cidr_str


# 특정 key를 맨 앞으로 보내는 코드
def move_key_to_front(d: dict, key: str) -> dict:
    if key not in d:
        return d  # 키가 없으면 원래 dict 반환

    return {key: d[key], **{k: v for k, v in d.items() if k != key}}


# CSV 파일 저장을 위한 형식으로 변환
# 하나의 필드에 여러개를 입력하는 경우를 고려하면 list형식에 맞추어 여러 값을 작성하는 형태로 변환 필요
def parse_firewall_info_to_csv(acl_list):
    data_list = []

    for acl in acl_list:
        data = {}
        data["src_net"] = acl["src_nets"][0]["name"]
        data["src_cidr"] = parse_multi_cidr(acl["src_addrs"])
        data["dst_net"] = acl["dst_nets"][0]["name"]
        data["dst_cidr"] = parse_multi_cidr(acl["dst_addrs"])

        services = acl["services"][0]
        data["start_port"] = services["startPort"] if "startPort" in services else ""
        data["end_port"] = services["endPort"] if "endPort" in services else ""
        data["protocol"] = services["protocol"] if "protocol" in services else ""

        data["action"] = acl["action"]

        if data["src_net"].endswith("_Sub"):
            data["src_net"] = data["src_net"].removesuffix("_Sub")
        if data["dst_net"].endswith("_Sub"):
            data["dst_net"] = data["dst_net"].removesuffix("_Sub")

        if data["dst_cidr"].startswith("PF_"):
            data["type"] = "port_forward"
        elif data["dst_cidr"].startswith("SN_"):
            data["type"] = "static_nat"
        else:
            data["type"] = "net2net"

        new_data = move_key_to_front(data, "type")

        data_list.append(new_data)

    return data_list


def _parse_snapshot_info(item):
    info = {}
    info["snapshot_id"] = item["id"]
    info["snapshot_name"] = item["name"]
    info["description"] = item["description"]
    info["volume_id"] = item["volume_id"]
    info["size"] = item["size"]
    info["progress"] = item["os-extended-snapshot-attributes:progress"]

    return info


# list_snapshot_info()의 response 파싱
"""
[
    {
      "snapshot_id": "ed0379d8-775e-4d2a-a1cc-f2a79cf3dbcd",
      "snapshot_name": "test-vol",
      "description": "Daily backup",
      "volume_id": "615c81cb-1c58-4293-9937-e449db2c96cd",
      "size": 50,
      "progress": "100%"
    }
]
"""


def parse_list_snapshot_info(res):
    info_list = []

    for item in res["snapshots"]:
        info = _parse_snapshot_info(item)
        info_list.append(info)

    return info_list


# snapshot 정보 조회
def parse_get_snapshot_info(res):
    return _parse_snapshot_info(res["snapshot"])


def _parse_image_info(item):
    info = {}
    info["image_id"] = item["id"]
    info["image_name"] = item["name"]
    info["size"] = item["size"]
    info["status"] = item["status"]
    info["min_disk"] = item["min_disk"]

    return info


# list_image_info()의 response 파싱
"""
[
    {
      "image_id": "c25c7a76-3773-47de-8676-c332dea79a90",
      "image_name": "yeongtestvm1image",
      "size": 6124047360,
      "status": "active"
      "min_disk : 50
    }
]
"""


def parse_list_image_info(res):
    info_list = []

    for item in res["images"]:
        info = _parse_image_info(item)
        info_list.append(info)

    return info_list


# get_image_info() 함수의 response 파싱
def parse_get_image_info(res):
    return _parse_image_info(res)


# list_portforward_info() 함수의 response 파싱
"""
[
    {
      "portforward_id": "06ef8bfe-4c24-48f5-9390-46355c30f57e",
      "privateip": "172.25.100.101",
      "publicip": "210.178.40.86",
      "protocol": "TCP",
      "private_port": "15433",
      "private_end_port": "15433",
      "public_port": "15431",
      "public_end_port": "15431",
      "publicip_id" : "565a0948-3834-455d-9dca-56dbfe3b1745",
      "name": "PF_210.178.40.86_15431_TCP"
    }
]
"""


def parse_list_portforward_info(res):
    info_list = []

    for item in res["data"]:
        info = {}
        info["portforward_id"] = item["portForwardingId"]
        info["privateip"] = item["mappedIp"]
        info["publicip"] = item["publicIp"]
        info["protocol"] = item["protocol"]
        info["private_port"] = item["startPrivatePort"]
        info["private_end_port"] = item["endPrivatePort"]
        info["public_port"] = item["startPublicPort"]
        info["public_end_port"] = item["endPublicPort"]
        # info["subnet_id"] = item["networkid"]  # 새로운 format에 없음
        info["publicip_id"] = item["publicIpId"]  # 추가함
        info["name"] = item["name"]

        info_list.append(info)

    return info_list


# 소문자 영문자와 숫자로만 구성된 랜덤 문자열 생성
def generate_random_string(length=6):
    characters = string.ascii_lowercase + string.digits  # 소문자 영문자 + 숫자
    return "".join(random.choices(characters, k=length))


# IP주소가 cidr범주내에 있는지 확인
def is_in_cidr(ip: str, cidr: str) -> bool:
    """
    IP 주소가 CIDR 범위에 포함되는지 확인.

    :param ip: 확인할 IP 주소 (예: "192.168.1.5")
    :param cidr: CIDR 범위 (예: "192.168.1.0/24")
    :return: IP가 CIDR 범위에 포함되면 True, 그렇지 않으면 False
    """
    try:
        ip_obj = ipaddress.ip_address(ip)  # IP 객체 생성
        network_obj = ipaddress.ip_network(cidr, strict=False)  # 네트워크 객체 생성
        return ip_obj in network_obj
    except ValueError as e:
        print(f"Invalid IP or CIDR: {e}")
        return False


# IP Address 형식이 맞는지 확인
def is_ip_address(ip_addr):
    try:
        ip = ipaddress.IPv4Address(ip_addr)  # IP를 IPv4 형식으로 변환
    except ValueError as e:
        return False

    return True


# ip주소가 start_ip와 end_ip사이에 있는지 확인
def is_ip_in_range(ip_addr, start_ip, end_ip):
    try:
        ip = ipaddress.IPv4Address(ip_addr)  # IP를 IPv4 형식으로 변환
    except ValueError as e:
        return False

    start = ipaddress.IPv4Address(start_ip)
    end = ipaddress.IPv4Address(end_ip)
    return start <= ip <= end  # 범위 비교


# NAS volume 정보 조회
"""
    {
      "volume_type": "HDD",
      "nas_network_id": "f7f87b59-817d-4f7f-b9b2-7425a70c8e2a",
      "export_locations": [
        "172.25.0.52:/share_7b0a87c5_65c8_46bb_84b6_7f3774fa4d16",
        "172.25.0.36:/share_7b0a87c5_65c8_46bb_84b6_7f3774fa4d16"
      ],
      "nas_size": 500,
      "nas_used" : 100,
      "nas_name": "yeongnas1",
      "nas_id": "7b7a7d21-c526-40e4-8d52-8fc8e971841e",
      "status": "available",
      "share_proto": "NFS"
    }
"""


def parse_get_nas_info(item):
    info = {}
    info["volume_type"] = item["volume_type"]
    info["nas_network_id"] = item["share_network_id"]
    info["export_locations"] = item["export_locations"]
    info["nas_size"] = item["size"]
    info["nas_used"] = item["used"]
    info["nas_name"] = item["name"]
    info["nas_id"] = item["id"]
    info["status"] = item["status"]
    info["share_proto"] = item["share_proto"]

    return info


# parse_list_nas_info() parsing
"""
[
    {
      "volume_type": "HDD",
      "nas_network_id": "375e97b4-854b-49aa-be94-2d997b311cc5",
      "export_locations": [
        "172.25.160.162:/share_197b1517_171a_4c6c_a006_a7d5a33f0f90",
        "172.25.160.70:/share_197b1517_171a_4c6c_a006_a7d5a33f0f90"
      ],
      "nas_size": 500,
      "nas_name": "cwpp-nas-01",
      "nas_id": "0e7384ed-a096-4529-b14f-b35339a5869e",
      "status": "available",
      "share_proto": "NFS"
    }
]
"""


def parse_list_nas_info(res):
    info_list = []

    for item in res["shares"]:
        info = parse_get_nas_info(item)
        info_list.append(info)

    return info_list


# NAS network 정보 조회
"""
{
  "nas_network_id": "08c22608-a49a-4762-b6d5-0eaa51fe435e",
  "nas_network_name": "mvp06-private",
  "subnet_id": "04c90b7f-11e4-4041-a981-d7aff1a83713",
  "cidr": "172.25.110.0/24"
}
"""


def parse_get_nas_network_info(item):
    info = {}
    info["nas_network_id"] = item["id"]
    info["nas_network_name"] = item["name"]
    info["subnet_id"] = item["neutron_net_id"]
    info["cidr"] = item["cidr"]

    return info


# NAS network 목록 정보 조회
"""
[
    {
      "nas_network_id": "08c22608-a49a-4762-b6d5-0eaa51fe435e",
      "nas_network_name": "mvp06-private",
      "subnet_id": "04c90b7f-11e4-4041-a981-d7aff1a83713",
      "cidr": "172.25.110.0/24"
    }
]
"""


def parse_list_nas_network_info(res):
    info_list = []

    for item in res["share_networks"]:
        info = parse_get_nas_network_info(item)
        info_list.append(info)

    return info_list


# CIDR 형식이 유효한지 확인
def is_valid_cidr(cidr):
    try:
        # CIDR 유효성 확인
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


# NAS 접근 권한 및 네트워크 정보 조회
"""
[
    {
      "access_id": "bd5c311f-3e63-4d63-9854-6dcee4c7c4d5",
      "access_level": "rw",
      "access_cidr": "10.0.0.0/24"
    }
]
"""


def parse_get_nas_access_info(res):
    info_list = []

    for item in res["access_list"]:
        info = {}
        info["access_id"] = item["id"]
        info["access_level"] = item["access_level"]
        info["access_cidr"] = item["access_to"]
        info_list.append(info)

    return info_list


# 원하는 양식으로 현재 시간 가져오기
def get_current_time():
    # 현재 UTC 시간 가져오기
    current_time = datetime.utcnow()

    # 원하는 형식으로 변환
    formatted_time = current_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

    return formatted_time


# object storage request url 생성 및 인증정보 생성에 활용
def get_auth_field(method, c_type, path):
    time_str = get_current_time()
    auth_field = f"{method}\n\n{c_type}\n{time_str}\n{path}"

    return auth_field, time_str


# object storage 인증정보 생성
def generate_signature(secret_key, message):
    # Secret Key와 메시지를 UTF-8로 인코딩
    key_bytes = secret_key.encode("utf-8")
    message_bytes = message.encode("utf-8")

    # HMAC-SHA1 생성
    hmac_obj = hmac.new(key_bytes, message_bytes, hashlib.sha1)

    # HMAC 결과를 Base64로 인코딩
    signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")

    return signature


# object storage 연결을 위한 헤더정보 생성
def get_auth_header(access_key, secret_key, method, c_type, path):
    message, time_str = get_auth_field(method, c_type, path)
    sig = generate_signature(secret_key, message)

    field = f"AWS {access_key}:{sig}"

    headers = {}
    headers["Date"] = time_str
    headers["Authorization"] = field
    if c_type:
        headers["Content-Type"] = c_type

    return headers


# box 목록 정보 조회
"""
[
    "Demo2-MySQL-Backup",
    "MYSQL-DB-0-f2127d12-747e-4bd7-8180-b23c90e78169",
    "MYSQL-DB-0-f7d7c991-6ce1-4a87-819f-e1cd780f43f6",
    "demo2-obj-lwk01",
    "mvp02-velero"
]
"""


def parse_list_filebox(res):
    res_dict = xmltodict.parse(res)
    info_list = []

    contents = res_dict["ListAllMyBucketsResult"]["Buckets"]["Bucket"]

    # 항목이 1개이면 그냥 주고, 2개 이상이면 list로 주기 때문에 분리하여 parsing
    if isinstance(contents, list):
        for item in contents:
            info_list.append(item["Name"])
    else:
        info_list.append(contents["Name"])

    return info_list


# box에 속한 file 목록 정보 조회
"""
[
    {
      "key_name": "japan/mov.mp4",
      "file_size": "2726551385"
    },
    {
      "key_name": "ktcloud.pdf",
      "file_size": "7685969"
    }
]
"""


def parse_list_box_file(res):
    res_dict = xmltodict.parse(res)
    info_list = []

    # 목록이 비어있는 경우
    if "Contents" not in res_dict["ListBucketResult"]:
        return []

    contents = res_dict["ListBucketResult"]["Contents"]

    # 항목이 1개이면 그냥 주고, 2개 이상이면 list로 주기 때문에 분리하여 parsing
    if isinstance(contents, list):
        for item in contents:
            info = {}
            info["key_name"] = item["Key"]
            info["file_size"] = item["Size"]
            info_list.append(info)
    else:
        info = {}
        info["key_name"] = contents["Key"]
        info["file_size"] = contents["Size"]
        info_list.append(info)

    return info_list


# multipart upload 작업 생성을 위한 parsing
def parse_create_multipart_upload(res):
    res_dict = xmltodict.parse(res)
    return res_dict["InitiateMultipartUploadResult"]["UploadId"]


# multipart upload 작업 목록 조회
def parse_list_multipart_upload_info(res):
    res_dict = xmltodict.parse(res)
    info_list = []

    for item in res_dict["ListMultipartUploadsResult"]["Upload"]:
        info = {}
        info["key_name"] = item["Key"]
        info["upload_id"] = item["UploadId"]
        info_list.append(info)

    return info_list


# dict 형식을 xml 형식으로 변환
def dict_to_custom_xml(data):
    # Create the root element
    root_name = list(data.keys())[0]
    root = ET.Element(root_name)

    # Iterate over the list of parts
    for item in data[root_name]:
        part_data = item["Part"]
        part_elem = ET.SubElement(root, "Part")

        for key, value in part_data.items():
            child = ET.SubElement(part_elem, key)
            child.text = str(value)

    # Return pretty printed XML as a string
    return ET.tostring(root, encoding="unicode", method="xml")


# multipart upload 진행에 따른 partnumber 및 etag 목록 정보
"""
parts =
{
    "CompleteMultipartUpload" : [
        {
            "Part" : {
                "PartNumber" : 1,
                "ETag" : "299381bf38920f86d4db6c93c580ded6"
            }
        },
        {
            "Part" : {
                "PartNumber" : 2,
                "ETag" : "a23dcb17a244d25fa4de47d11705d0a3"
            } 
        }
    ]
    
}
"""


def get_body_multipart_upload(parts):
    xml_parts = dict_to_custom_xml(parts)
    return xml_parts


# LB 목록 정보 조회
"""
[
    {
      "healthcheck_type": "tcp",
      "healthcheck_url": "",
      "service_port": "80",
      "service_ip": "172.25.0.181",
      "service_type": "HTTP",
      "lb_option": "SOURCEIPHASH",
      "lb_id": 45486,
      "established_conn": 0,
      "lb_name": "yeonglb1",
      "ciphergroup_name": "",
      "subnet_id": "80e48e72-441e-4fd1-b991-c17b13ff60bd",
      "state": "DOWN"
    }
]
"""


def parse_list_lb_info(res):
    info_list = []

    for item in res["listloadbalancersresponse"]["loadbalancer"]:
        info = {}
        if item["healthchecktype"] == "tcp":
            info["healthcheck_url"] = ""
        else:
            info["healthcheck_url"] = item["healthcheckurl"]

        info["healthcheck_type"] = item["healthchecktype"]
        info["service_port"] = item["serviceport"]
        info["service_ip"] = item["serviceip"]
        info["service_type"] = item["servicetype"]
        info["lb_option"] = item["loadbalanceroption"]
        info["lb_id"] = item["loadbalancerid"]
        info["established_conn"] = item["establishedconn"]
        info["lb_name"] = item["name"]
        info["ciphergroup_name"] = item["ciphergroupname"]
        info["subnet_id"] = item["networkid"]
        info["state"] = item["state"]
        info_list.append(info)

    return info_list


# LB ciphergroup의 validation check
def check_ciphergroup_validation(ciphergroup):
    if ciphergroup not in ciphergroup_list:
        example = ", ".join(ciphergroup_list)
        raise Exception(
            f"""'{ciphergroup}' : mis-typed ciphergroup name!, options : {example}"""
        )


# LB option의 validation check
def check_lb_option_validation(lb_option):
    if lb_option not in lb_options_list:
        example = ", ".join(lb_options_list)
        raise Exception(
            f"""'{lb_option}' : mis-typed loadbalancer option!, options : {example}"""
        )


# LB healthcheck type의 validation check
def check_healthcheck_type_validation(healthcheck_type, healthcheck_url):
    if healthcheck_type not in healthcheck_type_list:
        example = ", ".join(healthcheck_type_list)
        raise Exception(
            f"""'{healthcheck_type}' : mis-typed healthechck type!, options : {example}"""
        )

    if healthcheck_type == "http" or healthcheck_type == "https":
        if healthcheck_url == None:
            raise Exception(
                f"""'{healthcheck_type}' healthcheck type needs healthcheck url!"""
            )


# LB생성과 관련된 parameter의 유효성 검증
def check_parameter_validation(
    lb_option,
    service_type,
    healthcheck_type,
    healthcheck_url,
    ciphergroup_name,
    tlsv1,
    tlsv11,
    tlsv12,
):
    if service_type not in service_type_list:
        example = ", ".join(healthcheck_type_list)
        raise Exception(
            f"""'{service_type}' : mis-typed serivce type!, options : {example}"""
        )

    if service_type == "https":
        if ciphergroup_name == None:
            example = ", ".join(ciphergroup_list)
            raise Exception(
                f"""'{service_type}' service type needs ciphergroup name!, options : {example}"""
            )
        if tlsv1 not in tls_options_list:
            raise Exception(
                f"""'{service_type}' service type needs tlsv1 option(ENABLED/DISABLED)!"""
            )
        if tlsv11 not in tls_options_list:
            raise Exception(
                f"""'{service_type}' service type needs tlsv11 option(ENABLED/DISABLED)!"""
            )
        if tlsv12 not in tls_options_list:
            raise Exception(
                f"""'{service_type}' service type needs tlsv12 option(ENABLED/DISABLED)!"""
            )
        check_ciphergroup_validation(ciphergroup_name)

    check_healthcheck_type_validation(healthcheck_type, healthcheck_url)
    check_lb_option_validation(lb_option)


# LB가 부하분산할 서버의 목록 정보
"""
[
    {
        "vm_ip": "172.25.0.178",
        "lb_id": 45486,
        "vm_id": "f3e70d5b-af92-425b-8d0f-309a3f68c15f",
        "vm_port": "80",
        "state": "DOWN",
        "service_id": 269321,
        "cursrvrconnections": 15,
        "throughputrate ": 10,
        "avgsvrttfb": 10,
        "requestsrate": 10
    }
]      
"""


def parse_list_lb_server(res):
    info_list = []

    for item in res["listloadbalancerwebserversresponse"]["loadbalancerwebserver"]:
        info = {}
        info["vm_ip"] = item["ipaddress"]
        info["lb_id"] = item["loadbalancerid"]
        info["vm_id"] = item["virtualmachineid"]
        info["vm_port"] = item["publicport"]
        info["state"] = item["state"]
        info["service_id"] = item["serviceid"]
        info["cursrvrconnections"] = item["cursrvrconnections"]
        info["throughputrate"] = item["throughputrate"]
        info["avgsvrttfb"] = item["avgsvrttfb"]
        info["requestsrate"] = item["requestsrate"]
        info_list.append(info)

    return info_list


"""
[
      {
        "name": "testlb",
        "outbound": 0,
        "inbound": 0,
        "date": "2015-01-01"
      },
      {
        "name": "testlb",
        "outbound": 0,
        "inbound": 0,
        "date": "2015-01-02"
      }
]
"""


def parse_get_lb_usage(res):
    return res["usageloadbalancerserviceresponse"]["lists"]


# firewall protocol의 validation check
def validate_firewall_protocol(protocol):
    if protocol not in firewall_protocol:
        example = ", ".join(firewall_protocol)
        raise Exception(
            f"protocol '{protocol}' : doest not support, optiton : {example}"
        )


# firewall action의 validation check
def validate_firewall_action(action):
    if action not in firewall_action:
        example = ", ".join(firewall_action)
        raise Exception(f"action '{action}' : dose not support, option : {example}")


# voluem type의 validation check
def validate_volume_type(vol_type):
    if vol_type not in volume_types:
        example = ", ".join(volume_types)
        raise Exception(
            f"volume type '{vol_type}' : dose not support, option : {example}"
        )


# os name의 validation check
# def validate_os_name(os_name):
#     if os_name not in os_list:
#         example = ', '.join(os_list)
#         raise Exception(f"os name '{os_name}' : dose not support, option : {example}")

# os name이 os_list에 있는지 확인
# def check_os_name(os_name):
# return os_name in os_list


# zone name의 validation check
def validate_zone_name(zone_name):
    if zone_name not in zone_list:
        example = ", ".join(zone_list)
        raise Exception(
            f"zone name '{zone_name}' : dose not support, option : {example}"
        )


def validate_disk_source_type(source_type):
    if source_type not in disk_source_type_list:
        example = ", ".join(disk_source_type_list)
        raise Exception(
            f"disk_source_type '{source_type}' : dose not support, option : {example}"
        )


# dict 타입을 key=value 형태의 문자열로 구성
def dict_to_string(data):
    return ", ".join(f"{key}={value}" for key, value in data.items())


# open api 호출 및 log 저장
def request_api(
    func_name, cmd, url, headers, zone_mgr, params=None, body=None, **kwargs
):
    kwargs = kwargs.copy()
    if cmd == "post":
        response = requests.post(url, headers=headers, params=params, json=body)
    elif cmd == "get":
        response = requests.get(url, headers=headers, params=params, json=body)
    elif cmd == "delete":
        response = requests.delete(url, headers=headers, params=params, json=body)

    code = response.status_code
    kwargs["code"] = code
    if code >= 200 and code < 210:
        # 성공 log
        log_str = dict_to_string(kwargs)
        message = f"{func_name}() : success, {log_str}"
        zone_mgr.info_log(message)
    else:
        # 실패 log
        res = response.text
        if len(res) == 0:
            log_str = dict_to_string(kwargs)
            message = f"{func_name}() : fail, {log_str}"
            zone_mgr.error_log(message)
        else:
            res = response.json()
            kwargs["res"] = res
            log_str = dict_to_string(kwargs)
            message = f"{func_name}() : fail, {log_str}"
            zone_mgr.error_log(message)

    return response


# LB관련 open api 호출 및 log 저장
def request_lb_api(
    func_name, cmd, url, headers, zone_mgr, res_key, body=None, **kwargs
):
    kwargs = kwargs.copy()
    if cmd == "post":
        response = requests.post(url, headers=headers, json=body)
    elif cmd == "get":
        response = requests.get(url, headers=headers, json=body)
    elif cmd == "delete":
        response = requests.delete(url, headers=headers, json=body)

    code = response.status_code
    success = False
    kwargs["code"] = code
    if code >= 200 and code < 210:
        res = response.json()
        info = res[res_key]
        if "success" in info:
            if info["success"] == True:
                # 성공
                log_str = dict_to_string(kwargs)
                message = f"{func_name}(): success, {log_str}"
                zone_mgr.info_log(message)
                success = True
            else:
                # 실패
                kwargs["res"] = res
                log_str = dict_to_string(kwargs)
                message = f"{func_name}(): fail, {log_str}"
                zone_mgr.error_log(message)
        else:
            # 성공
            log_str = dict_to_string(kwargs)
            message = f"{func_name}(): success, {log_str}"
            zone_mgr.info_log(message)
            success = True
    else:
        # 실패 log
        res = response.text
        if len(res) == 0:
            log_str = dict_to_string(kwargs)
            message = f"{func_name}() : fail, {log_str}"
            zone_mgr.error_log(message)
        else:
            res = response.json()
            kwargs["res"] = res
            log_str = dict_to_string(kwargs)
            message = f"{func_name}() : fail, {log_str}"
            zone_mgr.error_log(message)

    return response, success


# job_id를 기반으로 비동기 처리 API request
def request_net_api(func_name, cmd, url, headers, zone_mgr, body=None, **kwargs):
    kwargs = kwargs.copy()
    if cmd == "post":
        response = requests.post(url, headers=headers, json=body)
    elif cmd == "get":
        response = requests.get(url, headers=headers, json=body)
    elif cmd == "delete":
        response = requests.delete(url, headers=headers, json=body)

    res = response.json()

    if res["httpStatus"] == 202 or res["httpStatus"] == 201:
        log_str = dict_to_string(kwargs)
        message = f"{func_name}(): success, {log_str}"
        zone_mgr.info_log(message)
        return res["jobId"]
    else:
        kwargs["res"] = res
        log_str = dict_to_string(kwargs)
        message = f"{func_name}(): fail, {log_str}"
        zone_mgr.error_log(message)
        return None


# VM생성 시 추가 disk 구성을 위한 body 생성
"""
disks = [
    {
      "source_type" : "snapshot",
      "vol_size" : 50,
      "vol_type" : "HDD",
      "snapshot_id" : "ed0379d8-775e-4d2a-a1cc-f2a79cf3dbcd"
    },
    {
      "source_type" : "blank",
      "vol_size" : 50,
      "vol_type" : "HDD",
    }
  ]
"""


def create_vm_add_disk_body(body, disks):
    for disk in disks:
        item = {}
        item["destination_type"] = "volume"
        item["volume_size"] = disk["vol_size"]
        item["volume_type"] = disk["vol_type"]
        item["source_type"] = disk["source_type"]
        if disk["source_type"] == "snapshot":
            item["uuid"] = disk["snapshot_id"]
        body["server"]["block_device_mapping_v2"].append(item)
    return body


# VM 생성시에 fixed ip를 사용하는 경우 해당 필드 추가
def create_vm_fixed_ip(body, fixed_ip):
    body["server"]["networks"][0]["fixed_ip"] = fixed_ip
    return body


# def get_image_name(os_name, zone_name):
#     try:
#         validate_os_name(os_name)
#     except Exception as e:
#         return None

#     validate_zone_name(zone_name)
#     return image_list_dict[os_name][zone_name]


# dict타입의 value에서 문자열의 앞뒤에 " 또는 ' 가 함께 있으면 제거
def remove_quotes_from_dict_values(data):
    def remove_quotes(value):
        # 문자열인 경우에만 처리
        if isinstance(value, str):
            return re.sub(r"^(['\"])(.*)\1$", r"\2", value)
        return value

    # dict 내 모든 값에 대해 따옴표 제거
    return {key: remove_quotes(value) for key, value in data.items()}


def set_firewall_add_port_body(body, start_port, end_port):
    if start_port == None:
        start_port = end_port
    if end_port == None:
        end_port = start_port

    body["startPort"] = start_port
    body["endPort"] = end_port

    return body


"""
[
  {
    "name" : "yeong-test-vm1",
    "key" : "yeong-kp01",
    "flavor" : "1x1.itl",
    "subnet" : "DMZ",
    "image" : "ubuntu-20.04-64bit",
    "root_vol_type" : "SSD",
    "fixed_ip" : "172.25.0.99", # optional
    "userdata" : "", # optional
    "disks" : [     # optional
      {
        "source_type" : "snapshot",
        "vol_size" : 10,
        "vol_type" : "HDD",
        "snapshot_name" : "yeong-vol-snap"
      }
    ]
  }
]
"""


def change_vm_shape(vm):
    result = True
    msg = ""

    new_vm = {}
    new_vm["res_name"] = vm["res_name"]
    new_vm["name"] = vm["name"]
    new_vm["key"] = vm["key"]
    new_vm["flavor"] = vm["flavor"]
    new_vm["subnet"] = vm["subnet"]
    new_vm["image"] = vm["image"]
    new_vm["root_vol_type"] = vm["root_vol_type"]

    if vm["fixed_ip"] != "":
        new_vm["fixed_ip"] = vm["fixed_ip"]

    if vm["userdata"] != "":
        new_vm["userdata"] = vm["userdata"]

    if vm["num_disks"] != "" and vm["num_disks"] != "0":
        disks = []
        num_disks = int(vm["num_disks"])

        for i in range(num_disks):
            disk = {}
            disk_name = f"disk{i+1}"
            disk_source_type = disk_name + "_source_type"
            disk_vol_size = disk_name + "_vol_size"
            disk_vol_type = disk_name + "_vol_type"

            if disk_source_type in vm:
                disk["source_type"] = vm[disk_source_type]
            else:
                result = False
                msg = f"""'{vm["name"]}' vm 설정에서 '{disk_source_type}'필드가 존재하지 않습니다."""
                break

            if disk_vol_size in vm:
                disk["vol_size"] = vm[disk_vol_size]
            else:
                result = False
                msg = f"""'{vm["name"]}' vm 설정에서 '{disk_vol_size}'필드가 존재하지 않습니다."""
                break

            if disk_vol_type in vm:
                disk["vol_type"] = vm[disk_vol_type]
            else:
                result = False
                msg = f"""'{vm["name"]}' vm 설정에서 '{disk_vol_type}'필드가 존재하지 않습니다."""
                break

            if vm[disk_source_type] == "snapshot":
                disk_snapshot_name = disk_name + "_snapshot_name"
                if disk_snapshot_name in vm:
                    disk["snapshot_name"] = vm[disk_snapshot_name]
                else:
                    result = False
                    msg = f"""'{vm["name"]}' vm 설정에서 '{disk_snapshot_name}'필드가 존재하지 않습니다."""
                    break

            disks.append(disk)

        new_vm["disks"] = disks

    return new_vm, result, msg


# csv파일로 읽어온 vm_list 형식을 변형
def change_vm_list_shape(vm_list, key):
    result = True
    msg_list = []
    new_vm_list = []

    for vm in vm_list:
        if len(vm["res_name"]) != 0:
            if not validate_string2(vm["res_name"]):
                result = False
                msg = f"""'{vm["res_name"]}'은 잘못된 res_name입니다. 영문자, 숫자, '-', '_'로 구성되며, 첫글자는 영문자여야 합니다."""
                append_msg_list(msg_list, key, msg)

        if vm["name"] != "":
            new_vm, result_tmp, msg = change_vm_shape(vm)
            if result_tmp == False:
                result = False
                append_msg_list(msg_list, key, msg)
            new_vm_list.append(new_vm)

    return new_vm_list, result, msg_list


def validate_string(s: str) -> bool:
    # 영문자, 숫자, '-'로만 구성 + 첫 문자는 영문자 확인
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]*", s))


def validate_string2(s: str) -> bool:
    # 영문자, 숫자, '-'로만 구성 + 첫 문자는 영문자 확인
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-_]*", s))


# dict list에서 특정 key에 해당 value가 존재하는지 확인
def check_exist_in_dict_list(target_key, target_value, data_list):
    return any(d.get(target_key) == target_value for d in data_list)


def get_value_in_dict_list(cmp_key, cmp_value, ret_key, data_list):
    for item in data_list:
        if item[cmp_key] == cmp_value:
            return item[ret_key]
    return None


def get_list_in_dict_list(cmp_key, cmp_value, ret_key, data_list):
    ret_list = []
    for item in data_list:
        if item[cmp_key] == cmp_value:
            ret_list.append(item[ret_key])

    return ret_list


def get_value_in_dict_list_two_key(
    cmp_key1, cmp_value1, cmp_key2, cmp_value2, ret_key, data_list
):
    for item in data_list:
        if item[cmp_key1] == cmp_value1:
            if item[cmp_key2] == cmp_value2:
                return item[ret_key]
    return None


# 중복되는 문자열 검사
def find_duplicates_str(str_list):
    counts = Counter(str_list)
    duplicates = [item for item, count in counts.items() if count > 1]
    return duplicates


# 중복되는 dict내 value 검사
def find_duplicates(key, dict_list):
    string_list = []
    for item in dict_list:
        if key in item:
            string_list.append(item[key])

    return find_duplicates_str(string_list)


# 중복되는 key dict내 value 검사
def find_duplicates_key_dict(key, key_dict_list):
    string_list = []
    for item in key_dict_list:
        if key in item["params"]:
            string_list.append(item["params"][key])

    return find_duplicates_str(string_list)


def validate_fixed_ip(ip_addr, old_vm_list):
    for vm in old_vm_list:
        if ip_addr == vm["subnets"][0]["privateip"]:
            return False
    return True


def find_duplicates_server_list(lb_list):
    server_list = []

    for lb in lb_list:
        if "server_list" in lb:
            server_list = server_list + lb["server_list"]

    return find_duplicates_str(server_list)


def validate_change_vm_list(key_vm_list, flavor_list, old_vm_list):
    result = True
    msg_list = []

    if len(key_vm_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_vm in key_vm_list:
        vm = key_vm["params"]
        key = key_vm["key"]

        if "name" not in vm:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        result_tmp, msg_tmp = check_key_list(vm, ["name", "flavor"])
        if result_tmp == False:
            msg = f"""'{vm["name"]}'에서 {msg_tmp}"""
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if not check_exist_in_dict_list("vm_name", vm["name"], old_vm_list):
            msg = f"""'{vm["name"]}'은 기존에 생성된 VM이 아닙니다."""
            append_msg_list(msg_list, key, msg)
            result = False

        if not check_exist_in_dict_list("flavor_name", vm["flavor"], flavor_list):
            result = False
            msg = (
                f"""'{vm["name"]}'에서 '{vm["flavor"]}'논 존재하지 않는 flavor입니다."""
            )
            append_msg_list(msg_list, key, msg)

    vm_list = []
    for key_vm in key_vm_list:
        vm_list.append(key_vm["params"])

    # VM name 중복 확인
    duplicates = find_duplicates("name", vm_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""'{str}' VM 이름이 중복됩니다."""
        append_msg_list(msg_list, "syntax_error", msg)
        result = False

    return result, msg_list


def validate_change_lb_list(key_lb_list, old_lb_list, vm_list):
    result = True
    msg_list = []

    if len(key_lb_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_lb in key_lb_list:
        lb = key_lb["params"]
        key = key_lb["key"]

        if "name" not in lb:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        result_tmp, msg_tmp = check_key_list(lb, ["option", "healthcheck_type"])
        if result_tmp == False:
            msg = f"""'{lb["name"]}'에서 {msg_tmp}"""
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if not check_exist_in_dict_list("lb_name", lb["name"], old_lb_list):
            msg = f"""'{lb["name"]}'은 기존에 생성된 LB가 아닙니다."""
            append_msg_list(msg_list, key, msg)
            result = False

        if "server_list" in lb:
            if not "server_port" in lb:
                result = False
                msg = f"""'{lb["name"]}'에서 'server_list"가 존재하는 경우, 'server_port"는 필수 항목입니다."""
                append_msg_list(msg_list, key, msg)
            else:
                lb["server_port"] = str_to_int(lb["server_port"])

            # 연결 서버의 유효성 검증 및 정보 조회
            vm_name_list = lb["server_list"]

            for vm_name in vm_name_list:
                if vm_name.startswith("@res"):
                    continue
                if not check_exist_in_dict_list("vm_name", vm_name, vm_list):
                    result = False
                    msg = f"""'{lb["name"]}'에서 '{lb["server_list"]}'에 존재하지 않는 vm name이 있습니다."""
                    append_msg_list(msg_list, key, msg)

        try:
            lb_option = None if "option" not in lb else lb["option"]
            healthcheck_type = (
                None if "healthcheck_type" not in lb else lb["healthcheck_type"]
            )
            healthcheck_url = (
                None if "healthcheck_url" not in lb else lb["healthcheck_url"]
            )

            check_healthcheck_type_validation(healthcheck_type, healthcheck_url)
            check_lb_option_validation(lb_option)
        except Exception as e:
            result = False
            msg = f"""'{lb["name"]}' 파라메타 에러 : {e}"""
            append_msg_list(msg_list, key, msg)

    lb_list = []
    for key_lb in key_lb_list:
        lb_list.append(key_lb["params"])

    # LB name 중복 확인
    duplicates = find_duplicates("name", lb_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""'{str}' LB 이름이 중복됩니다."""
        append_msg_list(msg_list, "syntax_error", msg)
        result = False

    return result, msg_list


# vm_list의 유효성 검사
# key_vm_list 형식
"""
    {
        "key" : xxx,
        "type" : "vm",
        "params" : {}
    }
"""


def validate_vm_list(
    key_vm_list,
    flavor_list,
    subnet_list,
    image_list,
    snapshot_list,
    old_vm_list,
    zone_name,
    action,
):
    result = True
    msg_list = []

    if len(key_vm_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_vm in key_vm_list:
        vm = key_vm["params"]
        key = key_vm["key"]

        # 상태 정보 추가
        key_vm["state"] = "none"

        if "name" not in vm:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        result_tmp, msg_tmp = check_key_list(
            vm, ["name", "key", "flavor", "subnet", "image", "root_vol_type"]
        )
        if result_tmp == False:
            msg = f"""'{vm["name"]}'에서 {msg_tmp}"""
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if check_exist_in_dict_list("vm_name", vm["name"], old_vm_list):
            msg = f"""'{vm["name"]}'은 기존 생성된 VM 이름과 중복됩니다."""
            append_msg_list(msg_list, key, msg)
            key_vm["state"] = "created"
            if action == "all":
                result = False

        if not validate_string(vm["name"]):
            result = False
            msg = f"""'{vm["name"]}'은 잘못된 name입니다. 영문자, 숫자, '-'로 구성되며, 첫글자는 영문자여야 합니다."""
            append_msg_list(msg_list, key, msg)

        if not validate_string(vm["key"]):
            result = False
            msg = f"""'{vm["name"]}'에서 '{vm["key"]}'은 잘못된 key name입니다. 영문자, 숫자, '-'로 구성되며, 첫글자는 영문자여야 합니다."""
            append_msg_list(msg_list, key, msg)

        if not check_exist_in_dict_list("flavor_name", vm["flavor"], flavor_list):
            result = False
            msg = (
                f"""'{vm["name"]}'에서 '{vm["flavor"]}'논 존재하지 않는 flavor입니다."""
            )
            append_msg_list(msg_list, key, msg)

        if not check_exist_in_dict_list("subnet_name", vm["subnet"], subnet_list):
            result = False
            msg = f"""'{vm["name"]}'에서 '{vm["subnet"]}'논 존재하지 않는 Subnet 입니다."""
            append_msg_list(msg_list, key, msg)

        image_name = get_image_name(vm["image"], zone_name)
        if image_name == None:
            image_name = vm["image"]

        if not check_exist_in_dict_list("image_name", image_name, image_list):
            result = False
            msg = (
                f"""'{vm["name"]}'에서 '{vm["image"]}'논 존재하지 않는 Image 입니다."""
            )
            append_msg_list(msg_list, key, msg)

        try:
            validate_volume_type(vm["root_vol_type"])
        except Exception as e:
            result = False
            msg = f"""'{vm["name"]}'에서 '{vm["root_vol_type"]}'논 잘못된 root_vol_type 유형입니다. 'HDD' 또는 'SSD'를 기재하세요."""
            append_msg_list(msg_list, key, msg)

        if "fixed_ip" in vm:
            ip_addr = vm["fixed_ip"]
            dicts = [d for d in subnet_list if d.get("subnet_name") == vm["subnet"]]
            start_ip = dicts[0]["startip"]
            end_ip = dicts[0]["endip"]

            # ip주소 범주에 속하는지 확인
            if not is_ip_in_range(ip_addr, start_ip, end_ip):
                result = False
                msg = f"""'{vm["name"]}'에서 '{vm["fixed_ip"]}' fixed_ip는 잘못 기재되었거나 '{vm["subnet"]}'의 {start_ip}와 {end_ip}사이에 존재하지 않습니다."""
                append_msg_list(msg_list, key, msg)

            # 기존 VM ip주소와 중복 확인
            if not validate_fixed_ip(ip_addr, old_vm_list):
                result = False
                msg = f"""'{vm["name"]}'에서 '{vm["fixed_ip"]}' fixed_ip가 기존 VM IP와 중복됩니다."""
                append_msg_list(msg_list, key, msg)

        if "disks" in vm:
            for disk in vm["disks"]:
                if "source_type" in disk:
                    if disk["source_type"] == "blank":
                        result_tmp, msg_tmp = check_key_list(
                            disk, ["vol_type", "vol_size"]
                        )
                    else:
                        result_tmp, msg_tmp = check_key_list(
                            disk, ["vol_type", "vol_size", "snapshot_name"]
                        )
                    if result_tmp == False:
                        msg = f"""'{vm["name"]}'에서 {msg_tmp}"""
                        append_msg_list(msg_list, key, msg)
                        return False, msg_list
                else:
                    msg = f"""'{vm["name"]}'에서 disks 정의 시 'volume_type'은 필수 항목입니다."""
                    append_msg_list(msg_list, key, msg)
                    return False, msg_list

                try:
                    validate_disk_source_type(disk["source_type"])
                except Exception as e:
                    result = False
                    msg = f"""'{vm["name"]}'에서 '{disk["source_type"]}'논 존재하지 않는 disk_source_type 입니다. "blank" 또는 "snapshot"을 기재하세요."""
                    append_msg_list(msg_list, key, msg)

                disk_vol_size = str_to_int(disk["vol_size"])
                disk["vol_size"] = disk_vol_size
                if disk_vol_size < 10 or disk_vol_size > 2000:
                    result = False
                    msg = f"""'{vm["name"]}'에서 disk volume size는 10GB 이상, 2TB 이하로 설정해야 합니다."""
                    append_msg_list(msg_list, key, msg)

                try:
                    validate_volume_type(disk["vol_type"])
                except Exception as e:
                    result = False
                    msg = f"""'{vm["name"]}'에서 '{disk["vol_type"]}'논 잘못된 volume_type 유형입니다. "HDD" 또는 "SSD"를 기재하세요."""
                    append_msg_list(msg_list, key, msg)

                if disk["source_type"] == "snapshot":
                    if not check_exist_in_dict_list(
                        "snapshot_name", disk["snapshot_name"], snapshot_list
                    ):
                        result = False
                        msg = f"""'{vm["name"]}'에서 '{disk["snapshot_name"]}'논 존재하지 않는 snapshot name 입니다."""
                        append_msg_list(msg_list, key, msg)
                    else:
                        vol_size = get_value_in_dict_list(
                            "snapshot_name",
                            disk["snapshot_name"],
                            "size",
                            snapshot_list,
                        )
                        if str_to_int(disk["vol_size"]) != str_to_int(vol_size):
                            result = False
                            msg = f"""'{vm["name"]}'에서 '{disk["snapshot_name"]}'의 'vol_size'는 {vol_size}여야 합니다."""
                            append_msg_list(msg_list, key, msg)

    vm_list = []
    for key_vm in key_vm_list:
        vm_list.append(key_vm["params"])

    # VM name 중복 확인
    duplicates = find_duplicates("name", vm_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""'{str}' VM 이름이 중복됩니다."""
        append_msg_list(msg_list, "syntax_error", msg)
        result = False

    # fixed ip중복 확인 : json내
    duplicates = find_duplicates("fixed_ip", vm_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""'{str}' fixed_ip가 중복됩니다."""
        append_msg_list(msg_list, "syntax_error", msg)
        result = False

    return result, msg_list


# lb_list의 유효성 검사
# key_lb_list 형식
"""
    {
        "key" : xxx,
        "type" : "lb",
        "params" : {}
    }
"""


def validate_lb_list(key_lb_list, subnet_list, vm_list, old_lb_list, action):
    result = True
    msg_list = []

    if len(key_lb_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_lb in key_lb_list:
        lb = key_lb["params"]
        key = key_lb["key"]

        key_lb["state"] = "none"

        if "name" not in lb:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        result_tmp, msg_tmp = check_key_list(
            lb,
            [
                "option",
                "service_ip",
                "service_port",
                "service_type",
                "healthcheck_type",
                "subnet",
            ],
        )
        if result_tmp == False:
            msg = f"""'{lb["name"]}'에서 {msg_tmp}"""
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if check_exist_in_dict_list("lb_name", lb["name"], old_lb_list):
            msg = f"""'{lb["name"]}'은 기존 생성된 LB 이름과 중복됩니다."""
            append_msg_list(msg_list, key, msg)
            key_lb["state"] = "created"
            if action == "all":
                result = False

        if not validate_string(lb["name"]):
            result = False
            msg = f"""'{lb["name"]}'은 잘못된 name입니다. 영문자, 숫자, '-'로 구성되며, 첫글자는 영문자여야 합니다."""
            append_msg_list(msg_list, key, msg)

        service_port = str_to_int(lb["service_port"])
        lb["service_port"] = service_port
        if service_port < 1 or service_port > 65535:
            result = False
            msg = f"""'{lb["name"]}'에서 server_port '{service_port}'는 잘못된 값입니다."""
            append_msg_list(msg_list, key, msg)

        if not check_exist_in_dict_list("subnet_name", lb["subnet"], subnet_list):
            result = False
            msg = f"""'{lb["name"]}'에서 '{lb["subnet"]}'논 존재하지 않는 Subnet 입니다."""
            append_msg_list(msg_list, key, msg)

        if "service_ip" in lb:
            if lb["service_ip"].startswith("new_"):
                if not check_new_ip_format(lb["service_ip"]):
                    result = False
                    msg = f"""{index} 번째 설정에서 '{nat["public_ip"]}'은 표현식 오류입니다. (예, new_001, new_123)"""
                    append_msg_list(msg_list, key, msg)
            else:
                if not is_ip_address(lb["service_ip"]):
                    result = False
                    msg = f"""'{lb["name"]}'에서 '{lb["service_ip"]}'논 잘못된 IP주소 입니다."""
                    append_msg_list(msg_list, key, msg)

                if not check_exist_in_dict_list(
                    "service_ip", lb["service_ip"], old_lb_list
                ):
                    result = False
                    msg = f"""'{lb["name"]}'에서 '{lb["service_ip"]}'는 기존 LB에서 사용하고 있지 않는 IP입니다."""
                    append_msg_list(msg_list, key, msg)
                else:
                    # serivce_ip, service_port의 기존 LB 중복 확인
                    for old_lb in old_lb_list:
                        if lb["service_ip"] == old_lb["service_ip"]:
                            old_port = str_to_int(old_lb["service_port"])
                            if lb["service_port"] == old_port:
                                msg = f"""'{lb["name"]}'에서 '{lb["service_ip"]}' service_ip, '{lb["service_port"]}' service_port 는 기존 LB와 중복됩니다."""
                                append_msg_list(msg_list, key, msg)
                                result = False

        if "server_list" in lb:
            if not "server_port" in lb:
                result = False
                msg = f"""'{lb["name"]}'에서 'server_list"가 존재하는 경우, 'server_port"는 필수 항목입니다."""
                append_msg_list(msg_list, key, msg)
            else:
                lb["server_port"] = str_to_int(lb["server_port"])

            # 연결 서버의 유효성 검증 및 정보 조회
            vm_name_list = lb["server_list"]

            for vm_name in vm_name_list:
                if vm_name.startswith("@res"):
                    continue
                if not check_exist_in_dict_list("vm_name", vm_name, vm_list):
                    result = False
                    msg = f"""'{lb["name"]}'에서 '{lb["server_list"]}'에 존재하지 않는 vm name이 있습니다."""
                    append_msg_list(msg_list, key, msg)

        ciphergroup_name = (
            None if "ciphergroup_name" not in lb else lb["ciphergroup_name"]
        )
        tlsv1 = None if "tlsv1" not in lb else lb["tlsv1"]
        tlsv11 = None if "tlsv11" not in lb else lb["tlsv11"]
        tlsv12 = None if "tlsv12" not in lb else lb["tlsv12"]
        healthcheck_url = None if "healthcheck_url" not in lb else lb["healthcheck_url"]

        try:
            check_parameter_validation(
                lb["option"],
                lb["service_type"],
                lb["healthcheck_type"],
                healthcheck_url,
                ciphergroup_name,
                tlsv1,
                tlsv11,
                tlsv12,
            )
        except Exception as e:
            result = False
            msg = f"""'{lb["name"]}' 파라메타 에러 : {e}"""
            append_msg_list(msg_list, key, msg)

    lb_list = []
    for lb in key_lb_list:
        lb_list.append(lb["params"])

    # name 중복 확인
    duplicates = find_duplicates("name", lb_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""'{str}' LB 이름이 중복됩니다."""
        append_msg_list(msg_list, "duplicate_error", msg)
        result = False

    # service_ip가 같은 경우, service_port 중복 확인 : json내
    result_tmp, msg_tmp = validate_duplicate_two_keys(
        lb_list, "service_ip", "service_port"
    )
    if result_tmp == False:
        msg = f"""LB정보에서 {msg_tmp}"""
        append_msg_list(msg_list, "syntax_error", msg)
        result = False

    # server_list 중복 확인 : 중복되면 LB연결되지 않음.
    duplicates = find_duplicates_server_list(lb_list)
    if len(duplicates) > 0:
        str = ", ".join(duplicates)
        msg = f"""LB의 server_list의 '{str}' VM 이름이 중복됩니다."""
        append_msg_list(msg_list, "duplicate_error", msg)
        result = False

    # service_ip와 subnet의 pair는 항상 동일해야 한다.
    if validate_key_consistency(lb_list, "service_ip", "subnet") == False:
        msg = f"""LB의 'service_ip'와 'subnet' pair가 다른 경우가 있습니다."""
        append_msg_list(msg_list, "consistancy_error", msg)
        result = False

    return result, msg_list


def check_key_list(target, key_list):
    result = True
    msg = ""

    for key in key_list:
        if key not in target:
            result = False
            msg = f"""'{key}' 필드는 필수 항목입니다."""
            break

    return result, msg


# key1의 value와 key2의 value가 pair로 항상 동일하면 True, 다른 경우가 있으면 False
def validate_key_consistency(data: list, key1: str, key2: str) -> bool:
    mapping = {}

    for item in data:
        k1_value = item.get(key1)
        k2_value = item.get(key2)

        if k1_value in mapping:
            if mapping[k1_value] != k2_value:
                # 다른 경우가 발견되면 False
                return False
        else:
            mapping[k1_value] = k2_value

    return True


def is_valid_domain(domain):
    pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z]{2,})+$"
    return bool(re.fullmatch(pattern, domain))


def validate_firewall_cidr(cidr_str):
    result, _ = check_cidr_list(cidr_str)

    if result == True:
        cidr_list = cidr_str.split(",")

        list_tmp = []
        for cidr in cidr_list:
            cidr_tmp = cidr.strip()
            list_tmp.append(cidr_tmp)

        return list_tmp
    else:
        raise Exception(f"firewall cidr '{cidr_str}' : cidr 양식이 맞지 않습니다.")


def check_cidr_list(cidr_str):
    result = True
    msg = ""

    cidr_list = cidr_str.split(",")

    list_tmp2 = []
    for cidr in cidr_list:
        cidr_tmp = cidr.strip()
        list_tmp2.append(cidr_tmp)

    for cidr in list_tmp2:
        if cidr.lower() == "all":
            continue

        if not is_valid_cidr(cidr):
            if not is_valid_domain(cidr):
                result = False
                msg = f"""'{cidr_str}'에 유효하지 않은 domain 표현 또는 CIDR 표현이 있습니다."""

    return result, msg


# dict list내에서 2개의 key가 동시에 중복되는 항목 검사
def validate_duplicate_two_keys(dict_list, key1, key2):
    # 중복된 항목 찾기
    duplicates = defaultdict(list)

    for item in dict_list:
        key_pair = (item[key1], item[key2])  # (name, age) 조합을 키로 사용
        duplicates[key_pair].append(item)

    for key_pair, items in duplicates.items():
        if len(items) > 1:
            msg = f"{key_pair}: {key1}, {key2} 정보가 중복됩니다."
            return False, msg

    return True, ""


# firewall 유효성 검사
# key_fw_list 형식
"""
    {
        "key" : xxx,
        "type" : "firewall",
        "params" : {}
    }
"""


def validate_firewall_list(
    key_fw_list, subnet_list, pf_list, sn_list, old_fw_list, action
):
    result = True
    msg_list = []

    if len(key_fw_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_fw in key_fw_list:
        key = key_fw["key"]
        fw_list = key_fw["params"]

        index = 0
        for fw in fw_list:
            index += 1

            if "type" not in fw:
                msg = "'type' 필드는 필수 항목입니다."
                append_msg_list(msg_list, key, msg)
                return False, msg_list
            if fw["type"] not in firewall_type_list:
                example = ", ".join(firewall_type_list)
                msg = f"""{index} 번째 설정에서 '{fw["type"]}'은 잘못 입력된 type입니다. options: {example}"""
                append_msg_list(msg_list, key, msg)
                return False, msg_list

            if fw["type"] == "net2net":
                result_tmp, msg_tmp = check_key_list(
                    fw,
                    [
                        "src_net",
                        "src_cidr",
                        "dst_net",
                        "dst_cidr",
                        "protocol",
                        "action",
                    ],
                )
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if not check_exist_in_dict_list(
                    "subnet_name", fw["src_net"], subnet_list
                ):
                    msg = f"""{index} 번째 설정에서 '{fw["src_net"]}'논 존재하지 않는 Subnet 입니다."""
                    append_msg_list(msg_list, key, msg)
                    result = False

                result_tmp, msg_tmp = check_cidr_list(fw["src_cidr"])
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if (
                    not check_exist_in_dict_list(
                        "subnet_name", fw["dst_net"], subnet_list
                    )
                    and fw["dst_net"] != "external"
                ):
                    msg = f"""{index} 번째 설정에서 '{fw["dst_net"]}'논 존재하지 않는 Subnet 입니다. 인터넷 연동시 'external'을 기재하세요."""
                    append_msg_list(msg_list, key, msg)
                    result = False

                result_tmp, msg_tmp = check_cidr_list(fw["dst_cidr"])
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if fw["protocol"] not in firewall_protocol_list:
                    example = ", ".join(firewall_protocol_list)
                    msg = f"""{index} 번째 설정에서 '{fw["protocol"]}'은 잘못 입력된 protocol 입니다. options : {example}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if fw["action"] != "allow" and fw["action"] != "deny":
                    msg = f"""{index} 번째 설정에서 '{fw["action"]}'은 잘못 입력된 action 입니다. options : "allow", "deny" """
                    append_msg_list(msg_list, key, msg)
                    result = False

                if "start_port" in fw:
                    start_port = str_to_int(fw["start_port"])
                    fw["start_port"] = start_port
                    if start_port < 1 or start_port > 65535:
                        msg = f"""{index} 번째 설정에서 start_port '{start_port}'는 잘못된 값입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

                    end_port = str_to_int(fw["end_port"])
                    fw["end_port"] = end_port
                    if end_port < 1 or end_port > 65535:
                        msg = f"""{index} 번째 설정에서 end_port '{end_port}'는 잘못된 값입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False
                    if end_port < start_port:
                        msg = f"""{index} 번째 설정에서 end_port '{end_port}'는 start_port '{start_port}' 보다 크거나 같아야 합니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

            elif fw["type"] == "port_forward":
                result_tmp, msg_tmp = check_key_list(fw, ["src_cidr", "dst_cidr"])
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                result_tmp, msg_tmp = check_cidr_list(fw["src_cidr"])
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if not check_exist_in_dict_list("name", fw["dst_cidr"], pf_list):
                    if fw["dst_cidr"].startswith("@res"):
                        continue
                    else:
                        msg = f"""{index} 번째 설정에서 'dst_cidr'의 '{fw["dst_cidr"]}'이 존재하지 않는 이름입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

            elif fw["type"] == "static_nat":
                result_tmp, msg_tmp = check_key_list(
                    fw, ["src_cidr", "dst_cidr", "protocol"]
                )
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                result_tmp, msg_tmp = check_cidr_list(fw["src_cidr"])
                if result_tmp == False:
                    msg = f"""{index} 번째 설정에서 {msg_tmp}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

                if not check_exist_in_dict_list("name", fw["dst_cidr"], sn_list):
                    if fw["dst_cidr"].startswith("@res"):
                        continue
                    else:
                        msg = f"""{index} 번째 설정에서 'dst_cidr'의 '{fw["dst_cidr"]}'이 존재하지 않는 이름입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

                if "start_port" in fw:
                    start_port = str_to_int(fw["start_port"])
                    fw["start_port"] = start_port
                    if start_port < 1 or start_port > 65535:
                        msg = f"""{index} 번째 설정에서 start_port '{start_port}'는 잘못된 값입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

                    end_port = str_to_int(fw["end_port"])
                    fw["end_port"] = end_port
                    if end_port < 1 or end_port > 65535:
                        msg = f"""{index} 번째 설정에서 end_port '{end_port}'는 잘못된 값입니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False
                    if end_port < start_port:
                        msg = f"""{index} 번째 설정에서 end_port '{end_port}'는 start_port '{start_port}' 보다 크거나 같아야 합니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False

                if fw["protocol"] not in firewall_protocol_list:
                    example = ", ".join(firewall_protocol_list)
                    msg = f"""{index} 번째 설정에서 '{fw["protocol"]}'은 잘못 입력된 protocol 입니다. options : {example}"""
                    append_msg_list(msg_list, key, msg)
                    result = False

        # acl 중복 확인
        for i, fw in enumerate(fw_list):
            acl_id = search_acl(fw, old_fw_list)
            if acl_id != None:
                msg = f"""{i+1}번재 acl은 기존에 생성된 ACL 입니다."""
                append_msg_list(msg_list, key, msg)
                if action == "all":
                    result = False

    return result, msg_list


def check_new_ip_format(string):
    pattern = r"^new_\d+$"  # 정규식: new_로 시작하고 숫자가 뒤에 붙음
    return bool(re.match(pattern, string))


def get_public_ip_type(public_ip, ip_list):
    for ip in ip_list:
        if ip["publicip"] == public_ip:
            return ip["type"]


# ip 유효성 검사
# key_ip_list 형식
"""
    {
        "key" : xxx,
        "type" : "publicip",
        "params" : {}
    }
"""


def validate_ip_list(key_nat_list, vm_list, lb_list, ip_list, pf_list, sn_list, action):
    result = True
    msg_list = []

    if len(key_nat_list) == 0:
        msg = "내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    nat_list = []
    for key_nat in key_nat_list:
        nat_list.append(key_nat["params"])

    for key_nat in key_nat_list:
        nat = key_nat["params"]
        key = key_nat["key"]

        key_nat["state"] = "none"
        key_nat["set"] = "none"

        if "type" not in nat:
            msg = "'type' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list
        if nat["type"] not in nat_ip_type_list:
            example = ", ".join(nat_ip_type_list)
            msg = f"""'{nat["type"]}'은 잘못 입력된 type입니다. options: {example}"""
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if nat["type"] == "port_forward":
            result_tmp, msg_tmp = check_key_list(
                nat,
                [
                    "public_ip",
                    "target",
                    "target_name",
                    "private_port",
                    "public_port",
                    "protocol",
                ],
            )
            if result_tmp == False:
                msg = msg_tmp
                append_msg_list(msg_list, key, msg)
                return False, msg_list

            nat["public_port"] = str_to_int(nat["public_port"])
            nat["private_port"] = str_to_int(nat["private_port"])

            if nat["public_ip"].startswith("new_"):
                if not check_new_ip_format(nat["public_ip"]):
                    result = False
                    msg = f"""'{nat["public_ip"]}'은 표현식 오류입니다. (예, new_001, new_123)"""
                    append_msg_list(msg_list, key, msg)
            else:
                if check_exist_in_dict_list("publicip", nat["public_ip"], ip_list):
                    # IP주소가 이미 생성되어 있음.
                    key_nat["state"] = "created"
                    ip_type = get_public_ip_type(nat["public_ip"], ip_list)
                    if ip_type == "STATICNAT":
                        msg = f"""'{nat["public_ip"]}'은 기존에 STAIC NAT로 구성되어 있습니다."""
                        append_msg_list(msg_list, key, msg)
                        result = False
                    elif ip_type == "PORTFORWARDING":
                        # public port가 중복되지 않아야 한다.
                        public_port_list = get_list_in_dict_list(
                            "publicip", nat["public_ip"], "public_port", pf_list
                        )
                        for public_port in public_port_list:
                            public_port = str_to_int(public_port)
                            if public_port == nat["public_port"]:
                                msg = f"""'{nat["public_ip"]}' public_ip와 {nat["public_port"]} public_port는 기존에 구성되어 있습니다."""
                                append_msg_list(msg_list, key, msg)
                                key_nat["set"] = nat["public_ip"]
                                if action == "all":
                                    result = False
                else:
                    result = False
                    msg = f"""'{nat["public_ip"]}'은 기존 공인IP주소가 아닙니다."""
                    append_msg_list(msg_list, key, msg)

            if nat["target"] != "vm":
                result = False
                msg = f"""'{nat["target"]}'은 잘못 설정되었습니다. 'vm'만 가능합니다."""
                append_msg_list(msg_list, key, msg)

            if not check_exist_in_dict_list("vm_name", nat["target_name"], vm_list):
                if nat["target_name"].startswith("@res"):
                    continue
                else:
                    result = False
                    msg = f"""'{nat["target_name"]}'은 존재하지 않는 VM 입니다."""
                    append_msg_list(msg_list, key, msg)
            else:
                # vm이 sn이 아니어야 한다. pf인 경우, private_port가 중복되지 않아야 한다.
                subnets = get_value_in_dict_list(
                    "vm_name", nat["target_name"], "subnets", vm_list
                )
                private_ip = subnets[0]["privateip"]
                ret_sn = get_value_in_dict_list(
                    "privateip", private_ip, "name", sn_list
                )
                private_port_list = get_list_in_dict_list(
                    "privateip", private_ip, "private_port", pf_list
                )

                if ret_sn != None:
                    msg = f"""'{nat["target_name"]}'은 이미 static nat가 설정되어 있습니다."""
                    append_msg_list(msg_list, key, msg)
                    public_ip = get_value_in_dict_list(
                        "privateip", private_ip, "publicip", sn_list
                    )
                    key_nat["state"] = "created"
                    key_nat["set"] = public_ip
                    result = False

                for private_port in private_port_list:
                    private_port = str_to_int(private_port)
                    if private_port == nat["private_port"]:
                        public_ip = get_value_in_dict_list_two_key(
                            "privateip",
                            private_ip,
                            "private_port",
                            str(private_port),
                            "publicip",
                            pf_list,
                        )
                        if public_ip == None:
                            msg = f"""'{nat["target_name"]}' VM의 port forward 설정된 public_ip가 없습니다."""
                            append_msg_list(msg_list, key, msg)
                            result = False
                        else:
                            msg = f"""'{nat["target_name"]}' VM의 '{private_port}' private_port는 기존에 port forward 구성되어 있습니다."""
                            append_msg_list(msg_list, key, msg)
                            key_nat["state"] = "created"
                            key_nat["set"] = public_ip
                            if action == "all":
                                result = False

            private_port = int(nat["private_port"])
            if private_port < 1 or private_port > 65535:
                result = False
                msg = f"""private_port '{private_port}'는 잘못된 값입니다."""
                append_msg_list(msg_list, key, msg)

            public_port = int(nat["public_port"])
            if public_port < 1 or public_port > 65535:
                result = False
                msg = f"""public_port '{public_port}'는 잘못된 값입니다."""
                append_msg_list(msg_list, key, msg)

            if nat["protocol"] != "TCP" and nat["protocol"] != "UDP":
                result = False
                msg = f"""protocol '{nat["protocol"]}'는 잘못된 값입니다. options : TCP, UDP"""
                append_msg_list(msg_list, key, msg)

        elif nat["type"] == "static_nat":
            result_tmp, msg_tmp = check_key_list(
                nat, ["public_ip", "target", "target_name"]
            )
            if result_tmp == False:
                msg = msg_tmp
                append_msg_list(msg_list, key, msg)
                return False, msg_list

            if nat["public_ip"].startswith("new_"):
                if not check_new_ip_format(nat["public_ip"]):
                    result = False
                    msg = f"""'{nat["public_ip"]}'은 표현식 오류입니다. (예, new_001, new_123)"""
                    append_msg_list(msg_list, key, msg)
            else:
                if check_exist_in_dict_list("publicip", nat["public_ip"], ip_list):
                    key_nat["state"] = "created"
                    ip_type = get_public_ip_type(nat["public_ip"], ip_list)
                    if ip_type == "STATICNAT":
                        msg = f"""'{nat["public_ip"]}'은 기존에 STAIC NAT로 구성되어 있습니다."""
                        append_msg_list(msg_list, key, msg)
                        key_nat["set"] = nat["public_ip"]
                        if action == "all":
                            result = False
                    elif ip_type == "PORTFORWARDING":
                        result = False
                        msg = f"""'{nat["public_ip"]}'가 port forward로 설정되어 있습니다."""
                        append_msg_list(msg_list, key, msg)
                else:
                    result = False
                    msg = f"""'{nat["public_ip"]}'은 기존 공인IP주소가 아닙니다."""
                    append_msg_list(msg_list, key, msg)

            if nat["target"] == "vm":
                if not check_exist_in_dict_list("vm_name", nat["target_name"], vm_list):
                    if nat["target_name"].startswith("@res"):
                        continue
                    else:
                        result = False
                        msg = f"""'{nat["target_name"]}'은 존재하지 않는 VM 입니다."""
                        append_msg_list(msg_list, key, msg)
                else:
                    # vm이 pf, sn 모두 없어야 한다.
                    subnets = get_value_in_dict_list(
                        "vm_name", nat["target_name"], "subnets", vm_list
                    )
                    private_ip = subnets[0]["privateip"]
                    ret_pf = get_value_in_dict_list(
                        "privateip", private_ip, "name", pf_list
                    )
                    ret_sn = get_value_in_dict_list(
                        "privateip", private_ip, "name", sn_list
                    )

                    if ret_pf != None:
                        result = False
                        msg = f"""'{nat["target_name"]}'은 이미 port forward로 설정되어 있습니다."""
                        append_msg_list(msg_list, key, msg)
                    elif ret_sn != None:
                        public_ip = get_value_in_dict_list(
                            "privateip", private_ip, "publicip", sn_list
                        )
                        if public_ip == nat["public_ip"]:
                            msg = f"""'{nat["public_ip"]}'은 이미 static nat가 설정되어 있습니다."""
                            append_msg_list(msg_list, key, msg)
                            key_nat["set"] = public_ip
                            if action == "all":
                                result = False
                        else:
                            result = False
                            msg = f"""'{nat["public_ip"]}'은 이미 static nat가 설정되어 있습니다."""
                            append_msg_list(msg_list, key, msg)

            elif nat["target"] == "lb":
                if not check_exist_in_dict_list("lb_name", nat["target_name"], lb_list):
                    if nat["target_name"].startswith("@res"):
                        continue
                    else:
                        result = False
                        msg = f"""'{nat["target_name"]}'은 존재하지 않는 LB 입니다."""
                        append_msg_list(msg_list, key, msg)
                else:
                    # lb는 sn 없어야 한다.
                    private_ip = get_value_in_dict_list(
                        "lb_name", nat["target_name"], "service_ip", lb_list
                    )
                    ret_sn = get_value_in_dict_list(
                        "privateip", private_ip, "name", sn_list
                    )

                    if ret_sn != None:
                        public_ip = get_value_in_dict_list(
                            "privateip", private_ip, "publicip", sn_list
                        )
                        if public_ip == nat["public_ip"]:
                            msg = f"""'{nat["public_ip"]}'은 이미 static nat가 설정되어 있습니다."""
                            append_msg_list(msg_list, key, msg)
                            key_nat["set"] = public_ip
                            if action == "all":
                                result = False
                        else:
                            result = False
                            msg = f"""'{nat["public_ip"]}'은 이미 static nat가 설정되어 있습니다."""
                            append_msg_list(msg_list, key, msg)

            else:
                result = False
                msg = f"""'{nat["target"]}'은 잘못 설정되었습니다. 'vm', 'lb'만 가능합니다."""
                append_msg_list(msg_list, key, msg)

    # 중복 확인 static_nat
    for key_nat in key_nat_list:
        nat = key_nat["params"]
        key = key_nat["key"]
        public_ip_count = 0
        target_name_count = 0

        if nat["type"] == "static_nat":
            for key_nat2 in key_nat_list:
                nat2 = key_nat2["params"]
                if nat["public_ip"] == nat2["public_ip"]:
                    public_ip_count += 1
                if nat["target_name"] == nat2["target_name"]:
                    target_name_count += 1

            if public_ip_count > 1:
                msg = f"""'{nat["public_ip"]}'가 중복으로 작성되었습니다."""
                append_msg_list(msg_list, key, msg)
                result = False
            if target_name_count > 1:
                msg = f"""'{nat["target_name"]}'가 중복으로 작성되었습니다."""
                append_msg_list(msg_list, key, msg)
                result = False

    # 중복 확인 port_forward
    key_pf_list = []
    for key_nat in key_nat_list:
        nat = key_nat["params"]
        if nat["type"] == "port_forward":
            key_pf_list.append(nat)

    result_tmp, msg_tmp = validate_duplicate_two_keys(
        key_pf_list, "public_ip", "public_port"
    )
    if result_tmp == False:
        msg = f"""port forward설정에서 public ip와 public port set가 중복됩니다. {msg_tmp}"""
        append_msg_list(msg_list, "duplicate_error", msg)
        result = False

    result_tmp, msg_tmp = validate_duplicate_two_keys(
        key_pf_list, "target_name", "private_port"
    )
    if result_tmp == False:
        msg = f"""port forward설정에서 target name과 private port set가 중복됩니다. {msg_tmp}"""
        append_msg_list(msg_list, "duplicate_error", msg)
        result = False

    return result, msg_list


def check_lb_update(lb, old_lb):
    lb_update = False

    # print(json.dumps(lb, indent=2))
    # print(json.dumps(old_lb, indent=2))

    if lb["option"].lower() != old_lb["lb_option"].lower():
        lb_update = True

    if lb["healthcheck_type"].lower() != old_lb["healthcheck_type"].lower():
        lb_update = True

    if "healthcheck_url" in lb:
        if "healthcheck_url" in old_lb:
            if lb["healthcheck_url"] != old_lb["healthcheck_url"]:
                lb_update = True
        else:
            lb_update = True
    else:
        if "healthcheck_url" in old_lb:
            if old_lb["healthcheck_url"] != "":
                lb_update = True

    return lb_update


def check_lb_server_update(vm_info_list, old_server_list):

    if len(vm_info_list) != len(old_server_list):
        return True

    for vm_info in vm_info_list:
        is_ok = False
        for old_vm in old_server_list:
            if vm_info["id"] == old_vm["vm_id"]:
                is_ok = True
                break

        if is_ok == False:
            return True
    return False


"""
[
  {
    "name" : "yeong-lb01",
    "option" : "roundrobin",
    "service_port" : 443,
    "service_type" : "https",
    "healthcheck_type" : "http",
    "subnet" : "DMZ",
    "healthcheck_url" : "index.html", # healthcheck_type에 따라 optional
    "service_ip" : "172.25.0.100", # ""이면 신규로 생성
    "server_list" : "vm1;vm2;vm3", # LB에 연결할 VM의 이름 목록, optional
    "server_port" : 80, # server_list가 없으면 불필요
    "ciphergroup_name" : "Recommend-2025-05", # service_type이 "https" 인 경우에만 기재
    "tlsv1" : "DISABLED", # service_type이 "https" 인 경우에만 기재
    "tlsv11" : "DISABLED", # service_type이 "https" 인 경우에만 기재
    "tlsv12" : "ENABLED" # service_type이 "https" 인 경우에만 기재
  }
]
"""


def change_lb_shape(lb):
    tmp_lb = {
        key: value for key, value in lb.items() if value != "" or key == "res_name"
    }

    new_lb = copy.deepcopy(tmp_lb)
    if "server_list" in new_lb:
        vm_list = new_lb["server_list"].split(";")
        vm_list2 = []
        for vm in vm_list:
            vm_list2.append(vm.strip())
        new_lb["server_list"] = vm_list2
    return new_lb


# csv파일로 읽어온 lb_list 형식을 변형
def change_lb_list_shape(lb_list, key):
    result = True
    msg_list = []
    new_lb_list = []

    for lb in lb_list:
        if len(lb["res_name"]) != 0:
            if not validate_string2(lb["res_name"]):
                result = False
                msg = f"""'{lb["res_name"]}'은 잘못된 res_name입니다. 영문자, 숫자, '-', '_'로 구성되며, 첫글자는 영문자여야 합니다."""
                append_msg_list(msg_list, key, msg)

        if lb["name"] != "":
            new_lb = change_lb_shape(lb)
            new_lb_list.append(new_lb)

    return new_lb_list, result, msg_list


"""
[
  {
    "type" : "net2net",
    "src_net" : "DMZ",
    "src_cidr" : "172.25.0.0/24",
    "dst_net" : "Private",
    "dst_cidr" : "172.25.1.0/24",
    "start_port" : 22, # optional
    "end_port" : 22, # optional
    "protocol" : "TCP",
    "action" : "allow"
  }
]
"""


def change_fw_shape(fw):
    new_fw = {key: value for key, value in fw.items() if value != ""}
    return new_fw


# csv파일로 읽어온 fw_list 형시글 변형
def change_fw_list_shape(fw_list):
    new_fw_list = []

    for fw in fw_list:
        if fw["type"] != "":
            new_fw = change_fw_shape(fw)
            new_fw_list.append(new_fw)

    return new_fw_list


"""
[
  {
    "type" : "port_forward",
    "public_ip" : "new_001",
    "target" : "vm",
    "target_name" : "test-vm01",
    "private_port" : 22,
    "public_port" : 22,
    "protocol" : "TCP"
  }
]
"""


def change_ip_shape(ip):
    new_ip = {
        key: value for key, value in ip.items() if value != "" or key == "res_name"
    }
    return new_ip


# csv파일로 읽어온 ip_list 형시글 변형
def change_ip_list_shape(ip_list, key):
    result = True
    msg_list = []
    new_ip_list = []

    for ip in ip_list:
        if len(ip["res_name"]) != 0:
            if not validate_string2(ip["res_name"]):
                result = False
                msg = f"""'{vm["res_name"]}'은 잘못된 res_name입니다. 영문자, 숫자, '-', '_'로 구성되며, 첫글자는 영문자여야 합니다."""
                append_msg_list(msg_list, key, msg)

        if ip["type"] != "":
            new_ip = change_ip_shape(ip)
            new_ip_list.append(new_ip)

    return new_ip_list, result, msg_list


# @res name에 대한 유효성 검증
def validate_res_name(keys_list, json_form):
    result = True
    msg_list = []

    for key in keys_list:
        res_type = json_form["resources"][key]["type"]
        params = json_form["resources"][key]["params"]

        if res_type == "lb":
            if "server_list" in params:
                for server in params["server_list"]:
                    if server.startswith("@res"):
                        key_name = server.split()[1]
                        if key_name in keys_list:
                            # res_name은 맞지만, vm이 아닌 경우
                            key_type = json_form["resources"][key_name]["type"]
                            if key_type != "vm":
                                msg = f"""'{params["name"]}'의 server_list에서 '{server}'가 vm의 resource name이 아닙니다."""
                                append_msg_list(msg_list, key, msg)
                                result = False
                        else:
                            # res_name이 맞지 않은 경우
                            msg = f"""'{params["name"]}'의 server_list에서 '{server}'의 resource key name이 존재하지 않습니다."""
                            append_msg_list(msg_list, key, msg)
                            result = False
        elif res_type == "publicip":
            if "target_name" in params and "target" in params:
                if params["target"] == "vm" or params["target"] == "lb":
                    if params["target_name"].startswith("@res"):
                        key_name = params["target_name"].split()[1]
                        if key_name in keys_list:
                            # res_name은 맞지만, vm이 아닌 경우
                            key_type = json_form["resources"][key_name]["type"]
                            if params["target"] == "vm" and key_type != "vm":
                                msg = f"""target_name 에서 '{key_name}'가 vm의 resource name이 아닙니다."""
                                append_msg_list(msg_list, key, msg)
                                result = False
                            if params["target"] == "lb" and key_type != "lb":
                                msg = f"""target_name 에서 '{key_name}'가 LB의 resource name이 아닙니다."""
                                append_msg_list(msg_list, key, msg)
                                result = False
                        else:
                            # res_name이 맞지 않은 경우
                            msg = f"""target_name 에서 '{key_name}'의 resource key name이 존재하지 않습니다."""
                            append_msg_list(msg_list, key, msg)
                            result = False
        elif res_type == "firewall":
            for i, acl in enumerate(params):
                if "dst_cidr" in acl and "type" in acl:
                    if acl["dst_cidr"].startswith("@res"):
                        key_name = acl["dst_cidr"].split()[1]
                        if key_name in keys_list:
                            key_type = json_form["resources"][key_name]["type"]
                            if key_type == "publicip":
                                param_type = json_form["resources"][key_name]["params"][
                                    "type"
                                ]
                                if (
                                    acl["type"] == "static_nat"
                                    and param_type != "static_nat"
                                ):
                                    msg = f"""'{i+1}'번째 dst_cidr 에서 '{key_name}'가 static nat resource가 아닙니다."""
                                    append_msg_list(msg_list, key, msg)
                                    result = False
                                if (
                                    acl["type"] == "port_forward"
                                    and param_type != "port_forward"
                                ):
                                    msg = f"""'{i+1}'번째 dst_cidr 에서 '{key_name}'가 port forward resource가 아닙니다."""
                                    append_msg_list(msg_list, key, msg)
                                    result = False
                        else:
                            msg = f"""'{i+1}'번째 dst_cidr 에서 '{key_name}'가 publicip의 resource name이 아닙니다."""
                            append_msg_list(msg_list, key, msg)
                            result = False

    return result, msg_list


# @res name정보를 실제 정보로 변환
def update_res_name(keys_list, json_form, res_key_type):
    # lb parameter 업데이트
    if res_key_type == "lb":
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            params = json_form["resources"][key]["params"]

            # validation 생략, 앞에서 했기 때문에
            if res_type == "lb":
                if "server_list" in params:
                    for i, server in enumerate(params["server_list"]):
                        if server.startswith("@res"):
                            key_name = server.split()[1]
                            json_form["resources"][key]["params"]["server_list"][i] = (
                                json_form["resources"][key_name]["params"]["name"]
                            )

    # ip parameter 업데이트
    elif res_key_type == "publicip":
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            params = json_form["resources"][key]["params"]

            # validation 생략, 앞에서 했기 때문에
            if res_type == "publicip":
                if params["target_name"].startswith("@res"):
                    key_name = params["target_name"].split()[1]
                    json_form["resources"][key]["params"]["target_name"] = json_form[
                        "resources"
                    ][key_name]["params"]["name"]

    # firewall parameter 업데이트
    elif res_key_type == "firewall":
        for key in keys_list:
            res_type = json_form["resources"][key]["type"]
            params = json_form["resources"][key]["params"]

            # validation 생략, 앞에서 했기 때문에
            if res_type == "firewall":
                for i, acl in enumerate(params):
                    if acl["dst_cidr"].startswith("@res"):
                        key_name = acl["dst_cidr"].split()[1]
                        json_form["resources"][key]["params"][i]["dst_cidr"] = (
                            json_form["resources"][key_name]["nat_name"]
                        )


# vm_list 삭제를 위한 유효성 검사
def validate_delete_vm_list(key_vm_list, old_vm_list, action):
    result = True
    msg_list = []

    if len(key_vm_list) == 0:
        msg = "vm_list 내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_vm in key_vm_list:
        key = key_vm["key"]
        vm = key_vm["params"]

        if "name" not in vm:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if not check_exist_in_dict_list("vm_name", vm["name"], old_vm_list):
            msg = f"""'{vm["name"]}'은 존재하지 않는 VM 이름입니다."""
            append_msg_list(msg_list, key, msg)
            key_vm["state"] = "none"
            if action == "all":
                result = False
        else:
            msg = f"""'{vm["name"]}'은 삭제 대상 VM 입니다."""
            append_msg_list(msg_list, key, msg)
            key_vm["state"] = "created"

    return result, msg_list


# lb_list 삭제를 위한 유효성 검사
def validate_delete_lb_list(key_lb_list, old_lb_list, action):
    result = True
    msg_list = []

    if len(key_lb_list) == 0:
        msg = "lb_list 내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_lb in key_lb_list:
        key = key_lb["key"]
        lb = key_lb["params"]

        if "name" not in lb:
            msg = "'name' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if not check_exist_in_dict_list("lb_name", lb["name"], old_lb_list):
            msg = f"""'{lb["name"]}'은 존재하지 않는 LB 이름입니다."""
            append_msg_list(msg_list, key, msg)
            key_lb["state"] = "none"
            if action == "all":
                result = False
        else:
            msg = f"""'{lb["name"]}'은 삭제 대상 LB입니다."""
            append_msg_list(msg_list, key, msg)
            key_lb["state"] = "created"

    return result, msg_list


# ip_list 삭제를 위한 유효성 검사
def validate_delete_ip_list(key_ip_list, old_ip_list, vpc, action):
    result = True
    msg_list = []

    if len(key_ip_list) == 0:
        msg = "ip_list 내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for i, key_ip in enumerate(key_ip_list):
        key = key_ip["key"]
        ip = key_ip["params"]
        key_ip["state"] = "none"
        key_ip["set"] = "none"

        if "type" not in ip:
            msg = "'type' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if "public_ip" not in ip:
            msg = "'public_ip' 필드는 필수 항목입니다."
            append_msg_list(msg_list, key, msg)
            return False, msg_list

        if key_ip["params"]["type"] == "static_nat":
            sn_id = vpc._get_staticnat_id(key_ip["nat_name"])
            if sn_id:
                msg = f"""static nat 설정은 삭제 대상입니다."""
                append_msg_list(msg_list, key, msg)
                key_ip["set"] = "set"
            else:
                msg = f"""삭제할 static nat 설정이 없습니다."""
                append_msg_list(msg_list, key, msg)
                if action == "all":
                    result = False

            if key_ip["params"]["public_ip"].startswith("new_"):
                public_ip = vpc._get_staticnat_publicip(key_ip["nat_name"])
                if public_ip:
                    msg = f"""'{public_ip}' public ip는 삭제 대상입니다."""
                    append_msg_list(msg_list, key, msg)
                    key_ip["state"] = "created"
                else:
                    msg = f"""삭제할 public ip가 없습니다."""
                    append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
            else:
                if not check_exist_in_dict_list(
                    "publicip", ip["public_ip"], old_ip_list
                ):
                    msg = f"""'{ip["public_ip"]}'은 존재하지 않는 공인IP 입니다."""
                    append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
                else:
                    msg = f"""'{ip["public_ip"]}'은 삭제 대상 IP입니다."""
                    append_msg_list(msg_list, key, msg)
                    key_ip["state"] = "created"

        elif key_ip["params"]["type"] == "port_forward":
            pf_id = vpc._get_portforward_id(key_ip["nat_name"])
            if pf_id:
                msg = f"""port forward 설정은 삭제 대상입니다."""
                append_msg_list(msg_list, key, msg)
                key_ip["set"] = "set"
            else:
                msg = f"""삭제할 port forward 설정이 없습니다."""
                append_msg_list(msg_list, key, msg)
                if action == "all":
                    result = False

            if key_ip["params"]["public_ip"].startswith("new_"):
                public_ip = vpc._get_portforward_publicip(key_ip["nat_name"])
                if public_ip:
                    msg = f"""'{public_ip}' public ip는 삭제 대상입니다."""
                    append_msg_list(msg_list, key, msg)
                    key_ip["state"] = "created"
                else:
                    msg = f"""삭제할 public ip가 없습니다."""
                    append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
            else:
                if not check_exist_in_dict_list(
                    "publicip", ip["public_ip"], old_ip_list
                ):
                    msg = f"""'{ip["public_ip"]}'은 존재하지 않는 공인IP 입니다."""
                    append_msg_list(msg_list, key, msg)
                    if action == "all":
                        result = False
                else:
                    msg = f"""'{ip["public_ip"]}'은 삭제 대상 IP입니다. 삭제 여부는 port forward 설정 존재 여부에 따라 결정됩니다."""
                    append_msg_list(msg_list, key, msg)
                    key_ip["state"] = "created"

    return result, msg_list


def check_cidr_match(str_cidr, list_cidr):
    list_tmp = str_cidr.split(",")
    list_tmp2 = []

    for cidr in list_tmp:
        cidr_tmp = cidr.strip()
        list_tmp2.append(cidr_tmp)

    for item in list_tmp2:
        is_ok = False
        for cidr in list_cidr:
            if cidr["name"] == "all":
                if item == "0.0.0.0/0":
                    is_ok = True
                    break
            if item == cidr["name"]:
                is_ok = True
                break
        if is_ok == False:
            return False

    return True


def str_to_int(port_str):
    return int(port_str) if isinstance(port_str, str) else port_str


def get_net_name(net_name):
    if net_name == "external":
        return net_name
    else:
        return net_name + "_Sub"


# fw_list에서 acl을 검색
def search_acl(acl, fw_list):
    acl_id = None

    for fw in fw_list:
        is_ok = False
        if acl["type"] == "net2net":
            if get_net_name(acl["src_net"]) != fw["src_nets"][0]["name"]:
                continue
            if not check_cidr_match(acl["src_cidr"], fw["src_addrs"]):
                continue
            if get_net_name(acl["dst_net"]) != fw["dst_nets"][0]["name"]:
                continue
            if not check_cidr_match(acl["dst_cidr"], fw["dst_addrs"]):
                continue

            if "start_port" in acl:
                if "startPort" in fw["services"][0]:
                    if str_to_int(acl["start_port"]) != str_to_int(
                        fw["services"][0]["startPort"]
                    ):
                        continue
            else:
                if "startPort" in fw["services"][0]:
                    continue

            if "end_port" in acl:
                if "endPort" in fw["services"][0]:
                    if str_to_int(acl["end_port"]) != str_to_int(
                        fw["services"][0]["endPort"]
                    ):
                        continue
            else:
                if "endPort" in fw["services"][0]:
                    continue

            if acl["protocol"] != fw["services"][0]["protocol"]:
                continue
            if acl["action"] != fw["action"]:
                continue
            is_ok = True

        elif acl["type"] == "static_nat":
            if not check_cidr_match(acl["src_cidr"], fw["src_addrs"]):
                continue
            if not check_cidr_match(acl["dst_cidr"], fw["dst_addrs"]):
                continue

            if "start_port" in acl:
                if "startPort" in fw["services"][0]:
                    if str_to_int(acl["start_port"]) != str_to_int(
                        fw["services"][0]["startPort"]
                    ):
                        continue
            else:
                if "startPort" in fw["services"][0]:
                    continue

            if "end_port" in acl:
                if "endPort" in fw["services"][0]:
                    if str_to_int(acl["end_port"]) != str_to_int(
                        fw["services"][0]["endPort"]
                    ):
                        continue
            else:
                if "endPort" in fw["services"][0]:
                    continue

            if acl["protocol"] != fw["services"][0]["protocol"]:
                continue
            is_ok = True

        elif acl["type"] == "port_forward":
            if not check_cidr_match(acl["src_cidr"], fw["src_addrs"]):
                continue
            if not check_cidr_match(acl["dst_cidr"], fw["dst_addrs"]):
                continue
            is_ok = True

        if is_ok:
            acl_id = fw["acl_id"]
            break

    return acl_id


# fw_list 삭제를 위한 유효성 검사
def validate_delete_firewall_list(key_fw_list, old_fw_list, action):
    result = True
    msg_list = []

    if len(key_fw_list) == 0:
        msg = "fw_list 내용이 비어 있습니다."
        append_msg_list(msg_list, "syntax_error", msg)
        return False, msg_list

    for key_fw in key_fw_list:
        key = key_fw["key"]
        fw_list = key_fw["params"]

        for i, fw in enumerate(fw_list):
            if "type" not in fw:
                msg = f"""{i+1}번재 acl에서 'type' 필드는 필수 항목입니다."""
                append_msg_list(msg_list, key, msg)
                return False, msg_list

            acl_id = search_acl(fw, old_fw_list)
            if acl_id == None:
                msg = f"""{i+1}번재 acl은 Firewall에 존재하지 않습니다."""
                append_msg_list(msg_list, key, msg)
                if action == "all":
                    result = False
            else:
                msg = f"""{i+1}번재 acl은 삭제 대상입니다."""
                append_msg_list(msg_list, key, msg)

    return result, msg_list


def append_msg_list(msg_list, key, msg):
    msg_dict = {key: msg}
    msg_list.append(msg_dict)
    print(msg_dict)


# json파일 읽어오기
def read_json_form(json_file):
    try:
        with open(json_file, "r") as file:
            json_form = json.load(
                file, object_pairs_hook=check_duplicate_keys
            )  # JSON을 dict 타입으로 변환
    except json.JSONDecodeError as e:
        msg = f"파일이 json형식에 맞지 않습니다. Error at line {e.lineno}"
        return False, msg, None
    except ValueError as e:  # 중복 키 예외 처리
        return False, str(e), None

    return True, "", json_form


def check_duplicate_keys(pairs):
    """JSON 키 중복 확인 후, 중복되면 ValueError 발생"""
    key_counts = Counter(key for key, _ in pairs)
    duplicates = [key for key, count in key_counts.items() if count > 1]

    if duplicates:
        raise ValueError(f"중복된 키 발견: {', '.join(duplicates)}")

    return dict(pairs)


def random_res_name(prefix):
    ran_str = generate_random_string()
    return prefix + ran_str
