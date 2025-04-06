# CI-Ver

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/ruzzz/py-ci-ver)](https://github.com/ruzzz/py-ci-ver/blob/main/LICENSE)

CI version utility for managing versioning in development branches, ensuring they are always higher than the versions in production branches.

## Features

- Automatically verify that development branch versions are higher than production
- Increment version numbers when necessary
- Works with semantic versioning (major.minor.build)
- Git integration for branch detection
- Simple command-line interface

## Installation

```bash
pip install ci-ver
```

## Usage

CI-Ver provides two main commands:

### Check Version

Verifies that the version in your development branch is higher than the production version:

```bash
ci-ver check path/to/your/version_file.py
```

### Update Version

Automatically increments the build number if the development version is not higher than production:

```bash
ci-ver up path/to/your/version_file.py
```

## Example Integration

Add to your CI workflows to ensure proper versioning:

```yaml
- name: Check version
  run: ci-ver check path/to/version_file.py
```

## Configuration

CI-Ver automatically detects development branches (any branch that is not 'master' or 'develop'). 

The version file should contain a version string in the format:

```python
__version__ = '1.0.0'
```

## Development

```bash
# Install dependencies
make deps

# Run tests
make test

# Format code
make fmt

# Check code
make check
```

## License

[MIT](LICENSE)