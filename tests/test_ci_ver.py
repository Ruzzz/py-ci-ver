import io
import re
from unittest.mock import patch

import pytest

from ci_ver import (
    CiVersionConfig,
    CiVersionTool,
    GitTool,
    VersionError,
    VersionT,
    out_err,
    out_msg,
)


def test_version_comparison():
    # Basic equality
    assert VersionT(0, 3, 0) == VersionT(0, 3, 0)
    assert VersionT(0, 2, 18) != VersionT(0, 3, 0)

    # Less than
    assert VersionT(0, 2, 18) < VersionT(0, 3, 0)
    assert VersionT(0, 3, 0) < VersionT(0, 3, 1)
    assert VersionT(0, 3, 0) < VersionT(1, 0, 0)

    # Less than or equal
    assert VersionT(0, 2, 18) <= VersionT(0, 3, 0)
    assert VersionT(0, 3, 0) <= VersionT(0, 3, 0)

    # Greater than
    assert VersionT(0, 3, 0) > VersionT(0, 2, 18)
    assert VersionT(1, 0, 0) > VersionT(0, 9, 9)

    # Greater than or equal
    assert VersionT(0, 3, 0) >= VersionT(0, 2, 18)
    assert VersionT(0, 3, 0) >= VersionT(0, 3, 0)

    # String representation
    assert str(VersionT(1, 2, 3)) == '1.2.3'

    # Compare with non-VersionT objects should return NotImplemented
    assert VersionT(1, 2, 3).__eq__('1.2.3') is NotImplemented
    assert VersionT(1, 2, 3).__ne__('1.2.3') is NotImplemented


def test_version_parse():
    config = CiVersionConfig(
        re.compile(r'(\d+)\.(\d+)(?:\.(\d+))?'),
        re.compile(r'__version__ = \'(\d+)\.(\d+)(?:\.(\d+))?'),
        "__version__ = '{}.{}.{}'",
    )

    # Test parsing from tag
    version = CiVersionTool.parse_version('1.2.3', regex=config.ver_re)
    assert version == VersionT(1, 2, 3)

    # Test parsing without build number
    version = CiVersionTool.parse_version('1.2', regex=config.ver_re)
    assert version == VersionT(1, 2, 0)

    # Test parsing from file
    version = CiVersionTool.parse_version("__version__ = '1.2.3'", regex=config.in_file_ver_re)
    assert version == VersionT(1, 2, 3)

    # Test no match
    version = CiVersionTool.parse_version('no version here', regex=config.ver_re)
    assert version is None


@patch('ci_ver.read_shell')
def test_git_tool(mock_read_shell):
    # Test is_dev_branch
    mock_read_shell.return_value = 'feature/branch'
    git_tool = GitTool()
    assert git_tool.is_dev_branch() is True

    # Test non-dev branch
    mock_read_shell.return_value = 'master'
    assert git_tool.is_dev_branch() is False

    # Test custom non-dev branches
    git_tool = GitTool(not_dev_branches=('master', 'main', 'release'))
    mock_read_shell.return_value = 'release'
    assert git_tool.is_dev_branch() is False

    # Test get_tag
    mock_read_shell.side_effect = ['abc123', 'v1.0.0']
    assert GitTool.get_tag() == 'v1.0.0'

    # Test tag error
    mock_read_shell.side_effect = ['', '']
    with pytest.raises(VersionError, match='Cannot determine git tag'):
        GitTool.get_tag()


def test_output_functions():
    # Test out_msg
    with patch('sys.stdout', new=io.StringIO()) as fake_out:
        out_msg('test', 'message')
        assert fake_out.getvalue().strip() == 'ci-ver: test message'

    # Test out_err
    with patch('sys.stdout', new=io.StringIO()) as fake_out:
        out_err('error', 'message')
        assert fake_out.getvalue().strip() == 'ci-ver-error: error message'
