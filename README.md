## Open Job Description - CLI

Open Job Description (OpenJD) is a flexible open specification for defining render jobs which are portable
between studios and render solutions. This package provides a command-line interface that can be used
to: Verifiy that OpenJD templates are syntactically correct; Run OpenJD jobs locally; and more.

For more information about Open Job Description and our goals with it, please see the
Open Job Description [Wiki on GitHub](https://github.com/OpenJobDescription/openjd-specifications/wiki).

## Compatibility

This library requires:

1. Python 3.9 or higher;
2. Linux, MacOS, or Windows operating system;
3. On Linux/MacOS:
    * `sudo`
4. On Windows:
    * PowerShell 7+

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/).

1. The MAJOR version is currently 0.
2. The MINOR version is incremented when backwards incompatible changes are introduced to the public API.
3. The PATCH version is incremented when bug fixes or backwards compatible changes are introduced to the public API.

## Commands

### Getting Help

The main `openjd` command and all subcommands support a `--help` option to display
information on how to use the command.

### `check`
Reports any syntax errors that appear in the schema of a Job Template file.

#### Arguments

|Name|Type|Required|Description|Example|
|---|---|---|---|---|
|`path`|path|yes|A path leading to a Job or Environment template file.|`/path/to/template.json`|
|`--output`|string|no|How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.|`--output json`, `--output yaml`|

#### Example
```sh
$ openjd check /path/to/job.template.json

Template at '/path/to/job.template.json' passes validation checks!
```

### `summary`
Displays summary information about a sample Job or a Step therein. The user may provide parameters to customize the Job.

#### Arguments

|Name|Type|Required|Description|Example|
|---|---|---|---|---|
|`path`|path|yes|A path leading to a Job template file.|`/path/to/job.template.json`|
|`--job-param`, `-p`|string, path|no|A key-value pair representing a parameter in the template and the value to use for it, provided as a string or a path to a JSON/YAML document prefixed with 'file://'. Can be specified multiple times.|`--job-param MyParam=5`, `-p file://parameter_file.json`|
|`--step-name`|string|no|The name of the Step to summarize.|`--step-name Step1`|
|`--output`|string|no|How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.|`--output json`, `--output yaml`|

#### Example
```sh
$ openjd-cli summary /path/to/job.template.json \
    --job-param JobName=SampleJob \
    --job-param FileToRender=sample.blend \
    --job-param file://some_more_parameters.json

--- Summary for 'SampleJob' ---

Parameters:
    - JobName (STRING): SampleJob
    - FileToRender (PATH): sample.blend
    - AnotherParameter (INT): 10

Total steps: 2
Total tasks: 15
Total environments: 0

--- Steps in 'SampleJob' ---

1. 'Step1'
    1 Task parameter(s)
    10 total Tasks

2. 'Step2'
    2 Task parameter(s)
    5 total Tasks
```

### `run`

Given a Job Template, Job Parameters, and optional Environment Templates this will run a set of the Tasks
from the constructed Job locally within an OpenJD Sesssion.

Please see [How Jobs Are Run](https://github.com/OpenJobDescription/openjd-specifications/wiki/How-Jobs-Are-Run) for
details on how Open Job Description's Jobs are run within Sessions.

#### Arguments

|Name|Type|Required|Description|Example|
|---|---|---|---|---|
|`path`|path|yes|A path leading to a Job template file.|`/path/to/job.template.json`|
|`--step-name`|string|yes|The name of the Step to run in a local Session.|`--step-name Step1`|
|`--environment`|paths|no|Path to a file containing Environment Template definitions. Can be provided multiple times.|`--environment /path/to/env.template1.json --environment /path/to/env.template2.yaml`|
|`--job-param`, `-p`|string, path|no|A key-value pair representing a parameter in the template and the value to use for it, provided as a string or a path to a JSON/YAML document prefixed with 'file://'. Can be specified multiple times.|`--job-param MyParam=5`, `-p file://parameter_file.json`|
|`--task-params`, `-tp`|string, path|no|A list of key-value pairs representing a Task parameter set for the Step, provided as a string or a path to a JSON/YAML document prefixed with 'file://'. If present, the Session will run one Task per parameter set supplied with `--task-params`. Can be specified multiple times.|`--task-params PingCount=20 PingDelay=30`, `-tp file://parameter_set_file.json`|
|`--maximum-tasks`|integer|no|A maximum number of Tasks to run from this Step. Unless present, the Session will run all Tasks defined in the Step's parameter space, or one Task per `--task-params` argument.|`--maximum-tasks 5`|
|`--run-dependencies`|flag|no|If present, runs all of a Step's dependencies in the Session prior to the Step itself.|`--run-dependencies`|
|`--path-mapping-rules`|string, path|no|The path mapping rules to apply to the template. Should be a JSON-formatted list of Open Job Description path mapping rules, provided as a string or a path to a JSON/YAML document prefixed with 'file://'.|`--path-mapping-rules [{"source_os": "Windows", "source_path": "C:\test", "destination_path": "/mnt/test"}]`, `--path-mapping-rules file://rules_file.json`|
|`--output`|string|no|How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.|`--output json`, `--output yaml`|

#### Example
```sh
$ openjd-cli run /path/to/job.template.json --step Step1 \
    --job-param PingServer=amazon.com \
    --task-params PingCount=20 PingDelay=30 \
    --task-params file://some_task_parameter_set.json
    --maximum-tasks 5

# ... Task logs accompanied by timestamps ...

--- Results of local session ---

Session ended successfully
Job: MyJob
Step: Step1
Duration: 1.0 seconds
Tasks run: 5

```

### `schema`
Returns the Open Job Description model as a JSON schema document body.

#### Arguments

|Name|Type|Required|Description|Example|
|---|---|---|---|---|
|`--version`|string|yes|The specification version to get the JSON schema for.|`--version jobtemplate-2023-09`|
|`--output`|string|no|How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.|`--output json`, `--output yaml`|

#### Example
```sh
$ openjd-cli schema --version jobtemplate-2023-09

{
    "title": "JobTemplate",
    # ... JSON body corresponding to the Open Job Description model schema ...
}
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.

