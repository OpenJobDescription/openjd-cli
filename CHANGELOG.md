## 0.7.7 (2026-09-02)



### Bug Fixes
* Forward the create-time step symbol table to openjd-sessions (#237) ([`bcd09b5`](https://github.com/OpenJobDescription/openjd-cli/commit/bcd09b5e1a2d7679c6b1d0b6281987bcf69cb46a))
* Forward the create-time step symbol table to sessions ([`bcd09b5`](https://github.com/OpenJobDescription/openjd-cli/commit/bcd09b5e1a2d7679c6b1d0b6281987bcf69cb46a))


## 0.7.6 (2026-08-11)


### Features
* RFC 0007/0008 support — step-level let bindings, wrap-hook step names, and template-declared
  extensions. A step's environments are entered with its step-level EXPR let bindings (RFC 0007),
  so environment variables and actions can reference them; RFC 0008 wrap hooks now resolve
  `WrappedStep.Name`; only the extensions a template declares are enabled; and `Job.Name` is
  seeded into the symbol table. ([`962e359`](https://github.com/OpenJobDescription/openjd-cli/commit/962e359b8c2aea7a3b818f6103a3fe6bb84177c4))
* Support RFC extensions in environment templates (#213) ([`cc8d354`](https://github.com/OpenJobDescription/openjd-cli/commit/cc8d3543c31e74d23897995127d3075bf314782d))

### Bug Fixes
* Require `openjd-sessions >= 0.10.11` ([`dfa118d`](https://github.com/OpenJobDescription/openjd-cli/commit/dfa118de0f7a49dee568e4c74f90d42faf6f8dd7))
* `openjd run` printed a stack trace instead of a readable error message when an environment failed to enter (e.g. violating RFC 0008's "at most one wrap environment" rule)
* `openjd run` reported a misleading "Must exit Environment X first" error when an environment failed partway through entering (e.g. a bad environment `variables` expression)
* `Step.Name` was not available in a step's `let` bindings and step-environment actions (RFC 0007 EXPR)
* Defer adaptive chunk adjustment without a measurable sample (#232) ([`7091007`](https://github.com/OpenJobDescription/openjd-cli/commit/7091007439699ba51549e36e94873bf689eb7bd9))


## 0.7.5 (2026-02-09)


### Features
* Implement [FEATURE_BUNDLE_1 RFC 0004](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0004-enhanced-limits-and-capabilities.md), increasing limits
  for job parameter counts and name lengths, enabling format strings in integer properties, providing control over embedded file line endings, and adding syntax sugar
  to simplify templates that run simple scripts with common interpreters ([`adfc5a6`](https://github.com/OpenJobDescription/openjd-cli/commit/adfc5a6ba57baed48cc664e4c63e0ad3d9229b0d))



## 0.7.4 (2025-11-14)


### Features
* Make `openjd run <template>` help output describe the job parameters ([`ac751c7`](https://github.com/OpenJobDescription/openjd-cli/commit/ac751c7a925812aed3236636513362b3dc377e4f))



## 0.7.3 (2025-10-27)


### Features
* Treat job template extensions other than .json as YAML ([`338f4d8`](https://github.com/OpenJobDescription/openjd-cli/commit/338f4d800155d25b8e2f81159f972837884b7c25))



## 0.7.2 (2025-10-23)


### Features
* Add version argument (#190) ([`1cae604`](https://github.com/OpenJobDescription/openjd-cli/commit/1cae604f2920c202405acf11858768fcc77b0406))


## 0.7.1 (2025-07-22)


### Features
* Adding support for redacted environment variable values through openjd_redacted_env ([`3070830`](https://github.com/OpenJobDescription/openjd-cli/commit/3070830f7e14f8115d2241aa051c03b0286f2d0c))

### Bug Fixes
* renable zero versions for semantic versioning ([`d1a8f9f`](https://github.com/OpenJobDescription/openjd-cli/commit/d1a8f9ffed60be0d58f470c022066d7f3666485d))
* sdist failed to install (#157) ([`77a443e`](https://github.com/OpenJobDescription/openjd-cli/commit/77a443eab00a6850d482b6f8e4d426a82ba1acf7))

## 0.7.0 (2025-03-19)

### BREAKING CHANGES
* The functions generate_jobs and job_from_template have changed to accept the environments and return the job parameters
  alongside the job. Constructing the LocalSession class now requires job parameters.

### Bug Fixes
* Running jobs with env templates does not support parameters ([`65a15b4`](https://github.com/OpenJobDescription/openjd-cli/commit/65a15b414bbd90a77c6b63451f5f052db2b8fcf8))

## 0.6.1 (2025-03-13)



### Bug Fixes
* `openjd run` command runs sessions twice ([`16ee6ae`](https://github.com/OpenJobDescription/openjd-cli/commit/16ee6ae63900b752cbaec7f1e68e758a64a56c99))

## 0.6.0 (2025-03-07)

### BREAKING CHANGES
* The logging output has changed to use relative timestamps by default, and print more messages about the job and steps that are running.

### Features
* Support adaptive chunking, general CLI improvement ([`664d008`](https://github.com/OpenJobDescription/openjd-cli/commit/664d0083c0e9d2d973a88e1e630e2af6cef67cc1))

## 0.5.1 (2025-02-26)

### Features

* Update to use Pydantic V2, and support task chunking (#134) ([`ad53f68`](https://github.com/OpenJobDescription/openjd-cli/pull/134/commits/ad53f689117d98273fb034916bcdd250e49ccffd))

## 0.5.0 (2024-11-13)


### Features
* **deps**: Update openjd-model to 0.5.* and openjd-session to 0.9.* (#118) ([`ef97dd8`](https://github.com/OpenJobDescription/openjd-cli/commit/ef97dd81e9dfc2e45a9c2605ae256b679961cd7b))


## 0.4.4 (2024-07-23)



### Bug Fixes
* run command exits when an action reaches timeout (#97) ([`d031a91`](https://github.com/OpenJobDescription/openjd-cli/commit/d031a91ee6d1796b33701c466dc52f5615ead3c6))
* run subcommand now exits all entered environments (#98) ([`f6a54b2`](https://github.com/OpenJobDescription/openjd-cli/commit/f6a54b20d5058b4c144b237c960212d9e9c5d2be))

## 0.4.3 (2024-04-16)

### Documenation
* Windows is no longer marked as experimental in documentation.


## 0.4.2 (2024-03-11)


### Features
* update to openjd-sessions 0.7.* (#66) ([`4d44db9`](https://github.com/OpenJobDescription/openjd-cli/commit/4d44db92e1c2e2e6aa1aa326bccc45ea8a5a31d4))


## 0.4.1 (2024-02-21)


### Features
* add template-debugging options to `openjd run` (#52) ([`80e8cb9`](https://github.com/OpenJobDescription/openjd-cli/commit/80e8cb9f12392dbd2e89c2bb850853640f2dc706))


## 0.4.0 (2024-02-13)

### BREAKING CHANGES
* public release (#41) ([`88dd089`](https://github.com/OpenJobDescription/openjd-cli/commit/88dd089848422b54acf99e1d69fbeacb61691676))



## 0.3.0 (2024-02-12)

### BREAKING CHANGES
* modifying how tasks are selected in run command (#37) ([`59c41d9`](https://github.com/OpenJobDescription/openjd-cli/commit/59c41d90eda95e666e49c37d1fdfe0d570742b32))
* Update openjd-cli to pass template_dir/cwd to preprocess_job_parameters (#29) ([`0983e1d`](https://github.com/OpenJobDescription/openjd-cli/commit/0983e1d0e3cece60ef825ec2d1b86dc20f2da22d))

### Features
* Allow job parameters as JSON string (#34) ([`8708b2c`](https://github.com/OpenJobDescription/openjd-cli/commit/8708b2ced5945465fd6706d95eac0bb1ac6317ca))
* support environment templates (#30) ([`b845d70`](https://github.com/OpenJobDescription/openjd-cli/commit/b845d70944863c11c308b50669cbdf99d037eeb3))

### Bug Fixes
* improve missing job parameter error for summary command (#44) ([`975863a`](https://github.com/OpenJobDescription/openjd-cli/commit/975863a7097d536ca786561e0adec665bb0eec77))
* Allow job parameter values to be empty strings. (#26) ([`b8959d0`](https://github.com/OpenJobDescription/openjd-cli/commit/b8959d077cc5cd4697f101ba3e45adceddb4ccac))

## 0.2.0 (2023-11-06)

### BREAKING CHANGES
* accept path mapping rules as per schema (#16) ([`a9d71fd`](https://github.com/OpenJobDescription/openjd-cli/commit/a9d71fd0ddba50cda9a6edeec93ad1cf3ce67fbd))



## 0.1.4 (2023-11-01)



### Bug Fixes
* add entrypoint to packaging (#14) ([`55cc90a`](https://github.com/OpenJobDescription/openjd-cli/commit/55cc90a58ec85271c4b84d392ddc627225a8bde9))

## 0.1.3 (2023-10-27)




## 0.1.1 (2023-09-14)



### Bug Fixes
* add back cli entrypoint (#8) ([`10188dd`](https://github.com/OpenJobDescription/openjd-cli/commit/10188ddf971dc51b043994858719fe91bbce8a68))

## 0.1.0 (2023-09-12)

* Initial import from internal repository


