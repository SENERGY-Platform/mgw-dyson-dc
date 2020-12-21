"""
   Copyright 2020 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


__all__ = ("Discovery", )


from util import get_logger, conf, MQTTClient, Storage, diff, to_dict
from .device import Device
import urllib3
import threading
import subprocess
import requests
import time
import json
import typing
import socket
import mgw_dc


logger = get_logger(__name__.split(".", 1)[-1])

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

probe_ports = [int(port) for port in str(conf.Discovery.ports).split(";")]


def get_cloud_credentials() -> typing.Tuple[str, str]:
    try:
        resp = requests.post(
            url="{}/{}?country={}".format(conf.Discovery.cloud_url, conf.Discovery.cloud_auth_api, conf.Account.country),
            json={"Email": conf.Account.email, "Password": conf.Account.pw},
            verify=False
        )
        if resp.ok:
            data = resp.json()
            return data["Account"], data["Password"]
        else:
            raise RuntimeError(resp.status_code)
    except Exception as ex:
        raise RuntimeError("retrieving cloud credentials failed - {}".format(ex))


def get_cloud_devices(acc: str, pw: str):
    try:
        resp = requests.get(
            url="{}/{}".format(conf.Discovery.cloud_url, conf.Discovery.cloud_provisioning_api),
            auth=(acc, pw),
            verify=False
        )
        if resp.ok:
            data = resp.json()
            devices = dict()
            for item in data:
                devices["{}{}".format(conf.Discovery.device_id_prefix, item['Serial'])] = {
                    "name": item["Name"],
                    "model": item["ProductType"],
                    # "serial": item['Serial'],
                    "local_credentials": item["LocalCredentials"],
                    "last_seen": time.time()
                }
            return devices
        else:
            raise RuntimeError(resp.status_code)
    except Exception as ex:
        raise RuntimeError("retrieving devices from cloud failed - {}".format(ex))


def ping(host) -> bool:
    return subprocess.call(['ping', '-c', '2', '-t', '2', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def get_local_ip() -> str:
    try:
        with open(conf.Discovery.ip_file, "r") as file:
            ip_addr = file.readline().strip()
        if ip_addr:
            logger.debug("host ip address is '{}'".format(ip_addr))
            return ip_addr
        else:
            raise RuntimeError("file empty")
    except Exception as ex:
        raise Exception("could not get local ip - {}".format(ex))


def get_ip_range(local_ip) -> list:
    split_ip = local_ip.rsplit('.', 1)
    base_ip = split_ip[0] + '.'
    if len(split_ip) > 1:
        ip_range = [str(base_ip) + str(i) for i in range(1, 255)]
        ip_range.remove(local_ip)
        return ip_range
    return list()


def discover_hosts_worker(ip_range, alive_hosts):
    for ip in ip_range:
        if ping(ip):
            alive_hosts.append(ip)


def discover_hosts() -> list:
    ip_range = get_ip_range(get_local_ip())
    logger.debug("scanning ip range '{}-254' ...".format(ip_range[0]))
    alive_hosts = list()
    workers = list()
    bin = 0
    bin_size = 3
    if ip_range:
        for i in range(int(len(ip_range) / bin_size)):
            worker = threading.Thread(target=discover_hosts_worker, name='discoverHostsWorker', args=(ip_range[bin:bin + bin_size], alive_hosts))
            workers.append(worker)
            worker.start()
            bin = bin + bin_size
        if ip_range[bin:]:
            worker = threading.Thread(target=discover_hosts_worker, name='discoverHostsWorker', args=(ip_range[bin:], alive_hosts))
            workers.append(worker)
            worker.start()
        for worker in workers:
            worker.join()
    return alive_hosts


def probe_hosts_worker(hosts, positive_hosts: dict):
    for host in hosts:
        try:
            hostname = socket.getfqdn(host)
            if hostname != host:
                for port in probe_ports:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(conf.Discovery.probe_timeout)
                    try:
                        s.connect((host, port))
                        s.close()
                        positive_hosts[hostname.upper()] = (host, port)
                        break
                    except Exception:
                        pass
        except Exception:
            pass


def probe_hosts(hosts) -> dict:
    positive_hosts = dict()
    workers = list()
    bin = 0
    bin_size = 2
    if len(hosts) <= bin_size:
        worker = threading.Thread(target=probe_hosts_worker, name='validateHostsWorker', args=(hosts, positive_hosts))
        workers.append(worker)
        worker.start()
    else:
        for i in range(int(len(hosts) / bin_size)):
            worker = threading.Thread(target=probe_hosts_worker, name='validateHostsWorker', args=(hosts[bin:bin + bin_size], positive_hosts))
            workers.append(worker)
            worker.start()
            bin = bin + bin_size
        if hosts[bin:]:
            worker = threading.Thread(target=probe_hosts_worker, name='validateHostsWorker', args=(hosts[bin:], positive_hosts))
            workers.append(worker)
            worker.start()
    for worker in workers:
        worker.join()
    return positive_hosts


class Discovery(threading.Thread):
    __devices_table = (
        "devices",
        (
            "id TEXT NOT NULL UNIQUE PRIMARY KEY",
            "name TEXT NOT NULL",
            "model TEXT NOT NULL",
            "local_credentials TEXT NOT NULL",
            "last_seen TEXT NOT NULL"
        )
    )

    def __init__(self, mqtt_client: MQTTClient):
        super().__init__(name="discovery", daemon=True)
        self.__mqtt_client = mqtt_client
        self.__device_pool: typing.Dict[str, Device] = dict()
        self.__refresh_flag = False
        self.__lock = threading.Lock()
        self.__local_storage = Storage(conf.Discovery.db_path, "devices", (Discovery.__devices_table,))

    def __load_devices(self):
        while True:
            try:
                items = self.__local_storage.read(Discovery.__devices_table[0])
                if items:
                    logger.info("loading '{}' devices from local storage ...".format(len(items)))
                    for item in items:
                        if item["id"] not in self.__device_pool:
                            device = Device(**item)
                            self.__mqtt_client.publish(
                                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                                payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                                qos=1
                            )
                            self.__device_pool[item["id"]] = device
                break
            except Exception as ex:
                logger.error("loading devices from local storage failed - {}".format(ex))
                time.sleep(5)

    def __handle_new_device(self, device_id: str, data: dict):
        try:
            logger.info("adding '{}'".format(device_id))
            device = Device(id=device_id, **data)
            self.__mqtt_client.publish(
                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                qos=1
            )
            self.__device_pool[device_id] = device
        except Exception as ex:
            logger.error("adding '{}' failed - {}".format(device_id, ex))

    def __handle_missing_device(self, device_id: str):
        try:
            logger.info("removing '{}' ...".format(device_id))
            device = self.__device_pool[device_id]
            self.__mqtt_client.publish(
                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                payload=json.dumps(mgw_dc.dm.gen_delete_device_msg(device)),
                qos=1
            )
            del self.__device_pool[device_id]
        except Exception as ex:
            logger.error("removing '{}' failed - {}".format(device_id, ex))

    def __handle_existing_device(self, device_id: str, data: dict):
        try:
            logger.info("updating '{}' ...".format(device_id))
            device = self.__device_pool[device_id]
            if device.name != data["name"]:
                name_bk = device.name
                device.name = data["name"]
                try:
                    self.__mqtt_client.publish(
                        topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                        payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                        qos=1
                    )
                except Exception as ex:
                    device.name = name_bk
                    raise ex
            if device.local_credentials != data["local_credentials"]:
                device.local_credentials = data["local_credentials"]
        except Exception as ex:
            logger.error("updating '{}' failed - {}".format(device_id, ex))

    def __refresh_local_storage(self):
        try:
            logger.info("refreshing local storage ...")
            local_devices = to_dict(self.__local_storage.read(Discovery.__devices_table[0]), "id")
            remote_devices = get_cloud_devices(*get_cloud_credentials())
            new_devices, missing_devices, existing_devices = diff(local_devices, remote_devices)
            if new_devices:
                for device_id in new_devices:
                    logger.info("adding record for '{}' ...".format(device_id))
                    try:
                        self.__local_storage.create(Discovery.__devices_table[0], {"id": device_id, **remote_devices[device_id]})
                    except Exception as ex:
                        logger.error("adding record for '{}' failed - {}".format(device_id, ex))
            if missing_devices:
                for device_id in missing_devices:
                    try:
                        device_data = self.__local_storage.read(Discovery.__devices_table[0], id=device_id)
                        now = time.time()
                        age = now - float(device_data[0]["last_seen"])
                        if age > conf.Discovery.grace_period:
                            logger.info("removing record for '{}' due to exceeded grace period ...".format(device_id))
                            try:
                                self.__local_storage.delete(Discovery.__devices_table[0], id=device_id)
                            except Exception as ex:
                                logger.error("removing record for '{}' failed - {}".format(device_id, ex))
                        else:
                            logger.info(
                                "remaining grace period for missing '{}': {}s".format(
                                    device_id,
                                    conf.Discovery.grace_period - age
                                )
                            )
                    except Exception as ex:
                        logger.error("can't calculate grace period for missing '{}' - {}".format(device_id, ex))
            if existing_devices:
                for device_id in existing_devices:
                    logger.info("updating record for '{}' ...".format(device_id))
                    try:
                        self.__local_storage.update(Discovery.__devices_table[0], remote_devices[device_id], id=device_id)
                    except Exception as ex:
                        logger.error("updating record for '{}' failed - {}".format(device_id, ex))
        except Exception as ex:
            logger.error("refreshing local storage failed - {}".format(ex))

    def __refresh_devices(self):
        try:
            stored_devices = to_dict(self.__local_storage.read(Discovery.__devices_table[0]), "id")
            new_devices, missing_devices, existing_devices = diff(self.__device_pool, stored_devices)
            if new_devices:
                for device_id in new_devices:
                    self.__handle_new_device(device_id, stored_devices[device_id])
            if missing_devices:
                for device_id in missing_devices:
                    self.__handle_missing_device(device_id)
            if existing_devices:
                for device_id in existing_devices:
                    self.__handle_existing_device(device_id, stored_devices[device_id])
        except Exception as ex:
            logger.error("refreshing devices failed - {}".format(ex))

    def run(self) -> None:
        if not self.__mqtt_client.connected():
            time.sleep(3)
        logger.info("starting {} ...".format(self.name))
        self.__refresh_local_storage()
        last_cloud_check = time.time()
        self.__refresh_devices()
        while True:
            if time.time() - last_cloud_check > conf.Discovery.cloud_delay:
                self.__refresh_local_storage()
                last_cloud_check = time.time()
                self.__refresh_devices()
            try:
                positive_hosts = probe_hosts(discover_hosts())
                logger.debug(positive_hosts)
                for device in self.__device_pool.values():
                    if not device.session:
                        for hostname, data in positive_hosts.items():
                            if device.id.replace(conf.Discovery.device_id_prefix, "") in hostname:
                                logger.info("found '{}' at '{}'".format(device.id, data[0]))
            except Exception as ex:
                logger.error("discovery failed - {}".format(ex))
            time.sleep(conf.Discovery.delay)
