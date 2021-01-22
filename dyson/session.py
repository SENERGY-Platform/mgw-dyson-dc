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
        credentials = json.loads(decrypt_password(device.local_credentials))
        self.__serial = credentials["serial"]
        self.__session_client.username_pw_set(username=credentials["serial"], password=credentials["apPasswordHash"])
        if conf.Session.logging:
            self.__session_client.enable_logger(logger.getChild("{}-mqtt".format(self.name)))
        self.__stop = False
        self.__sensor_trigger = threading.Thread(
            target=self.__trigger_sensor_data,
            name="{}-sensor-trigger".format(self.name),
            daemon=True
        )
        self.device_state: typing.Optional[dict] = None
        self.trigger_sensor_data = False

    def run(self):
        logger.info("starting {} ...".format(self.name))
        try:
            self.__session_client.connect(self.__ip, self.__port, keepalive=conf.Session.keepalive)
            self.__session_client.loop_forever()
        except Exception as ex:
            logger.error(
                "could not connect to '{}' at '{}' on '{}' - {}".format(
                    self.__device.id,
                    self.__ip,
                    self.__port,
                    ex
                )
            )
        logger.info("{} exited".format(self.name))

    def __trigger_device_state(self):
        self.__session_client.publish(
            '{}/{}/command'.format(self.__device.model.id, self.__serial),
            json.dumps(self.__device.model.gen_state_req_msg()),
            1
        )

    def __trigger_sensor_data(self):
        logger.debug("starting {} ...".format(self.__sensor_trigger.name))
        while True:
            if self.__session_client.is_connected() and self.trigger_sensor_data:
                logger.debug("triggering sensor data for '{}'".format(self.__device.id))
                self.__session_client.publish(
                    '{}/{}/command'.format(self.__device.model.id, self.__serial),
                    json.dumps(self.__device.model.gen_sensor_data_req_msg())
                )
            if self.__stop:
                break
            time.sleep(conf.Session.sensor_interval)
        logger.debug("{} exited".format(self.__sensor_trigger.name))

    def __handle_state_data(self, data: dict):
        logger.debug("{}: got state data".format(self.name))
        self.device_state = data
        try:
            self.__dc_client.publish(
                topic=mgw_dc.com.gen_event_topic(self.__device.id, self.__device.model.push_state_srv[0]),
                payload=json.dumps(self.__device.model.push_state_srv[1](data)),
                qos=1
            )
        except Exception as ex:
            logger.error("{}: can't publish state - {}".format(self.name, ex))

    def __handle_sensor_data(self, data: dict):
        logger.debug("{}: got sensor data".format(self.name))
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
                self.__dc_client.publish(
                    topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                    payload=json.dumps(mgw_dc.dm.gen_set_device_msg(self.__device)),
                    qos=1
                )
            except Exception as ex:
                logger.warning("can't update state of '{}' - {}".format(self.__device.id, ex))
            if not self.__sensor_trigger.is_alive():
                self.__sensor_trigger.start()
        else:
            logger.error("{}: could not connect - {}".format(self.name, paho.mqtt.client.connack_string(rc)))

    def __on_disconnect(self, client, userdata, rc):
        if rc == 0:
            logger.info("{}: disconnected".format(self.name))
        else:
            logger.warning("disconnected from '{}' unexpectedly".format(self.__device.id))
        self.__device.state = mgw_dc.dm.device_state.offline
        try:
            self.__dc_client.publish(
                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                payload=json.dumps(mgw_dc.dm.gen_set_device_msg(self.__device)),
                qos=1
            )
        except Exception as ex:
            logger.warning("can't update state of '{}' - {}".format(self.__device.id, ex))
