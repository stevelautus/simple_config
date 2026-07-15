import os, pathlib

THIS_FILE_PATH = pathlib.Path(__file__)
TEST_DIR = THIS_FILE_PATH.parent
PROJECT_ROOT = TEST_DIR.parent
EXAMPLE_PROJECTS_DIR = TEST_DIR.joinpath("example_projects")
EXAMPLE_USER_HOME_DIRS_ROOT = TEST_DIR.joinpath("example_user_home_dirs")

import unittest
import mock

from contextlib import contextmanager
from yaml.parser import ParserError

from simple_config import YamlConfig
from simple_config.error_types import ConfigError
from simple_config.lazy_property import force_lazy_prop_value


############    UTILITY METHODS    ############
def _mock_project_config_dir_contents(config, config_dir_file_names):
    config_dir_file_paths = set(config.config_dir.joinpath(fname) for fname in config_dir_file_names)

    force_lazy_prop_value(config, "raw_project_config_files", config_dir_file_paths)

def _mock_user_override_config_dir(config, example_user_name):
    mock_dir_path = EXAMPLE_USER_HOME_DIRS_ROOT.joinpath(example_user_name, YamlConfig._LOCAL_USER_OVERRIDE_FOLDER_NAME, config.project_name)
    
    print(f"FORCING USER OVERRIDE CONFIG DIR PATH -> '{mock_dir_path}'")

    force_lazy_prop_value(config, "user_override_config_dir", mock_dir_path)

def _get_example_project_config_arg_dicts():
    example_projects = {}

    for project_root_path in EXAMPLE_PROJECTS_DIR.iterdir():
        name = project_root_path.name
        env_var = f"{name.upper()}_MODE"
        top_level_dir_names = set(sub_p.name for sub_p in project_root_path.iterdir() if sub_p.is_dir())
        app_dir_path = project_root_path.joinpath("app") if "app" in top_level_dir_names else project_root_path

        example_projects[project_root_path.name.replace("_example_project", "")] = {
            "name": name,
            "env_var": env_var,
            "project_dir_path": str(project_root_path),
            "app_dir_path": str(app_dir_path),
        }

    return example_projects
###############################################




