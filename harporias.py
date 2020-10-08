from kubernetes import client, config, watch
import os
import time
import logging
import base64
import json
import sys
from datetime import datetime
from pytz import timezone
import requests 
from requests.auth import HTTPBasicAuth

__author__ = "Felix Daniel Perez"
__license__ = "MIT"
__version__ = "1.0.0"


haproxy_url = os.environ['HA_PROXY_API_URL']
haproxy_port = os.environ['HA_PROXY_PORT']
haproxy_username = os.environ['HA_PROXY_API_USERNAME']
haproxy_password = os.environ['HA_PROXY_API_PASSWORD']
haproxy_backends = os.environ['HA_PROXY_BACKENDS']
haproxy_backend_list = haproxy_backends.split(',')

haproxy_base_url = haproxy_url+":"+haproxy_port+"/v2/services/haproxy"
haproxy_config_url = "/configuration"
haproxy_version_url = haproxy_base_url + haproxy_config_url + "/frontends"
haproxy_transaction_url = haproxy_base_url + "/transactions?version="
haproxy_servers_url = haproxy_base_url + haproxy_config_url + "/servers?backend=yourbackend"
haproxy_update_url = haproxy_base_url + haproxy_config_url + "/servers/"
haproxy_submit_url = haproxy_base_url + "/transactions/"

now_utc = datetime.now(timezone('UTC'))
transact_id = 0
service_name = 0
service_port = 0

logger = logging.getLogger('logger: ')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.__stdout__)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(lineno)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def main():

    logger.info("Current time at UTC is: %s", now_utc)
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    w = watch.Watch()
   
    for event in w.stream(v1.list_service_for_all_namespaces, label_selector="harporias=ha-proxy", timeout_seconds=0):
        service = event['object']
        if service.spec.type == 'NodePort':
            if event['type'] == 'ADDED':
               event_time = service.metadata.creation_timestamp
               if calc_time(event_time):
                  logger.info("New service event ahead, go harporias!")
                  logger.info("The event time is: %s", event_time)
                  logger.info("Service details. | Name: %s | Namespace: %s | Type: %s | Port: %s | Event: %s |", service.metadata.name, service.metadata.namespace, service.spec.type, service.spec.ports[0].node_port, event['type'])
#                  print(service)
                  if exist_resource("frontends", service.metadata.name):
                     logger.info("Configuration for the NodePort service %s exist in ha_proxy. Please, check it.", service.metadata.name)
                  else:
                     logger.info("No configuration found in ha_proxy for NodePort service %s. Adding...", service.metadata.name)
                     create_transaction_id()
                     add_haproxy_backend(service.metadata.name)
                     add_haproxy_backend_servers(service.metadata.name, service.spec.ports[0].node_port)
                     add_haproxy_frontend(service.metadata.name)
                     add_haproxy_bind(service.metadata.name, service.spec.ports[0].node_port)
                     commit_transaction(transact_id)
                     harporias_ver = get_current_version()           
               else:
                  logger.info("You are an old NodePort service event. | Name: %s | Namespace: %s | Event: %s |",service.metadata.name, service.metadata.namespace, event['type'])    
            if event['type'] == 'DELETED':
               logger.info("New service event ahead, go harporias!")
               logger.info("A NodePort service was deleted. | Name: %s | Namespace: %s |", service.metadata.name, service.metadata.namespace)
               logger.info("The event time is: %s", event_time)
               if exist_resource("frontends", service.metadata.name):
                  logger.info("Configuration for the NodePort service %s exist in ha_proxy. Removing...", service.metadata.name)
                  logger.info("Removing frontend and backend of ha_proxy...")
                  create_transaction_id()
                  delete_frontend(service.metadata.name)
                  delete_backend(service.metadata.name)
                  commit_transaction(transact_id)
                  logger.info("Resources config was removed from ha_proxy")
                  harporias_ver = get_current_version()
                  time.sleep(5)
               else:
                  logger.info("Configuration for service %s does not exist in ha_proxy", service.metadata.name)
        else:
            logger.info("You are not a NodePort service. | Name: %s | Namespace: %s | Event: %s |",service.metadata.name, service.metadata.namespace, event['type'])


def send_post(url, json_data):
    header = {"Content-Type":"application/json"}
    try:
       response = requests.post(url, data=json.dumps(json_data), headers=header, auth=(haproxy_username, haproxy_password))
       logger.info("The request URI is: %s", response.request.url)
       logger.info("The request body is: %s", str(response.request.body)) 
       logger.info("The request headers are: %s", str(response.request.headers)) 
       logger.info("The reply in json is: %s", response.json())
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))
    
