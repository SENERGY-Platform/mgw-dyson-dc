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


from util import get_logger, conf, MQTTClient, decrypt_password
from .device import Device
import paho.mqtt.client
import time
import json
import threading
import typing
import queue
import mgw_dc


logger = get_logger(__name__.split(".", 1)[-1])


class Session(threading.Thread):
    def __init__(self, mqtt_client: MQTTClient, device: Device, ip: str, port: int):
        super().__init__(name="session-{}".format(device.id), daemon=True)
        self.__dc_client = mqtt_client
        self.__device = device
        self.__ip = ip
        self.__port = port
        self.__session_client = paho.mqtt.client.Client()
        self.__session_client.on_connect = self.__on_connect
        self.__session_client.on_disconnect = self.__on_disconnect
        self.__session_client.on_message = self.__on_message
        # credentials = json.loads(decrypt_password(device.local_credentials))
        credentials = json.loads(device.local_credentials)
        self.__serial = credentials["serial"]
        self.__session_client.username_pw_set(username=credentials["serial"], password=credentials["apPasswordHash"])
        if conf.Session.logging:
            self.__session_client.enable_logger(logger.getChild("{}-mqtt".format(self.name)))
        self.__stop = False
        self.__sensor_trigger = threading.Thread(
            target=self.__trigger_sensor_data,
            name="{}-sensor-trigger".format(self.name),
            daemon=True
        ) if self.__device.model.gen_sensor_data_req_msg else None
        self.__command_handler = threading.Thread(
            target=self.__handle_command,
            name="{}-command-handler".format(self.name),
            daemon=True
        )
        self.__command_queue = queue.Queue()
        self.device_state: typing.Optional[dict] = None
        self.__disconnect_count = 0

    def put_command(self, cmd: tuple):
        self.__command_queue.put_nowait(cmd)

    def run(self):
        logger.info("starting {} ...".format(self.name))
        try:
            self.__session_client.connect(self.__ip, self.__port, keepalive=conf.Session.keepalive)
            self.__session_client.loop_forever()
        except Exception as ex:
            logger.error(
                "{}: could not connect to '{}' on '{}' - {}".format(
                    self.name,
                    self.__ip,
                    self.__port,
                    ex
                )
            )
        self.__stop = True
        logger.info("{} exited".format(self.name))

    def __trigger_sensor_data(self):
        logger.debug("starting {} ...".format(self.__sensor_trigger.name))
        while not self.__stop:
            if self.__session_client.is_connected():
                logger.debug("{}: triggering sensor data".format(self.__sensor_trigger.name))
                self.__session_client.publish(
                    topic=self.__device.model.command_topic.format(self.__serial),
                    payload=json.dumps(self.__device.model.gen_sensor_data_req_msg()),
                    qos=1
                )
            time.sleep(conf.Session.sensor_interval)
        logger.debug("{} exited".format(self.__sensor_trigger.name))

    def __call_service(self, service: typing.Callable, data: typing.Optional[str] = None) -> dict:
        if data:
            return service(self, **json.loads(data))
        else:
            return service(self)

    def __handle_command(self):
        logger.debug("starting {} ...".format(self.__command_handler.name))
        while not self.__stop:
            try:
                srv_id, cmd = self.__command_queue.get(timeout=30)
                logger.debug("{}: '{}' <- '{}'".format(self.__command_handler.name, srv_id, cmd))
                if not self.__session_client.is_connected():
                    raise RuntimeError("not connected to device".format(self.__device.id))
                if not self.device_state:
                    raise RuntimeError("no device state available".format(self.__device.id))
                cmd = json.loads(cmd)
                resp = str()
                if srv_id in self.__device.model.set_services:
                    self.__session_client.publish(
                        topic=self.__device.model.command_topic.format(self.__serial),
                        payload=json.dumps(
                            self.__call_service(
                                self.__device.model.set_services[srv_id],
                                cmd.get(mgw_dc.com.command.data)
                            )
                        ),
                        qos=1
                    )
                elif srv_id in self.__device.model.get_services:
                    resp = json.dumps(
                        self.__call_service(self.__device.model.get_services[srv_id], cmd.get(mgw_dc.com.command.data))
                    )
                else:
                    raise RuntimeError("service '{}' not supported".format(srv_id))
                resp_msg = mgw_dc.com.gen_response_msg(cmd[mgw_dc.com.command.id], resp)
                logger.debug("{}: '{}'".format(self.__command_handler.name, resp_msg))
                try:
                    self.__dc_client.publish(
                        topic=mgw_dc.com.gen_response_topic(self.__device.id, srv_id),
                        payload=json.dumps(resp_msg),
                        qos=1
                    )
                except Exception as ex:
                    logger.error(
                        "{}: could not send response for '{}' - {}".format(
                            self.__command_handler.name,
                            cmd[mgw_dc.com.command.id],
                            ex
                        )
                    )
            except queue.Empty:
                pass
            except Exception as ex:
                logger.error("{}: handling command failed - {}".format(self.__command_handler.name, ex))
        logger.debug("{} exited".format(self.__command_handler.name))

    def __handle_state_data(self, data: dict):
        self.device_state = self.__device.model.parse_device_state(data) if self.__device.model.parse_device_state else data
        try:
            self.__dc_client.publish(
                topic=mgw_dc.com.gen_event_topic(self.__device.id, self.__device.model.push_state_srv[0]),
                payload=json.dumps(self.__device.model.push_state_srv[1](self.device_state)),
                qos=1
            )
        except Exception as ex:
            logger.error("{}: can't publish state - {}".format(self.name, ex))

    def __handle_sensor_data(self, data: dict):
        try:
            self.__dc_client.publish(
                topic=mgw_dc.com.gen_event_topic(self.__device.id, self.__device.model.push_readings_srv[0]),
                payload=json.dumps(self.__device.model.push_readings_srv[1](data)),
                qos=1
            )
        except Exception as ex:
            logger.error("{}: can't publish readings - {}".format(self.name, ex))

    def __on_message(self, client, userdata, message: paho.mqtt.client.MQTTMessage):
        try:
            logger.debug("{}: got message '{}'".format(self.name, message.payload.decode()))
            payload = json.loads(message.payload)
            if payload[self.__device.model.msg_type_field] in self.__device.model.device_state_msg_types:
                self.__handle_state_data(payload)
            elif payload[self.__device.model.msg_type_field] in self.__device.model.sensor_data_msg_types:
                self.__handle_sensor_data(payload)
            else:
                logger.warning("{}: message type '{}' not supported".format(self.name, payload[self.__device.model.msg_type_field]))
        except Exception as ex:
            logger.error("{}: parsing message failed - {}".format(self.name, ex))

    def __on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("{}: connected".format(self.name))
            try:
                self.__device.state = mgw_dc.dm.device_state.online
                self.__dc_client.publish(
                    topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                    payload=json.dumps(mgw_dc.dm.gen_set_device_msg(self.__device)),
                    qos=1
                )
                self.__dc_client.subscribe(topic=mgw_dc.com.gen_command_topic(self.__device.id), qos=1)
            except Exception as ex:
                logger.error("{}: setting state failed - {}".format(self.name, ex))
            try:
                self.__session_client.subscribe(topic=self.__device.model.state_topic.format(self.__serial))
                self.__session_client.publish(
                    topic=self.__device.model.command_topic.format(self.__serial),
                    payload=json.dumps(self.__device.model.gen_state_req_msg()),
                    qos=1
                )
                if self.__sensor_trigger and not self.__sensor_trigger.is_alive():
                    self.__sensor_trigger.start()
                if not self.__command_handler.is_alive():
                    self.__command_handler.start()
                self.__disconnect_count = 0
            except Exception as ex:
                logger.error("{}: handling connect failed - {}".format(self.name, ex))
                self.__session_client.disconnect()
        else:
            logger.error("{}: could not connect - {}".format(self.name, paho.mqtt.client.connack_string(rc)))

    def __on_disconnect(self, client, userdata, rc):
        if rc == 0:
            logger.info("{}: disconnected".format(self.name))
        else:
            logger.warning("{}: disconnected unexpectedly".format(self.name))
        if self.__disconnect_count > conf.Session.max_disconnects:
            self.__session_client.disconnect()
        else:
            try:
                self.__device.state = mgw_dc.dm.device_state.offline
                self.__dc_client.publish(
                    topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                    payload=json.dumps(mgw_dc.dm.gen_set_device_msg(self.__device)),
                    qos=1
                )
                self.__dc_client.unsubscribe(topic=mgw_dc.com.gen_command_topic(self.__device.id))
            except Exception as ex:
                logger.warning("{}: setting state failed - {}".format(self.name, ex))
        self.__disconnect_count += 1
