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


__all__ = ("Storage", )


import sqlite3
import typing
import os


class Storage:
    def __init__(self, path: str, name: str, tables: typing.Iterable):
        self.__db_path = os.path.join(path, "{}.sqlite3".format(name))
        try:
            with sqlite3.connect(self.__db_path) as conn:
                for table in tables:
                    conn.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(table[0], ", ".join(table[1])))
        except Exception as ex:
            raise RuntimeError("initializing database failed - {}".format(ex))

    def create(self, table: str, data: dict):
        fields = list()
        values = list()
        for field, value in data.items():
            fields.append(field)
            values.append(value)
        with sqlite3.connect(self.__db_path) as conn:
            conn.execute(
                "INSERT INTO {} ({}) VALUES ({})".format(table, ", ".join(fields), ", ".join(["?"] * len(fields))),
                values
            )

    def read(self, table: str, **kwargs):
        statement = [
            "SELECT * FROM {}".format(table)
        ]
        if kwargs:
            fields = list()
            statement.append(list())
            for field, value in kwargs.items():
                fields.append("{}=(?)".format(field))
                statement[1].append(value)
            statement[0] += " WHERE {}".format(" AND ".join(fields))
        with sqlite3.connect(self.__db_path) as conn:
            cursor = conn.execute(*statement)
            for item in cursor:
                print(item)

    def update(self, table: str, data: dict, **kwargs):
        d_fields = list()
        values = list()
        for field, value in data.items():
            d_fields.append("{}=(?)".format(field))
            values.append(value)
        f_fields = list()
        for field, value in kwargs.items():
            f_fields.append("{}=(?)".format(field))
            values.append(value)
        with sqlite3.connect(self.__db_path) as conn:
            conn.execute(
                "UPDATE {} SET {} WHERE {}".format(table, ", ".join(d_fields), " AND ".join(f_fields)),
                values
            )

    def delete(self, table: str, **kwargs):
        fields = list()
        values = list()
        for field, value in kwargs.items():
            fields.append("{}=(?)".format(field))
            values.append(value)
        with sqlite3.connect(self.__db_path) as conn:
            conn.execute(
                "DELETE FROM {} WHERE {}".format(table, " AND ".join(fields)),
                values
            )
