## Open Job Description - CLI

[![pypi](https://img.shields.io/pypi/v/openjd-cli.svg)](https://pypi.python.org/pypi/openjd-cli)
[![python](https://img.shields.io/pypi/pyversions/openjd-cli.svg?style=flat)](https://pypi.python.org/pypi/openjd-cli)
[![license](https://img.shields.io/pypi/l/openjd-cli.svg?style=flat)](https://github.com/OpenJobDescription/openjd-cli/blob/mainline/LICENSE)

Open Job Description (OpenJD) is a flexible open specification for defining render jobs which are portable
between studios and render solutions. This package provides a command-line interface that can be used
to validate OpenJD templates, run OpenJD jobs locally, and more.

For more information about Open Job Description and our goals with it, please see the
Open Job Description [Wiki on GitHub](https://github.com/OpenJobDescription/openjd-specifications/wiki).

## Compatibility

This library requires:

1. Python 3.9 or higher;
2. Linux, MacOS, or Windows operating system;
3. On Linux/MacOS:
    * `sudo`

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/), but is still considered to be in its
initial development, thus backwards incompatible versions are denoted by minor version bumps. To help illustrate how
versions will increment during this initial development stage, they are described below:

1. The MAJOR version is currently 0, indicating initial development.
2. The MINOR version is currently incremented when backwards incompatible changes are introduced to the public API.
3. The PATCH version is currently incremented when bug fixes or backwards compatible changes are introduced to the public API.

## Contributing

We encourage all contributions to this package.  Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for our contributing guidelines.

## Commands

### Getting Help

The main `openjd` command and all subcommands support a `--help` option to display
information on how to use the command.

### `check`

Validates, or reports any syntax errors that appear in the schema of a Job Template file.

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

Displays summary information about a sample Job or Step, and the Steps and Tasks therein. The user may provide parameters to
customize the Job, as parameters can have an impact on the amount of Steps and Tasks that a job consists of.

#### Arguments

|Name|Type|Required| Description                                                                                                                                                                                                                               |Example|
|---|---|---|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---|
|`path`|path|yes| A path leading to a Job template file.                                                                                                                                                                                                    |`/path/to/job.template.json`|
|`--job-param`, `-p`|string, path|no| The values for the job template's parameters. Can be provided as key-value pairs, inline JSON string, or path(s) to a JSON or YAML document. If provided more than once then the given values are combined in the order that they appear. |`--job-param MyParam=5`, `-p file://parameter_file.json`, `-p '{"MyParam": "5"}'`|
|`--step`|string|no| The name of the Step to summarize.                                                                                                                                                                                                        |`--step Step1`|
|`--output`|string|no| How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.                                                                                                                             |`--output json`, `--output yaml`|

#### Example
```sh
$ openjd summary /path/to/job.template.json \
    --job-param JobName=SampleJob \
    --job-param '{"FileToRender": "sample.blend"}' \
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

|Name|Type|Required| Description                                                                                                                                                                                                                                                                           |Example|
|---|---|---|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---|
|`path`|path|yes| A path leading to a Job template file.                                                                                                                                                                                                                                                |`/path/to/job.template.json`|
|`--step`|string|yes| The name of the Step to run in a local Session.                                                                                                                                                                                                                                       |`--step Step1`|
|`--environment`|paths|no| Path to a file containing Environment Template definitions. Can be provided multiple times.                                                                                                                                                                                           |`--environment /path/to/env.template1.json --environment /path/to/env.template2.yaml`|
|`--job-param`, `-p`|string, path|no| The values for the job template's parameters. Can be provided as key-value pairs, inline JSON string, or as path(s) to a JSON or YAML document. If provided more than once then the given values are combined in the order that they appear.                                          |`--job-param MyParam=5`, `-p file://parameter_file.json`, `-p '{"MyParam": "5"}'`|
|`--task-param`, `-tp`|string|no| Instructs the command to run a single task in a Session with the given value for one of the task parameters. The option must be provided once for each task parameter defined for the Step, with each instance providing the value for a different task parameter. Mutually exclusive with `--tasks` and `--maximum-tasks`. |`-tp MyParam=5 -tp MyOtherParam=Foo`|
|`--tasks`|string, path|no| Instructs the command to run one or more tasks for the Step in a Session. The argument must be either the filename of a JSON or YAML file containing an array of maps from task parameter name to value; or an inlined JSON string of the same. Mutually exclusive with `--task-param/-tp` and `--maximum-tasks`. |`--tasks '[{"MyParam": 5}]'`, `--tasks file://parameter_set_file.json`|
|`--maximum-tasks`|integer|no| A maximum number of Tasks to run from this Step. Unless present, the Session will run all Tasks defined in the Step's parameter space or the Task(s) selected by the `--task-param` or `--tasks` arguments. Mutually exclusive with `--task-param/-tp` and `--tasks`. |`--maximum-tasks 5`|
|`--run-dependencies`|flag|no| If present, runs all of a Step's dependencies in the Session prior to the Step itself.                                                                                                                                                                                                |`--run-dependencies`|
|`--path-mapping-rules`|string, path|no| The path mapping rules to apply to the template. Should be a JSON-formatted list of Open Job Description path mapping rules, provided as a string or a path to a JSON/YAML document prefixed with 'file://'.                                                                          |`--path-mapping-rules [{"source_os": "Windows", "source_path": "C:\test", "destination_path": "/mnt/test"}]`, `--path-mapping-rules file://rules_file.json`|
|`--preserve`|flag|no| If present, the Session's working directory will not be deleted when the run is completed.           |`--preserve`|
|`--verbose`|flag|no| If present, then verbose logging will be enabled in the Session's log. |`--verbose`|
|`--output`|string|no| How to display the results of the command. Allowed values are `human-readable` (default), `json`, and `yaml`.                                                                                                                                                                         |`--output json`, `--output yaml`|

#### Example
```sh
$ openjd run /path/to/job.template.json --step Step1 \
    --job-param PingServer=amazon.com \
    --task-param PingCount=20 \
    --task-param PingDelay=30

# ... Task logs accompanied by timestamps ...

--- Results of local session ---

Session ended successfully
Job: MyJob
Step: Step1
Duration: 1.0 seconds
Chunks run: 1

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
$ openjd schema --version jobtemplate-2023-09

{
    "title": "JobTemplate",
    # ... JSON body corresponding to the Open Job Description model schema ...
}
```

## Downloading

You can download this package from:
- [PyPI](https://pypi.org/project/openjd-cli/)
- [GitHub releases](https://github.com/OpenJobDescription/openjd-cli/releases)

### Verifying GitHub Releases

See [Verifying GitHub Releases](https://github.com/OpenJobDescription/openjd-cli?tab=security-ov-file#verifying-github-releases) for more information.

## Security

We take all security reports seriously. When we receive such reports, we will
investigate and subsequently address any potential vulnerabilities as quickly
as possible. If you discover a potential security issue in this project, please
notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly via email to [AWS Security](aws-security@amazon.com). Please do not
create a public GitHub issue in this project.

## License

This project is licensed under the Apache-2.0 License.

