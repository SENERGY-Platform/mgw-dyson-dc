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


__all__ = ("Device", )


from util import conf
import mgw_dc


class Device(mgw_dc.dm.Device):
    __type_map = {
        "475": conf.Senergy.dt_pure_cool_link,
    }

    def __init__(self, id: str, model: str, name: str, ip_address: str, pw: str):
        super().__init__(id=id, name=name, type=Device.__type_map[model])
        self.ip_address = ip_address
        self.pw = pw

    def __iter__(self):
        items = (
            ("name", self.name),
            ("ip_address", self.ip_address)
        )
        for item in items:
            yield item