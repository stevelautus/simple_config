# simple_config
`simple_config` turns YAML configs into python objects. It has support for multi-environment, yaml overrides, local yaml files, and secrets transforms.

`simple_config` works by looking for YAML files in the `app/config` folder. The config object is created by taking `base.yaml` and overwriting it with a yaml file of your choice (like `staging.yaml`). That yaml file is chosen via a specific ENV variable:

`os.environ.get('<PROJECT_NAME>_MODE', default_mode)`


* `<PROJECT_NAME>_MODE` is the env variable. For example if the github repo name is hello_world, then the env var would be `HELLO_WORLD_MODE`
  * The value of the env var is typically `ad_hoc`, `development`, `staging`, or `production` (or anything that matches a corresponding config yaml file in the config folder)
* `default_mode` is `development` unless otherwise specified

The recommended file structure for you application is:

```
app/
├─ config/
│  ├─ base.yaml
│  ├─ development.yaml
│  ├─ staging.yaml
│  ├─ production.yaml
├─ hello_world/
│  ├─ environment.py
│  ├─ main.py
├─ other files and folders...
```

## Using local config files (outside of github)

`simple_config` also will look for local config files outside of the github repo in `~/.simple_config/<REPO_NAME>/`

This is useful for running manual scripts on your local machine.

For example if we have `~/.simple_config/hello_world/ad_hoc.yaml`, then when we run our application:
```sh
HELLO_WORLD_MODE=ad_hoc python -m hello_world.main
```

## Special Transforms

### .SECRET transform
Allows the application to use secrets without writing them in plaintext. `simple_config` will replace transform with the value of an AWS secretsmanager secret at runtime, and only store it in memory.

```
key.SECRET: "<secretsmanager_name>/<secretsmanager_json_key>"
```

For example, let's say we have this config,
```
jwt:
    jwt_key.SECRET: "my-app-staging-secrets/jwt"
```
And our secret in secretsmanager has the name `my-app-staging-secrets` with the value:
```
{
  jwt: "myjwtkey"
}
```
Then the resulting config data will be:
```
jwt:
    jwt_key: "myjwtkey"
```
And is accessible in code by attributes or dict like so:
```python
  config = YamlConfig(...)
  # accessing secret value by attributes
  secret_jwt_secret = config.jwt.jwt_key
  # accessing secret value by dict keys
  secret_jwt_secret = config['jwt']['jwt_key']
  # you can even mix and match them
  secret_jwt_secret = config.jwt['jwt_key']
```

# Example

See [test/example_projects](test/example_projects) for complete working project layouts.
# simple_config

# License

Licensed under the [Apache License 2.0](LICENSE.txt).