def delete_frontend(frontend_name):
    logger.info("Removing frontend: %s ", frontend_name)
    url = haproxy_base_url + haproxy_config_url + "/frontends/" + frontend_name + "?transaction_id=" + transact_id
    header = {"Content-Type":"application/json"}
    try:
       response = requests.delete(url, headers=header, auth=(haproxy_username, haproxy_password))
       logger.info("Frontend removed: %s", frontend_name)
       logger.info("The request URI is: %s", response.request.url)
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))
 
def delete_backend(backend_name):
    logger.info("Removing backend: %s", backend_name)
    url = haproxy_base_url + haproxy_config_url + "/backends/" + backend_name + "?transaction_id=" + transact_id
    header = {"Content-Type":"application/json"}
    try:
       response = requests.delete(url, headers=header, auth=(haproxy_username, haproxy_password))
       logger.info("Backend removed: %s", backend_name)
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))

def add_haproxy_backend(svc_name):
    logger.info("Adding ha_proxy backend ...")
    with open("/tmp/haproxy_backend_tmpl.json", "r") as backend_json:
         data = json.load(backend_json)
         data["name"] = svc_name
         url = haproxy_base_url + haproxy_config_url + "/backends?transaction_id=" + transact_id
         send_post(url, data)
       
def add_haproxy_backend_servers(backend_name, servers_port):
    logger.info("Adding ha_proxy backend servers...")
    url = haproxy_base_url + haproxy_config_url + "/servers?backend=" + backend_name + "&transaction_id=" + transact_id
    with open("/tmp/haproxy_backend_server_tmpl.json", "r") as backend_servers_json:
        data = json.load(backend_servers_json)
        logger.info("The nodeport is: %s", str(servers_port))
        data["port"] = servers_port
        for i in haproxy_backend_list:
            data["name"] = "server"+i
            data["address"] = i
            logger.info("Adding server: %s", i)
            send_post(url, data)
            print("\n")

def add_haproxy_frontend(service_name):
    logger.info("Adding ha_proxy frontend: %s", service_name)
    url = haproxy_base_url + haproxy_config_url + "/frontends?transaction_id=" + transact_id
    with open("/tmp/haproxy_frontend_tmpl.json", "r") as frontend_json:
         data = json.load(frontend_json)
         data["name"] = service_name
         data["default_backend"] = service_name 
         send_post(url, data)

def add_haproxy_bind(frontend_name, server_port):
    logger.info("Adding ha_proxy bind to frontend: %s", frontend_name)
    url = haproxy_base_url + haproxy_config_url + "/binds?frontend=" + frontend_name + "&transaction_id=" + transact_id
    with open("/tmp/haproxy_frontend_bind_tmpl.json", "r") as bind_front_end:
         data = json.load(bind_front_end)
         data["name"] = frontend_name
         data["port"] = server_port
         send_post(url, data)

def get_current_version():
    logger.info("Getting current version number of haproxy config...")
    url = haproxy_version_url
    try:
       response = requests.get(url, auth=(haproxy_username, haproxy_password))
       r_data = response.json()
       ver = str(r_data['_version'])
       logger.info("Current version is: %s", ver)
       return ver
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))
       return 0

def commit_transaction(transaction_id):
    logger.info("Commiting transaction...")
    url = haproxy_submit_url + transaction_id
    header = {"Content-Type":"application/json"}
    try:
       response = requests.put(url, headers=header, auth=(haproxy_username, haproxy_password))
       logger.info("Transaction commit response is: %s", response.json())
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))

def create_transaction_id():
    logger.info("Creating new transaction...")
    ver = get_current_version()
    header = {"Content-Type":"application/json"}
    url = haproxy_transaction_url + ver
    try:
       response = requests.post(url, headers=header, auth=(haproxy_username, haproxy_password))
       r_data = response.json()
       tid = (r_data['id'])
       global transact_id
       transact_id = tid
       logger.info("The new transaction id is: %s", transact_id)
       return tid
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))    
       return 0

def exist_resource(resource_type, resource_name):
    logger.info("Cheking if %s %s exist in ha_proxy...", resource_type, resource_name)
    url = haproxy_base_url + haproxy_config_url + "/" + resource_type + "/" + resource_name
    try:
       response = requests.get(url, auth=(haproxy_username, haproxy_password))
       r_data = response.json()
       print(r_data)
       if 'code' in r_data:
        return False
       else:
        return True
    except requests.ConnectionError as error_con:
       logger.error("Ops, something went wrong: %s", str(error_con))

def calc_time(event_time):
    event_time = event_time.replace(microsecond=0)
    current_time = datetime.now(timezone('UTC'))
    current_time = current_time.replace(microsecond=0)
    time_diff = (current_time-event_time).total_seconds()
    if time_diff < 60:
        return True
    else:
        return False


if __name__ == '__main__':
    main()
