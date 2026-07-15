import pathlib, sys

PRIMARY_MODULE_DIR = pathlib.Path(__file__).parent
APP_ROOT = PRIMARY_MODULE_DIR.parent
PROJ_ROOT = APP_ROOT.parent

import datetime
import getpass
import socket

from simple_config import YamlConfig
from simple_config.singleton import Singleton
from simple_config.logging_tools import init_logger


def ensure_directory_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


# class Env (object):
#     __metaclass__ = Singleton

#     PROJECT_NAME = "k8s_example_project"

#     def __init__ (self):
#         self.process_name = os.path.splitext (os.path.basename (sys.argv [0]))[0] #in this case it's enviroment
#         self.host_name = socket.gethostname()
#         self.script_start = datetime.datetime.now()
#         self.script_start_ts = self.script_start.strftime("%Y-%m-%d--%H-%M-%S")

#         self.config = YamlConfig(self.PROJECT_NAME, process_name = self.process_name)
#         self.config.project_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
#         self.config.load()

#         ensure_directory_exists(self.config.logging.directory)

#         logging.basicConfig(
#             filename=os.path.join(self.config.logging.directory, self.config.logging.file_name),
#             level=getattr(logging, self.config.logging.level.upper()),
#             format=self.config.logging.format
#         )
#         self.logger = get_logger(self.config.mode)

class Env(metaclass=Singleton):
    PROJECT_NAME = PRIMARY_MODULE_DIR.name

    logger = None
    config = None

    def __init__(self):
        self.process_name = pathlib.Path(sys.argv[0]).stem
        self.user_name = getpass.getuser()
        self.host_name = socket.gethostname()
        self.runtime_start = datetime.datetime.now()

        self.config = Config(self.PROJECT_NAME, process_name=self.process_name)
        self.config.app_dir = APP_ROOT.as_posix()
        self.config.project_dir = PROJ_ROOT.as_posix() if (PROJ_ROOT.name == self.PROJECT_NAME) else APP_ROOT.as_posix()
        self.config.load()

        self.logger = init_logger(self.config.logging.logger_type, self.config.logging.logger_options)

