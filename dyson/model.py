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
import typing


class Model:
    def __init__(self, id: str, type: str, services: dict, push_dev_ste_srv: typing.Optional[typing.Callable[[dict], typing.Any]] = None, push_sen_rdg_srv: typing.Optional[typing.Callable[[dict], typing.Any]] = None):
        self.id = id
        self.type = type
        self.services = services
        self.push_dev_ste_srv = push_dev_ste_srv
        self.push_sen_rdg_srv = push_sen_rdg_srv


pure_cool_link = Model(
    id="475",
    type=conf.Senergy.dt_pure_cool_link,
    services={
        "setPower": None,
        "setOscillation": None,
        "setSpeed": None,
        "setMonitoring": None,
        "getDeviceState": None
    },
    push_dev_ste_srv=None,
    push_sen_rdg_srv=None
)

model_map = {
    pure_cool_link.id: pure_cool_link
}
