import json
import os
from collections import defaultdict
from functools import cache

from dateutil.parser import parse as parse_dt
import boto3


session = boto3.Session(region_name="us-east-1")
secretsmanager = session.client("secretsmanager")


@cache
def cached_get_secret(secret_name):
    return secretsmanager.get_secret_value(SecretId=secret_name)


class YamlConfigPart(object):
    def _string_transformer(self, name, raw_val, interp_dict):
        formatted_val = raw_val.format(**interp_dict)

        if name.endswith("_dir"):
            formatted_val = os.path.normpath(
                os.path.abspath(os.path.expanduser(formatted_val))
            )
        elif name.endswith("_datetime"):
            formatted_val = parse_dt(formatted_val)

        return formatted_val

    def _sequence_transformer(self, name, raw_val, interp_dict):
        return [self.transform("", sub_val, interp_dict) for sub_val in raw_val]

    def _dict_transformer(self, name, raw_val, interp_dict):
        return self.__class__(raw_val, interp_dict=interp_dict)

    @property
    def transformers(self):
        return defaultdict(
            lambda: lambda name, raw_val, interp_dict: raw_val,
            (
                (str, self._string_transformer),
                (tuple, self._sequence_transformer),
                (list, self._sequence_transformer),
                (set, self._sequence_transformer),
                (dict, self._dict_transformer),
            ),
        )

    def transform(self, name, raw_val, interp_dict):
        if "." in name:
            return self.special_transform(name, raw_val, interp_dict)

        return self.transformers[type(raw_val)](name, raw_val, interp_dict)

    def special_transform(self, name, raw_val, interp_dict):
        """Special transforms are denoted by having a .TRANSFORM on a yaml key."""
        transform_name = name.split(".")[1]
        value_type = type(raw_val)
        supported_transforms = [("SECRET", str)]
        if transform_name == "SECRET" and value_type == str:
            secret_name, secret_key = raw_val.split("/")
            response = cached_get_secret(secret_name)
            return json.loads(response["SecretString"])[secret_key]

        print(
            "WARNING - Simple config doesn't support transform and value type pair of: "
            + f"{transform_name}-{value_type}.\n"
            + f"Supported transform and value type pairs are {supported_transforms}"
        )

    def strip_transform(self, name):
        """Strips out special . suffixes for yaml keys if any"""
        if "." in name:
            return name.split(".")[0]
        return name

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return zip(self.keys(), self.values())

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def __repr__(self):
        return "YamlConfigPart: " + repr(self.__dict__)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __contains__(self, key):
        return key in self.__dict__

    def __init__(self, part_dict, interp_dict={}):
        for name, raw_val in part_dict.items():
            transformed_name = self.strip_transform(name)
            self.__dict__[transformed_name] = self.transform(name, raw_val, interp_dict)
