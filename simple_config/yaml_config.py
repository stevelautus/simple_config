import copy
import os
import sys
import io
import pathlib
import collections.abc
from contextlib import contextmanager
import yaml

from simple_config.lazy_property import lazy_property
from simple_config.yaml_config_part import YamlConfigPart
from simple_config.error_types import ConfigError


def recursive_update(original, changes):
    for key, value in changes.items():
        if isinstance(value, collections.abc.Mapping):
            nested_mapping = recursive_update(original.get(key, {}), value)
            original[key] = nested_mapping
        else:
            original[key] = changes[key]
    return original
    

class YamlConfig(object):
    _DEFAULT_MODE = 'development'
    _CONFIG_EXT = 'yaml'
    _LOCAL_USER_OVERRIDE_MODE_PREFIX = "userlocal_"
    _LOCAL_USER_OVERRIDE_FOLDER_NAME = ".simple_config"

    def __init__(self, project_name, default_mode=_DEFAULT_MODE, process_name=None):
        """
        :param project_name: name of your project, will be lowercased
        :param default_mode: mode your project should default to when environment var is not set
        :param process_name: name of the current process e.g. "event_watcher"
        """
        self.project_name = project_name.lower()
        self.default_mode = default_mode.lower()

        self.process_name = self._process_name(process_name)

        self._project_dir = None
        self._app_dir = None
        self._workspace_dir = None

        self.env_var = '{0}_MODE'.format(self.project_name.upper().replace("-","_"))

    @classmethod
    def _argv_name(self):
        return sys.argv[0]

    def _process_name(self, process_name):
        if process_name is not None:
            return process_name

        argv_name = self._argv_name()
        if argv_name == '':
            return "unnamed_process"

        return pathlib.Path(argv_name).stem

    @lazy_property
    def valid_modes(self):
        modes_w_config_files = set(cf.stem for cf in self.all_config_files)
        modes_w_config_files.discard("base")

        if len(modes_w_config_files) == 0:
            raise ConfigError("Must provide at least one non-base config file")
        
        return modes_w_config_files

    @lazy_property
    def mode(self):
        selected_mode = self._read_env_var().lower()

        if selected_mode not in self.valid_modes:
            raise EnvironmentError("Invalid {0} specified: '{1}'. Valid choices are: {2}".format(self.env_var, selected_mode, self.valid_modes))

        return selected_mode

    @property
    def project_dir(self):
        return self._project_dir

    @project_dir.setter
    def project_dir(self, new_val):
        self._project_dir = pathlib.Path(new_val)

    @property
    def app_dir(self):
        return self._app_dir

    @app_dir.setter
    def app_dir(self, new_val):
        self._app_dir = pathlib.Path(new_val)

    @property
    def workspace_dir(self):
        return self._workspace_dir

    @workspace_dir.setter
    def workspace_dir(self, new_val):
        self._workspace_dir = pathlib.Path(new_val)

    @property
    def config_dir(self):
        assert self.app_dir is not None, "You must set app_dir before a valid config_dir can be returned!"
        return self.app_dir.joinpath("config")

    @lazy_property
    def user_override_config_dir(self):
        return pathlib.Path.home().joinpath(self._LOCAL_USER_OVERRIDE_FOLDER_NAME, self.project_name)

    @lazy_property
    def raw_project_config_files(self):
        return set(cf_path for cf_path in self.config_dir.glob(f"*.{self._CONFIG_EXT}") if cf_path.is_file())

    @lazy_property
    def raw_user_override_config_files(self):
        return set(cf_path for cf_path in self.user_override_config_dir.glob(f"*.{self._CONFIG_EXT}") if cf_path.is_file())

    @property
    def all_raw_config_files(self):
        return self.raw_project_config_files | self.raw_user_override_config_files

    @property
    def all_config_files(self):
        config_file_paths = set()
        file_names_w_upper_case = set()

        for config_file_path in self.all_raw_config_files:
            config_file_paths.add(config_file_path)

            if config_file_path.stem.lower() != config_file_path.stem:
                file_names_w_upper_case.add(config_file_path)
        
        if file_names_w_upper_case:
            raise ConfigError(
                "All config file names must be lowercase. (Offending files were: {0})".format(
                    file_names_w_upper_case
                )
            )

        return config_file_paths    

    def _has_base_config(self):
        file_name = f"base.{self._CONFIG_EXT}"
        return self.config_dir.joinpath(file_name).exists()

    def _configs_to_load(self, include_user_overrides):
        configs = [self.mode]
        if self._has_base_config():
            configs.insert(0, "base")
        if include_user_overrides and self.user_override_config_dir.exists():
            configs.append(self._LOCAL_USER_OVERRIDE_MODE_PREFIX + self.mode)
        return configs

    def load(self, include_user_overrides=False):
        top_level_parts = self._load_configs_with_inheritance(*self._configs_to_load(include_user_overrides))
        self.__dict__.update(top_level_parts.__dict__)

    def try_loading_all_configs(self):
        exceptions = {}
        for mode in self.valid_modes:
            config = copy.deepcopy(self)
            if hasattr(config, "_lazy_mode"): del config._lazy_mode
            config._read_env_var = lambda: mode
            try:
                config.load()
            except Exception as e:
                exceptions[mode] = e
        return exceptions

    def load_all_configs(self):
        exceptions = self.try_loading_all_configs()
        if len(exceptions.values()) > 0:
            raise list(exceptions.values())[0]

    def _read_env_var(self):
        return os.environ.get(self.env_var, self.default_mode)

    def _load_configs_with_inheritance(self, *modes):
        config_dict = {}
        for mode in modes:
            with self._open_config_file(mode) as config_file_stream:
                current_file_dict = yaml.load(config_file_stream, Loader=yaml.Loader)
                if isinstance(current_file_dict, dict):
                    recursive_update(config_dict, current_file_dict)
                elif current_file_dict is not None:  # None when file is empty - skip empty files
                    raise ConfigError("{0} config not a dict (was {1})".format(mode, repr(current_file_dict)))

        return YamlConfigPart(config_dict, interp_dict={"config": self})

    @contextmanager
    def _open_config_file(self, mode):
        if mode.startswith(self._LOCAL_USER_OVERRIDE_MODE_PREFIX):
            tgt_config_dir = self.user_override_config_dir
            mode = mode.replace(self._LOCAL_USER_OVERRIDE_MODE_PREFIX, "")
            file_name = f"{mode}.{self._CONFIG_EXT}"
            file_path = tgt_config_dir.joinpath(file_name)

            if not file_path.exists():
                with io.StringIO("") as f:
                    yield f
            else:
                with open(file_path, "rb") as f:
                    yield f
        else:
            tgt_config_dir = self.config_dir
            file_name = f"{mode}.{self._CONFIG_EXT}"
            file_path = tgt_config_dir.joinpath(file_name)
        
            with open(file_path, "rb") as f:
                yield f
