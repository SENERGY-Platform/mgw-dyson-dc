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


from ..session import Session
import datetime
import time


_value_map = {
    "FAN": True,
    "AUTO": True,
    "ON": True,
    "OFF": False,
}


def _parse_device_state(data: dict) -> dict:
    return {
        "power": _value_map[data["product-state"]["fmod"]],
        "oscillation": _value_map[data["product-state"]["oson"]],
        "speed": 0 if data["product-state"]["fnsp"] == "AUTO" else int(data["product-state"]["fnsp"]),
        "monitoring": _value_map[data["product-state"]["rhtm"]],
        "filter_life": round(int(data["product-state"]["filf"]) / 4300 * 100, 2)
    }


def _gen_msg(msg: str) -> dict:
    return {
        "msg": msg,
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


def _gen_set_state_msg(data: dict) -> dict:
    odd_keys = ['filf', 'fnst', 'ercd', 'wacd']
    for key in odd_keys:
        try:
            del data[key]
        except KeyError:
            pass
    data.update({'sltm': 'STET', 'rstf': 'STET'})
    msg = _gen_msg("STATE-SET")
    msg["mode-reason"] = "LAPP"
    msg["data"] = data
    return msg


def gen_device_state_req_msg():
    return _gen_msg("REQUEST-CURRENT-STATE")


def gen_sensor_data_req_msg():
    return _gen_msg("REQUEST-PRODUCT-ENVIRONMENT-CURRENT-SENSOR-DATA")


def push_device_state(data: dict) -> dict:
    state = _parse_device_state(data)
    state["time"] = "{}Z".format(datetime.datetime.utcnow().isoformat())
    return state


def push_sensor_readings(data: dict) -> dict:
    if all(val not in ("OFF", "INIT") for val in data["data"].values()):
        return {
            "temperature": int(data["data"]["tact"]) / 10,
            "humidity": int(data["data"]["hact"]),
            "particles": int(data["data"]["pact"]),
            "volatile_components": int(data["data"]["vact"]),
            "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
        }
    raise RuntimeError("sensors not ready")


def set_power(session: Session, power: bool):
    state = session.device_state.copy()
    if power:
        state["fmod"] = "FAN"
    else:
        state["fmod"] = "OFF"
    return _gen_set_state_msg(state)


def get_power(session: Session) -> dict:
    state = session.device_state
    return {
        "power": _value_map[state["product-state"]["fmod"]],
        "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
    }


def set_oscillation(session: Session, oscillation: bool):
    state = session.device_state.copy()
    if oscillation:
        state["oson"] = "ON"
    else:
        state["oson"] = "OFF"
    return _gen_set_state_msg(state)


def get_oscillation(session: Session) -> dict:
    state = session.device_state
    return {
        "oscillation": _value_map[state["product-state"]["oson"]],
        "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
    }


def set_speed(session: Session, speed: int):
    state = session.device_state.copy()
    state["fnsp"] = "{:04d}".format(speed)
    return _gen_set_state_msg(state)


def get_speed(session: Session) -> dict:
    state = session.device_state
    return {
        "speed": 0 if state["product-state"]["fnsp"] == "AUTO" else int(state["product-state"]["fnsp"]),
        "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
    }


def set_monitoring(session: Session, monitoring: bool):
    state = session.device_state.copy()
    if monitoring:
        state["rhtm"] = "ON"
    else:
        state["rhtm"] = "OFF"
    session.trigger_sensor_data = monitoring
    return _gen_set_state_msg(state)


def get_monitoring(session: Session) -> dict:
    state = session.device_state
    return {
        "monitoring": _value_map[state["product-state"]["rhtm"]],
        "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
    }


def get_filter_life(session: Session) -> dict:
    state = session.device_state
    return {
        "filter_life": round(int(state["product-state"]["filf"]) / 4300 * 100, 2),
        "time": "{}Z".format(datetime.datetime.utcnow().isoformat())
    }