class TestYamlConfig(unittest.TestCase):
    def setUp(self):

        self.config_args = _get_example_project_config_arg_dicts()

        self.configs = {}
        for example_type, config_args in self.config_args.items():
            if config_args["env_var"] in os.environ:
                del os.environ[config_args["env_var"]]
            ex_config = YamlConfig(config_args["name"])
            ex_config.app_dir = config_args["app_dir_path"]
            ex_config.project_dir = config_args["project_dir_path"]

            self.configs[example_type] = ex_config

    def mock_config(self, mode_files):
        tgt_config_args = self.config_args["legacy"]

        config = YamlConfig(tgt_config_args["name"])
        config.app_dir = tgt_config_args["app_dir_path"]
        config.project_dir = tgt_config_args["project_dir_path"]
        yml_file_names = [f"{mode_name}.{YamlConfig._CONFIG_EXT}" for mode_name in mode_files.keys()]
        _mock_project_config_dir_contents(config, yml_file_names)

        @contextmanager
        def mock_open(mode):
            yield mode_files[mode]
        config._open_config_file = mock_open

        return config

    def mock_and_load(self, mode_files):
        config = self.mock_config(mode_files)
        config.load()
        return config

    def test_project_name(self):
        self.assertEqual(self.configs["legacy"].project_name, "legacy_example_project")
        self.assertEqual(self.configs["k8s"].project_name, "k8s_example_project")

    def test_process_name(self):
        # Pretend that sys.argv[0] != 'nosetests' =)
        YamlConfig._argv_name = mock.MagicMock(return_value="")
        config = YamlConfig("example_project")
        self.assertEqual(config.process_name, "unnamed_process")

        config = YamlConfig("example_project", process_name="cool_process")
        self.assertEqual(config.process_name, "cool_process")

    def test_app_dir(self):
        self.assertTrue(str(self.configs["legacy"].app_dir).endswith("simple_config/test/example_projects/legacy_example_project"))
        self.assertTrue(str(self.configs["k8s"].app_dir).endswith("simple_config/test/example_projects/k8s_example_project/app"))

    def test_project_dir(self):
        self.assertTrue(str(self.configs["legacy"].project_dir).endswith("simple_config/test/example_projects/legacy_example_project"))
        self.assertTrue(str(self.configs["k8s"].project_dir).endswith("simple_config/test/example_projects/k8s_example_project"))

    def test_load_without_project_dir(self):
        config = YamlConfig("wee")
        with self.assertRaises(AssertionError):
            config.load()

        tgt_config_args = self.config_args["legacy"]
        config.app_dir = tgt_config_args["app_dir_path"]
        config.project_dir = tgt_config_args["project_dir_path"]
        config.load() # no raise

    def test_workspace_dir(self):
        tgt_config = self.configs["legacy"]

        self.assertEqual(tgt_config.workspace_dir, None)
        tgt_config.workspace_dir = "/workspace"
        self.assertEqual(str(tgt_config.workspace_dir), "/workspace")

    def test_env_var(self):
        self.assertEqual(self.configs["legacy"].env_var, self.config_args["legacy"]["env_var"])
        self.assertEqual(self.configs["k8s"].env_var, self.config_args["k8s"]["env_var"])

    def test_config_dir(self):
        self.assertEqual(self.configs["legacy"].config_dir, self.configs["legacy"].app_dir.joinpath("config"))
        self.assertEqual(self.configs["k8s"].config_dir, self.configs["k8s"].app_dir.joinpath("config"))

        config = YamlConfig("wee")
        with self.assertRaises(AssertionError):
            config.config_dir # didn't set a project_dir yet

    def test_valid_modes(self):
        _mock_user_override_config_dir(self.configs["legacy"], "user_1")
        self.assertEqual(self.configs["legacy"].valid_modes, set(["development", "test"]))

        _mock_user_override_config_dir(self.configs["k8s"], "user_1")
        self.assertEqual(self.configs["k8s"].valid_modes, set(["development", "test", "production"]))

    def test_valid_modes_upper(self):
        tgt_config = self.configs["legacy"]
        _mock_user_override_config_dir(tgt_config, "user_1")

        _mock_project_config_dir_contents(tgt_config, ["base.yml", "Test.yml"])
        with self.assertRaises(ConfigError):
            tgt_config.valid_modes

        _mock_project_config_dir_contents(tgt_config, ["base.yml", "test.yml"])
        self.assertEqual(tgt_config.valid_modes, set(["test"]))

    def test_bad_mode(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]

        os.environ[tgt_config_args["env_var"]] = "blah"
        with self.assertRaises(EnvironmentError):
            tgt_config.mode

    def test_good_mode(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]

        os.environ[tgt_config_args["env_var"]] = "test"
        self.assertEqual(tgt_config.mode, "test")

    def test_good_mode_upper(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]

        os.environ[tgt_config_args["env_var"]] = "TEST"
        self.assertEqual(tgt_config.mode, "test")

    def test_default_mode(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]

        self.assertEqual(tgt_config.mode, "development")
        lower_default = YamlConfig(tgt_config_args["name"], default_mode="test")
        lower_default.app_dir = tgt_config_args["app_dir_path"]
        lower_default.project_dir = tgt_config_args["project_dir_path"]
        self.assertEqual(lower_default.mode, "test")
        upper_default = YamlConfig(tgt_config_args["name"], default_mode="TEST")
        upper_default.app_dir = tgt_config_args["app_dir_path"]
        upper_default.project_dir = tgt_config_args["project_dir_path"]
        self.assertEqual(upper_default.mode, "test")
        self.assertEqual(upper_default.default_mode, "test")

    def test_mode_laziness(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]

        self.assertEqual(tgt_config.mode, "development")
        os.environ[tgt_config_args["env_var"]] = "test"
        self.assertEqual(tgt_config.mode, "development")

    def test_missing_config(self):
        config = self.mock_config({})
        _mock_user_override_config_dir(config, "user_1")
        with self.assertRaises(ConfigError):
            config.valid_modes
        with self.assertRaises(ConfigError):
            config.load()

    def test_no_non_base_configs(self):
        config = self.mock_config({"base": ""})
        _mock_user_override_config_dir(config, "user_1")
        with self.assertRaises(ConfigError):
            config.valid_modes
        with self.assertRaises(ConfigError):
            config.load()

    def test_all_config_files_wo_user_overrides_dir(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_1"
        tgt_config_dir_path = pathlib.Path(tgt_config_args["app_dir_path"]).joinpath("config")

        expected_config_files = set((
            tgt_config_dir_path.joinpath(f"base.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"development.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"test.{YamlConfig._CONFIG_EXT}"),
        ))

        _mock_user_override_config_dir(tgt_config, tgt_user_name)        

        self.assertEqual(tgt_config.all_config_files, expected_config_files)

    def test_all_config_files_wo_user_overrides_files(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_2"
        tgt_config_dir_path = pathlib.Path(tgt_config_args["app_dir_path"]).joinpath("config")

        expected_config_files = set((
            tgt_config_dir_path.joinpath(f"base.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"development.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"test.{YamlConfig._CONFIG_EXT}"),
        ))

        _mock_user_override_config_dir(tgt_config, tgt_user_name)        

        self.assertEqual(tgt_config.all_config_files, expected_config_files)

    def test_all_config_files_w_user_overrides(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_3"
        tgt_config_dir_path = pathlib.Path(tgt_config_args["app_dir_path"]).joinpath("config")
        tgt_user_override_dir = EXAMPLE_USER_HOME_DIRS_ROOT.joinpath(tgt_user_name, YamlConfig._LOCAL_USER_OVERRIDE_FOLDER_NAME, tgt_config_args["name"])

        expected_config_files = set((
            tgt_config_dir_path.joinpath(f"base.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"development.{YamlConfig._CONFIG_EXT}"),
            tgt_config_dir_path.joinpath(f"test.{YamlConfig._CONFIG_EXT}"),
            tgt_user_override_dir.joinpath(f"development.{YamlConfig._CONFIG_EXT}"),
            tgt_user_override_dir.joinpath(f"production.{YamlConfig._CONFIG_EXT}"),
        ))

        _mock_user_override_config_dir(tgt_config, tgt_user_name)        

        self.assertEqual(tgt_config.all_config_files, expected_config_files)

    def test_include_user_overrides_wo_override_dir(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_1"

        _mock_user_override_config_dir(tgt_config, tgt_user_name)

        tgt_config.load()
        self.assertEqual(tgt_config.databases.replica.host, "replica_host_1")

        tgt_config.load(include_user_overrides=True)
        self.assertEqual(tgt_config.databases.replica.host, "replica_host_1")

    def test_include_user_override_wo_override_file(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_2"

        _mock_user_override_config_dir(tgt_config, tgt_user_name)

        tgt_config.load()
        self.assertEqual(tgt_config.databases.replica.host, "replica_host_1")

        tgt_config.load(include_user_overrides=True)
        self.assertEqual(tgt_config.databases.replica.host, "replica_host_1")

    def test_include_user_override_w_override_file(self):
        tgt_config = self.configs["legacy"]
        tgt_config_args = self.config_args["legacy"]
        tgt_user_name = "user_3"

        _mock_user_override_config_dir(tgt_config, tgt_user_name)

        tgt_config.load()
        self.assertEqual(tgt_config.databases.replica.host, "replica_host_1")

        tgt_config.load(include_user_overrides=True)
        self.assertEqual(tgt_config.databases.replica.host, "overriden_replica_host")

    def test_minimal_config(self):
        # always need a base, and need at least one non-base config
        config = self.mock_and_load({"base": "", "development": ""})

    def test_bad_yaml(self):
        bad_yaml = "{a}: ''''b'"
        with self.assertRaises(ParserError):
            self.mock_and_load({"base": bad_yaml, "development": ""})
        with self.assertRaises(ParserError):
            self.mock_and_load({"base": "", "development": bad_yaml})

    def test_bad_structure(self):
        with self.assertRaises(ConfigError):
            self.mock_and_load({"base": "1", "development": ""})
        with self.assertRaises(ConfigError):
            self.mock_and_load({"base": "", "development": "1"})
        with self.assertRaises(ConfigError):
            self.mock_and_load({"base": "1", "development": "1"})
        with self.assertRaises(ConfigError):
            self.mock_and_load({"base": "[1, 2, 3]", "development": ""})

    def test_inheritance(self):
        config = self.mock_config({"base": "a: 1", "development": ""})
        with self.assertRaises(AttributeError):
            config.a # not loaded yet
        config.load()
        self.assertEqual(config.a, 1)

    def test_override(self):
        config = self.mock_and_load({"base": "a: 1", "development": "a: 2"})
        self.assertEqual(config.a, 2)

    def test_complex_override(self):
        base = """
        a: 1
        b: hello
        c:
            d: 2
            e: [1, 2, 3]
            f:
                g: blah
                h:
                    i: 3
        """
        dev = """
        b: bye
        c:
            e: [4, 5, 6]
            f:
                h:
                    i: 4
        """
        config = self.mock_and_load({"base": base, "development": dev})
        self.assertEqual(config.a, 1)
        self.assertEqual(config.b, "bye")
        self.assertEqual(config.c.d, 2)
        self.assertEqual(config.c.e, [4, 5, 6])
        self.assertEqual(config.c.f.g, "blah")
        self.assertEqual(config.c.f.h.i, 4)

    def test_dictlike_getting(self):
        base = """
        a:
            d: 2
            e: [1, 2, 3]
            f:
                g: blah
                h:
                    i: 3
        """
        config = self.mock_and_load({"base": base, "development": ""})

        self.assertEqual(config.a["d"], 2)
        self.assertEqual(config.a.get("e"), [1, 2, 3])
        self.assertEqual(config.a.get("z"), None)
        self.assertEqual(config.a.get("z", 8), 8)

    def test_dictlike_setting_fails(self):
        base = """
        a:
            d: 2
            e: [1, 2, 3]
            f:
                g: blah
                h:
                    i: 3
        """
        config = self.mock_and_load({"base": base, "development": ""})

        with self.assertRaises(TypeError):
            config.a["d"] = 9

    def test_dictlike_membership_testing(self):
        base = """
        a:
            d: 2
            e: [1, 2, 3]
            f:
                g: blah
                h:
                    i: 3
        """
        config = self.mock_and_load({"base": base, "development": ""})

        self.assertTrue("d" in config.a)
        self.assertFalse("z" in config.a)

    def test_file_choosing(self):
        tgt_config_args = self.config_args["legacy"]

        mode_files = {"base": "", "development": "a: 1", "test": "a: 2"}
        config = self.mock_and_load(mode_files)
        self.assertEqual(config.a, 1)
        os.environ[tgt_config_args["env_var"]] = "test"
        config = self.mock_and_load(mode_files)
        self.assertEqual(config.a, 2)

    def test_string_interpolation(self):
        keys = ["project_name", "workspace_dir", "project_dir", "mode", "some_crazy_new_prop"]
        s = ", ".join(["{config." + k + "}" for k in keys])

        # make sure interpolation is being performed at depth
        base = """
        a:
            b:
                c: "{0}"
                d: ["{0}"]
        """
        config = self.mock_config({"base": base.format(s), "development": ""})

        # kinda dumb... we're just going to set these properties to something "constant"
        config.workspace_dir = "/a"
        config.project_dir = "/b"

        # some_crazy_new_prop isn't defined as part of our API - just making sure string
        # interpolation is in sync with what's defined on config
        config.some_crazy_new_prop = "wahoo!"

        config.load()
        expected_str = "legacy_example_project, /a, /b, development, wahoo!"
        self.assertEqual(config.a.b.c, expected_str)
        self.assertEqual(config.a.b.d[0], expected_str)

    def test_try_loading_all_configs(self):
        config = self.mock_config({"base": "", "development": "", "test": ""})
        _mock_user_override_config_dir(config, "user_1")
        exceptions = config.try_loading_all_configs()
        self.assertEqual(len(exceptions), 0)
        config = self.mock_config({"base": "", "development": "", "test": "{a}: ''''b'"})
        _mock_user_override_config_dir(config, "user_1")
        self.assertEqual(config.mode, "development")
        exceptions = config.try_loading_all_configs()
        self.assertEqual(list(exceptions.keys()), ["test"])
        self.assertIsInstance(exceptions["test"], ParserError)

    def test_load_all_configs(self):
        config = self.mock_config({"base": "", "development": "", "test": ""})
        _mock_user_override_config_dir(config, "user_1")
        config.load_all_configs() # no exception
        config = self.mock_config({"base": "", "development": "", "test": "{a}: ''''b'"})
        _mock_user_override_config_dir(config, "user_1")
        with self.assertRaises(ParserError):
            config.load_all_configs()

    def test_schema_difference(self):
        # TODO: raise exception on unknown keys?
        base = """
        a: 1
        b: 2
        c:
            d: 3
            e: 4
        """
        dev = """
        x: 1
        b: 7
        c:
            d: 8
            f: 9
        """
        config = self.mock_and_load({"base": base, "development": dev})
        self.assertEqual(config.a, 1)
        self.assertEqual(config.x, 1)
        self.assertEqual(config.b, 7)
        self.assertEqual(config.c.d, 8)
        self.assertEqual(config.c.e, 4)
        self.assertEqual(config.c.f, 9)

    def test_type_difference(self):
        # TODO: raise exception when types are different?
        config = self.mock_and_load({"base": "a: 1", "development": "a: '1'"})
        self.assertEqual(config.a, "1")
        config = self.mock_and_load({"base": "a: True", "development": "a: 'True'"})
        self.assertEqual(config.a, "True")
        config = self.mock_and_load({"base": "a: '7'", "development": "a: 7"})
        self.assertEqual(config.a, 7)
        config = self.mock_and_load({"base": "a: [1, 2, 3]", "development": "a: '1, 2, 3'"})
        self.assertEqual(config.a, "1, 2, 3")

    def test_none_values(self):
        # TODO: raise an exception when base has a None value or dev overrides with None?
        config = self.mock_and_load({"base": "a: ", "development": ""})
        self.assertEqual(config.a, None)
        config = self.mock_and_load({"base": "a: 1", "development": "a: "})
        self.assertEqual(config.a, None)
