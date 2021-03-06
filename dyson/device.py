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


from .model import Model, model_map
import mgw_dc


class Device(mgw_dc.dm.Device):
    def __init__(self, id: str, model: str, name: str, local_credentials: str):
        self.model: Model = model_map[model]
        self.local_credentials = local_credentials
        super().__init__(id=id, name=name, type=self.model.type, state=mgw_dc.dm.device_state.offline)
