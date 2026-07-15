# simple_config

`simple_config` turns YAML files into ready-to-use Python config objects. Define shared settings once in `base.yaml`, override them per environment (`development.yaml`, `production.yaml`, …), and switch environments with a single environment variable.

**At a glance:**

- **Layered configs** — `base.yaml` plus one file per mode, deep-merged
- **One-variable mode switching** — `<PROJECT_NAME>_MODE=production`
- **Natural access** — `config.databases.replica.host`, `config.databases['replica']`, or a mix
- **String interpolation** — `'{config.project_dir}/logs'` inside YAML values
- **Smart values** — automatic path normalization (`*_dir` keys), datetime parsing (`*_datetime` keys), and AWS Secrets Manager lookups (`.SECRET` keys)
- **Per-user local overrides** in `~/.simple_config/` — personal settings that never touch the repository
- Bundled **logging setup** (`init_logger`) and **singleton** helpers

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Project structure](#project-structure)
- [Modes](#modes)
- [How files are merged](#how-files-are-merged)
- [Accessing values](#accessing-values)
- [Value transforms](#value-transforms)
- [Per-user local overrides](#per-user-local-overrides)
- [Validating every mode](#validating-every-mode)
- [Logging helper](#logging-helper)
- [API quick reference](#api-quick-reference)
- [Example projects](#example-projects)
- [License](#license)

## Installation

From a clone of this repository:

```sh
pip install .
```

Requires Python 3.9+. Dependencies (installed automatically): PyYAML, python-dateutil, boto3.

## Quick start

Lay out your project like this (see [Project structure](#project-structure) for the rules and an alternate layout):

```
my_project/                  <- repository root
├─ app/
│  ├─ config/
│  │  ├─ base.yaml           <- shared defaults (optional, recommended)
│  │  ├─ development.yaml    <- one file per mode
│  │  ├─ production.yaml
│  │  ├─ test.yaml
│  ├─ my_project/
│  │  ├─ __init__.py
│  │  ├─ environment.py      <- creates and loads the config (below)
│  │  ├─ main.py
```

**1. Write your config files.** `base.yaml` holds what every mode shares; each mode file overrides or adds what's different:

```yaml
# app/config/base.yaml
logging:
    logger_type: 'stdout'
    logger_options:
        name: 'my_project'
        base_level: 'INFO'
        line_format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

databases:
    replica:
        host: 'localhost'
        port: 3306
```

```yaml
# app/config/production.yaml
logging:
    logger_type: 'local_file'
    logger_options:
        directory: '{config.project_dir}/shared/log'
        file_name: '{config.process_name}.log'

databases:
    replica:
        host: 'replica.internal.example.com'
```

Mode files can be empty to start — an empty `development.yaml` simply means "use `base.yaml` as-is".

**2. Create the config once, in an `environment.py`:**

```python
# app/my_project/environment.py
import pathlib

from simple_config import YamlConfig
from simple_config.singleton import Singleton
from simple_config.logging_tools import init_logger

MODULE_DIR = pathlib.Path(__file__).parent      # app/my_project/
APP_ROOT = MODULE_DIR.parent                    # app/
PROJECT_ROOT = APP_ROOT.parent                  # repository root


class Env(metaclass=Singleton):
    PROJECT_NAME = "my_project"

    def __init__(self):
        self.config = YamlConfig(self.PROJECT_NAME)
        self.config.app_dir = APP_ROOT.as_posix()          # parent of config/ — required
        self.config.project_dir = PROJECT_ROOT.as_posix()  # optional, for interpolation
        self.config.load()

        self.logger = init_logger(
            self.config.logging.logger_type,
            self.config.logging.logger_options,
        )
```

**3. Use it anywhere.** Thanks to the `Singleton` metaclass, `Env()` builds the config on first use and returns that same loaded instance everywhere after:

```python
# app/my_project/main.py
from my_project.environment import Env

env = Env()
db = env.config.databases.replica
env.logger.info(f"Connecting to {db.host}:{db.port}")
```

**4. Pick the mode at launch** with the `MY_PROJECT_MODE` environment variable:

```sh
python -m my_project.main                            # development (the default)
MY_PROJECT_MODE=production python -m my_project.main
```

That's the whole loop: YAML files in `config/`, one environment variable, one loaded object.

## Project structure

`simple_config` reads `*.yaml` files from `<app_dir>/config/`. You tell it where `app_dir` is, so any layout works — including both of these (working copies of each are in the project files under `test/example_projects/`):

| Layout | `config/` location | Directory settings |
|---|---|---|
| **Containerized / k8s-style** (recommended) | `<root>/app/config/` | `app_dir = <root>/app`, `project_dir = <root>` |
| **Legacy / flat** | `<root>/config/` | `app_dir = project_dir = <root>` |

Three directory attributes exist on the config object:

| Attribute | Required? | Meaning |
|---|---|---|
| `config.app_dir` | **Yes, before `load()`** | The directory that contains `config/` |
| `config.project_dir` | Optional | Repository root — handy in `{config.project_dir}` interpolation |
| `config.workspace_dir` | Optional | Any scratch/workspace path you want available in interpolation |

Rules for the `config/` folder:

- Files must use the `.yaml` extension — anything else in the folder is ignored.
- File names must be lowercase (`Test.yaml` raises `ConfigError`).
- At least one non-`base` file must exist; `base.yaml` itself is optional.
- Empty files are fine (they contribute nothing); a non-empty file must be a YAML mapping at the top level.

## Modes

```python
YamlConfig(project_name, default_mode="development", process_name=None)
```

| Parameter | Meaning |
|---|---|
| `project_name` | Your project's name (conventionally the repository name). Lowercased internally; also names the [per-user override folder](#per-user-local-overrides). |
| `default_mode` | Mode used when the environment variable isn't set. Default: `development`. |
| `process_name` | Name of the running process, available as `{config.process_name}`. Default: the current script's filename stem. |

The mode-selecting environment variable is the project name, uppercased with `-` replaced by `_`, plus `_MODE` — for `my-project` that's `MY_PROJECT_MODE` (also available as `config.env_var`).

- The valid modes are exactly the config file stems (minus `base`): create `staging.yaml` and `staging` becomes a valid mode.
- Values are case-insensitive: `MY_PROJECT_MODE=TEST` selects `test`.
- An invalid value raises `EnvironmentError` naming the valid choices.
- The mode is read once, on first use, and stays fixed for the life of the config object.

## How files are merged

`config.load()` reads, in order — later files win:

1. `base.yaml` (if present)
2. `<mode>.yaml`
3. `~/.simple_config/<project_name>/<mode>.yaml` — only with `load(include_user_overrides=True)`

Nested mappings are deep-merged key by key; every other value — strings, numbers, **lists** — is replaced wholesale:

```yaml
# base.yaml            # production.yaml      # loaded result
retries: 3             retries: 5             retries: 5
database:              database:              database:
    host: 'localhost'      host: 'db.internal'    host: 'db.internal'
    port: 5432                                    port: 5432        <- kept from base
tags: ['a', 'b']       tags: ['prod']         tags: ['prod']        <- lists replace, never merge
```

Mode files may also introduce keys that `base.yaml` doesn't have.

## Accessing values

After `load()`, the values live on the config object itself:

```python
config.databases.replica.host             # attribute style
config.databases['replica']['host']       # dict style
config.databases['replica'].host          # mix and match

section = config.databases.replica
section.get('passwd')                     # None if missing
section.get('passwd', 'fallback')         # with a default
'host' in section                         # membership test
section.keys(); section.values(); section.items()
```

The top level is attribute-only (`config.databases`, not `config['databases']`); from there down, every nested section supports both styles plus `get`/`in`/`keys`/`values`/`items`.

Treat the loaded config as read-only — assigning through dict syntax (`config.databases['replica']['host'] = ...`) raises `TypeError`.

## Value transforms

Values are transformed as they load:

| You write | You get |
|---|---|
| `'...{config.mode}...'` in any string | The placeholder interpolated from the config object |
| A key ending in `_dir` | The path with `~` expanded, made absolute, and normalized |
| A key ending in `_datetime` | A `datetime` object (parsed by `dateutil`) |
| A key suffixed `.SECRET` | The value fetched from AWS Secrets Manager |

### String interpolation

Every string value — at any nesting depth, including inside lists — is formatted with `config` bound, so `{config.<field>}` placeholders resolve to:

| Placeholder | Value |
|---|---|
| `{config.mode}` | The active mode, e.g. `production` |
| `{config.project_name}` | The (lowercased) project name |
| `{config.process_name}` | The script name, or the `process_name` you passed |
| `{config.project_dir}`, `{config.app_dir}`, `{config.workspace_dir}` | The directories you set |
| `{config.<anything>}` | Any attribute you set on the config object before `load()` |

```yaml
paths:
    log_dir: '{config.project_dir}/logs/{config.mode}'
```

To include a literal brace in a string, double it: `'{{'` and `'}}'`.

### `_dir` and `_datetime` keys

```yaml
cache_dir: '~/caches/{config.project_name}'   # -> /home/you/caches/my_project
launch_datetime: '2026-07-04 12:00'           # -> datetime.datetime(2026, 7, 4, 12, 0)
```

Relative `_dir` paths resolve against the current working directory.

### `.SECRET` — AWS Secrets Manager

Use secrets without writing them down. The value is fetched at load time and only ever held in memory:

```yaml
jwt:
    jwt_key.SECRET: 'my-app-staging-secrets/jwt'
```

The value format is `<secret_name>/<json_key>`: the named secret's string is parsed as JSON and the key is extracted. The `.SECRET` suffix is stripped, so the result above is a plain `config.jwt.jwt_key`.

- Uses your standard boto3/AWS credentials; secrets are read from the `us-east-1` region.
- Each secret is fetched once per process, then cached.
- Any other `.SUFFIX` on a key prints a warning and yields `None`.

## Per-user local overrides

For values personal to one developer or machine, `simple_config` can merge one extra file from outside the repository, last in the chain: `~/.simple_config/<project_name>/<mode>.yaml`. It's opt-in per load:

```python
config.load(include_user_overrides=True)
```

If the folder or file doesn't exist, loading proceeds normally. A typical use — point development at your own database without editing project files:

```yaml
# ~/.simple_config/my_project/development.yaml
databases:
    replica:
        host: 'my-sandbox-db.local'
```

For a personal scratch mode, commit an **empty** `ad_hoc.yaml` to `config/` (making `ad_hoc` a valid mode), keep the real values in `~/.simple_config/my_project/ad_hoc.yaml`, and run:

```sh
MY_PROJECT_MODE=ad_hoc python -m my_project.main
```

## Validating every mode

Catch a broken `production.yaml` in your test suite, not at deploy time. These load every mode on throwaway copies, without touching your loaded config:

```python
config.load_all_configs()                    # raises the first failure it finds
errors = config.try_loading_all_configs()    # or: {mode: exception}, empty if all good
```

## Logging helper

`init_logger(logger_type, logger_options)` builds a standard `logging` logger from config — pass it the config section, as in the [quick start](#quick-start):

```python
logger = init_logger(config.logging.logger_type, config.logging.logger_options)
```

| `logger_type` | Writes to | Required `logger_options` |
|---|---|---|
| `'stdout'` | Console | `name`, `base_level`, `line_format` |
| `'local_file'` | Log file + console | the above, plus `directory`, `file_name` |

With `local_file`, the log directory is created if missing, everything at `base_level` and up goes to the file, `DEBUG`/`INFO` echo to stdout, and `WARNING` and up echo to stderr.

## API quick reference

```python
from simple_config import YamlConfig                     # the main class
from simple_config.logging_tools import init_logger      # config-driven logger setup
from simple_config.singleton import Singleton            # metaclass for a shared Env
from simple_config.error_types import ConfigError        # raised for config-file problems
```

| `YamlConfig` member | What it does |
|---|---|
| `YamlConfig(project_name, default_mode='development', process_name=None)` | Create an unloaded config |
| `.app_dir` | **Set before loading** — the directory that contains `config/` |
| `.project_dir`, `.workspace_dir` | Optional directories, available to interpolation |
| `.load(include_user_overrides=False)` | Read, merge, and transform the active mode's files onto the object |
| `.load_all_configs()` | Load every mode on copies; raise the first failure |
| `.try_loading_all_configs()` | As above, but return `{mode: exception}` instead of raising |
| `.mode` | The active mode (fixed after first access) |
| `.valid_modes` | Set of modes that have a config file |
| `.env_var` | Name of the mode-selecting environment variable |
| `.config_dir` | `<app_dir>/config` |
| `.user_override_config_dir` | `~/.simple_config/<project_name>` |
| `.project_name`, `.process_name`, `.default_mode` | As given at construction (normalized) |

Errors you may meet: `ConfigError` (folder/file rules violated), `EnvironmentError` (invalid mode selected), and PyYAML's `ParserError` (malformed YAML).

## Example projects

Complete working layouts live in the project files: [`test/example_projects/`](test/example_projects) has one containerized-style and one legacy-style project, and [`test/example_user_home_dirs/`](test/example_user_home_dirs) shows the per-user override folder structure.

# License

Licensed under the [Apache License 2.0](LICENSE.txt).
