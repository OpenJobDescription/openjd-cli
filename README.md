## Open Job Description - CLI

[![pypi](https://img.shields.io/pypi/v/openjd-cli.svg)](https://pypi.python.org/pypi/openjd-cli)

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
4. On Windows:
    * PowerShell 5.x

**EXPERIMENTAL** Note that compatibility with the Windows operating system is currently in active development
and should be considered to be experimental. We recommend that this application not be used in Windows-based
production environments at this time. We will remove this notice when Windows compatibility is considered
sufficiently stable and secure for use in Windows-based production environments.

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
$ openjd-cli summary /path/to/job.template.json \
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
$ openjd-cli run /path/to/job.template.json --step Step1 \
    --job-param PingServer=amazon.com \
    --task-param PingCount=20 \
    --task-param PingDelay=30

# ... Task logs accompanied by timestamps ...

--- Results of local session ---

Session ended successfully
Job: MyJob
Step: Step1
Duration: 1.0 seconds
Tasks run: 1

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

## Downloading

You can download this package from:
- [PyPI](https://pypi.org/project/openjd-cli/)
- [GitHub releases](https://github.com/OpenJobDescription/openjd-cli/releases)

### Verifying GitHub Releases

You can verify the authenticity of the release artifacts using the `gpg` command line tool.

1) Download the desired release artifacts from the GitHub releases page. Make sure to download the corresponding PGP signature file (ending with `.sig`) as well.
For example, if you would like to verify your download of the wheel for version `1.2.3`, you should have the following files downloaded:
    ```
    openjd_cli-1.2.3-py3-none-any.whl
    openjd_cli-1.2.3-py3-none-any.whl.sig
    ```

2) Install the `gpg` command line tool. The installation process varies by operating system. Please refer to the GnuPG website for instructions: https://gnupg.org/download/

3) Save the following contents to a file called `openjobdescription-pgp.asc`:
    ```
    -----BEGIN PGP PUBLIC KEY BLOCK-----
    
    mQINBGXGjx0BEACdChrQ/nch2aYGJ4fxHNQwlPE42jeHECqTdlc1V/mug+7qN7Pc
    C4NQk4t68Y72WX/NG49gRfpAxPlSeNt18c3vJ9/sWTukmonWYGK0jQGnDWjuVgFT
    XtvJAAQBFilQXN8h779Th2lEuD4bQX+mGB7l60Xvh7vIehE3C4Srbp6KJXskPLPo
    dz/dx7a+GXRiyYCYbGX4JziXSjQZRc0tIaxLn/GDm7VnXpdHcUk3qJitree61oC8
    agtRHCH5s56E8wt8fXzyStElMkFIZsoLDlLp5lFqT81En9ho/+K6RLBkIj0mC8G7
    BafpHKlxkrIgNK3pWACL93GE6xihqwkZMCAeqloVvkOTdfAKDHuDSEHwKxHG3cZ1
    /e1YhtkPMVF+NMeoQavykUGVUT1bRoVNdk6bYsnbUjUI1A+JNf6MqvdRJyckZqEC
    ylkBekBp/SFpFHvQkRCpfVizm2GSrjdZKgXpm1ZlQJyMRVzc/XPbqdSWhz52r3IC
    eudwReHDc+6J5rs6tg3NbFfPVfCBMSqHlu1HRewWAllIp1+y6nfL4U3iEsUvZ1Y6
    IV3defHIP3kNPU14ZWf3G5rvJDZrIRnjoWhDcaVmivmB/cSdDzphL5FovSI8dsPm
    iU/JZGQb3EvZq+nl4pOiK32hETJ/fgCCzgUA3WqGeFNUNSI9KYZgBe6daQARAQAB
    tDRPcGVuIEpvYiBEZXNjcmlwdGlvbiA8b3BlbmpvYmRlc2NyaXB0aW9uQGFtYXpv
    bi5jb20+iQJXBBMBCABBFiEEvBcWYrv5OB7Tl2sZovDwWbzECYcFAmXGjx0DGy8E
    BQkDwmcABQsJCAcCAiICBhUKCQgLAgMWAgECHgcCF4AACgkQovDwWbzECYcSHRAA
    itPYx48xnJiT6tfnult9ZGivhcXhrMlvirVYOqEtRrt0l18sjr84K8mV71eqFwMx
    GS7e4iQP6guqW9biQfMA5/Id8ZjE7jNbF0LUGsY6Ktj+yOlAbTR+x5qr7Svb7oEs
    TMB/l9HBZ1WtIRzcUk9XYqzvYQr5TT997A63F28u32RchJ+5ECAz4g/p91aWxwVo
    HIfN10sGzttoukJCzC10CZAVscJB+nnoUbB/o3bPak6GUxBHpMgomb0K5g4Z4fXY
    4AZ9jKFoLgNcExdwteiUdSEnRorZ5Ny8sP84lwJziD3wuamVUsZ1C/KiQJBGTp5e
    LUY38J1oIwptw5fqjaAq2GQxEaIknWQ4fr3ZvNYUuGUt5FbHe5U5XF34gC8PK7v7
    bT/7sVdZZzKFScDLfH5N36M5FrXfTaXsVbfrRoa2j7U0kndyVEZyJsKVAQ8vgwbJ
    w/w2hKkyQLAg3l5yO5CHLGatsfSIzea4WoOAaroxiNtL9gzVXzqpw6qPEsH9hsws
    HsPEQWXHmDQvFTNUU14qic1Vc5fyxCBXIAGAPBd20b+219XznJ5uBKUgtvnqcItj
    nMYe6Btxh+pjrTA15X/p81z6sB7dkL1hPHfawLhCEzJbIPyyBTQYqY00/ap4Rj7t
    kzSiyzBejniFfAZ6eYBWsej7uXUsVndBF1ggZynPTeE=
    =iaEm
    -----END PGP PUBLIC KEY BLOCK-----
    ```

4) Import the OpenPGP key for Open Job Description by running the following command:

    ```
    gpg --import --armor openjobdescription-pgp.asc
    ```

5) Determine whether to trust the OpenPGP key. Some factors to consider when deciding whether or not to trust the above key are:

    - The internet connection you’ve used to obtain the GPG key from this website is secure
    - The device that you are accessing this website on is secure

    If you have decided to trust the OpenPGP key, then edit the key to trust with `gpg` like the following example:
    ```
    $ gpg --edit-key A2F0F059BCC40987
    gpg (GnuPG) 2.0.22; Copyright (C) 2013 Free Software Foundation, Inc.
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.
    
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    gpg> trust
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    Please decide how far you trust this user to correctly verify other users' keys
    (by looking at passports, checking fingerprints from different sources, etc.)
    
      1 = I don't know or won't say
      2 = I do NOT trust
      3 = I trust marginally
      4 = I trust fully
      5 = I trust ultimately
      m = back to the main menu
    
    Your decision? 5
    Do you really want to set this key to ultimate trust? (y/N) y
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: ultimate      validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    Please note that the shown key validity is not necessarily correct
    unless you restart the program.
    
    gpg> quit
    ```

6) Verify the signature of the Open Job Description release via `gpg --verify`. The command for verifying the example files from step 1 would be:

    ```
    gpg --verify ./openjd_cli-1.2.3-py3-none-any.whl.sig ./openjd_cli-1.2.3-py3-none-any.whl
    ```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.

