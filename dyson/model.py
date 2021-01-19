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


__all__ = ("Model", "model_map")


from util import conf
from . import service
import typing


class Model:
    def __init__(
            self,
            id: str,
            type: str,
            msg_type_field: str,
            device_state_msg_types: tuple,
            services: dict,
            gen_state_req_msg: typing.Callable,
            gen_sensor_data_req_msg: typing.Optional[typing.Callable] = None,
            sensor_data_msg_types: typing.Optional[tuple] = tuple(),
            push_state_srv: typing.Optional[typing.Tuple[str, typing.Callable]] = None,
            push_readings_srv: typing.Optional[typing.Tuple[str, typing.Callable]] = None
    ):
        self.id = id
        self.type = type
        self.msg_type_field = msg_type_field
        self.services = services
        self.gen_state_req_msg = gen_state_req_msg
        self.gen_sensor_data_req_msg = gen_sensor_data_req_msg
        self.device_state_msg_types = device_state_msg_types
        self.sensor_data_msg_types = sensor_data_msg_types
        self.push_state_srv = push_state_srv
        self.push_readings_srv = push_readings_srv


pure_cool_link = Model(
    id="475",
    type=conf.Senergy.dt_pure_cool_link,
    msg_type_field="msg",
    services={
        "setPower": service.pcl_475.set_power,
        "getPower": service.pcl_475.get_power,
        "setOscillation": service.pcl_475.set_oscillation,
        "getOscillation": service.pcl_475.get_oscillation,
        "setSpeed": service.pcl_475.set_speed,
        "getSpeed": service.pcl_475.get_speed,
        "setMonitoring": service.pcl_475.set_monitoring,
        "getMonitoring": service.pcl_475.get_monitoring,
        "getFilterLife": service.pcl_475.get_filter_life
    },
    gen_state_req_msg=service.pcl_475.gen_device_state_req_msg,
    gen_sensor_data_req_msg=service.pcl_475.gen_sensor_data_req_msg,
    device_state_msg_types=("CURRENT-STATE", "STATE-CHANGE"),
    sensor_data_msg_types=("ENVIRONMENTAL-CURRENT-SENSOR-DATA", ),
    push_state_srv=("getDeviceState", service.pcl_475.push_device_state),
    push_readings_srv=("getSensorReadings", service.pcl_475.push_sensor_readings)
)

model_map = {
    pure_cool_link.id: pure_cool_link
}
