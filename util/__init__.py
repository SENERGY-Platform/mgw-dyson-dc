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

from .config import *
from .logger import *
from .mqtt import *
from .router import *
from .storage import *
import sys
import random
import time
import Crypto.Cipher.AES
import base64
import typing


__all__ = (
    config.__all__,
    logger.__all__,
    mqtt.__all__,
    router.__all__,
    storage.__all__
)


def handle_sigterm(signo, stack_frame):
    print("\ngot signal '{}' - exiting ...\n".format(signo))
    sys.exit(0)


def delay_start(min: int, max: int):
    delay = random.randint(min, max)
    print("delaying start for {}s".format(delay))
    time.sleep(delay)


def diff(known: dict, unknown: dict):
    known_set = set(known)
    unknown_set = set(unknown)
    missing = known_set - unknown_set
    new = unknown_set - known_set
    intersection = known_set & unknown_set
    return new, missing, intersection


def to_dict(items: typing.Sequence, unique_key: str):
    _dict = dict()
    for item in items:
        _dict[item[unique_key]] = item
        del _dict[item[unique_key]][unique_key]
    return _dict


def unpad(string):
    """
    From: https://github.com/CharlesBlonde/libpurecoollink

    Copyright 2017 Charles Blonde

    Licensed under the Apache License

    Un pad string."""
    return string[:-ord(string[len(string) - 1:])]


def decrypt_password(encrypted_password):
    """
    From: https://github.com/CharlesBlonde/libpurecoollink

    Copyright 2017 Charles Blonde

    Licensed under the Apache License

    Decrypt password.
    :param encrypted_password: Encrypted password
    """
    key = b'\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10' \
          b'\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f '
    init_vector = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                  b'\x00\x00\x00\x00'
    cipher = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CBC, init_vector)
    return unpad(cipher.decrypt(base64.b64decode(encrypted_password)).decode('utf-8'))
