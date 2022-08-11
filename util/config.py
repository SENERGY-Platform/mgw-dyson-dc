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

__all__ = ("conf",)


import simple_env_var


@simple_env_var.configuration
class Conf:

    @simple_env_var.section
    class MsgBroker:
        host = "message-broker"
        port = 1883

    @simple_env_var.section
    class Logger:
        level = "info"
        enable_mqtt = False

    @simple_env_var.section
    class Client:
        clean_session = False
        keep_alive = 10
        id = "dyson-dc"

    @simple_env_var.section
    class Discovery:
        cloud_url = "https://appapi.cp.dyson.com"
        cloud_auth_api = "v1/userregistration/authenticate"
        cloud_provisioning_api = "v1/provisioningservice/manifest"
        cloud_delay = 600
        grace_period = 86400
        db_path = "/opt/storage"
        device_id_prefix = None
        delay = 240
        ports = "1883;8883"
        probe_timeout = 2
        ip_file = "/opt/host_ip"
        device_wifi_ssid = None
        device_wifi_password = None
        device_name = None

    @simple_env_var.section
    class Account:
        email = None
        pw = None
        country = None

    @simple_env_var.section
    class Session:
        sensor_interval = 10
        keepalive = 5
        logging = False
        max_disconnects = 10

    @simple_env_var.section
    class StartDelay:
        enabled = False
        min = 5
        max = 20

    @simple_env_var.section
    class Senergy:
        dt_pure_cool_link = None


conf = Conf()


if not conf.Senergy.dt_pure_cool_link:
    exit('Please provide a SENERGY device types')
