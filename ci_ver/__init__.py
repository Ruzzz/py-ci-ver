"""CI version utility for managing versioning in development branches.

This module provides tools for checking and updating version numbers in development branches,
ensuring they are always higher than the versions in production branches.
"""

import argparse
import re
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import NamedTuple, Protocol

__version__ = '1.0.1'


def read_shell(cmd: str) -> str:
    """Execute shell command and return its output as a string.

    Args:
        cmd: Command to execute

    Returns:
        Command output as string
    """
    args = shlex.split(cmd)
    with subprocess.Popen(args, stdout=subprocess.PIPE) as process:  # noqa: S603
        return process.communicate()[0].decode('utf-8').strip()


@unique
class Cmds(str, Enum):
    CHECK = 'check'
    UP = 'up'


class VersionError(Exception):
    pass


class VersionT(NamedTuple):
    """Semantic version representation as a named tuple.

    Represents a version as major.minor.build and provides comparison operations.
    """

    major: int
    minor: int
    build: int

    def compare(self, other: 'VersionT') -> int:
        """Compare two versions and return difference.

        Args:
            other: Version to compare with

        Returns:
            Negative if self < other, positive if self > other, zero if equal
        """
        return (self.major - other.major) or (self.minor - other.minor) or (self.build - other.build)

    def __str__(self) -> str:
        return f'{self.major}.{self.minor}.{self.build}'

    def __lt__(self, other: 'VersionT') -> bool:  # type: ignore[override]
        return self.compare(other) < 0

    def __le__(self, other: 'VersionT') -> bool:  # type: ignore[override]
        return self.compare(other) <= 0

    def __gt__(self, other: 'VersionT') -> bool:  # type: ignore[override]
        return self.compare(other) > 0

    def __ge__(self, other: 'VersionT') -> bool:  # type: ignore[override]
        return self.compare(other) >= 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionT):
            return NotImplemented
        return self.compare(other) == 0

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, VersionT):
            return NotImplemented
        return self.compare(other) != 0


class VcsToolP(Protocol):
    """Protocol for version control system tools."""

    def is_dev_branch(self) -> bool: ...
    def get_tag(self) -> str: ...


class GitTool:
    """Git implementation of the VCS tool protocol."""

    NOT_DEV_BRANCHES = 'master', 'develop'

    def __init__(self, not_dev_branches: tuple[str, ...] | None = None):
        """Initialize GitTool.

        Args:
            not_dev_branches: Branches considered non-development
        """
        self.not_dev_branches = not_dev_branches or self.NOT_DEV_BRANCHES

    def is_dev_branch(self) -> bool:
        """Check if current branch is a development branch.

        Returns:
            True if current branch is a development branch

        Raises:
            VersionError: If branch cannot be determined
        """
        if not (branch := read_shell('git rev-parse --abbrev-ref HEAD')):
            raise VersionError('Cannot determine git branch')
        return branch not in self.not_dev_branches

    @classmethod
    def get_tag(cls) -> str:
        """Get the latest git tag.

        Returns:
            Latest tag string

        Raises:
            VersionError: If tag cannot be determined
        """
        if (tag_hash := read_shell('git rev-list --tags --max-count=1')) and (
            tag := read_shell(f'git describe --tags {tag_hash}')
        ):
            return tag
        raise VersionError('Cannot determine git tag')


@dataclass(frozen=True)
class CiVersionConfig:
    """Configuration for CI version tool."""

    ver_re: re.Pattern
    in_file_ver_re: re.Pattern
    in_file_ver_tmp: str


DEF_CI_VERSION_CONFIG = CiVersionConfig(
    re.compile(r'(\d+)\.(\d+)(?:\.(\d+))?', re.UNICODE),
    re.compile(r'__version__ = \'(\d+)\.(\d+)(?:\.(\d+))?', re.UNICODE),
    "__version__ = '{}.{}.{}",
)


class CiVersionTool:
    """Tool for managing CI version checks and updates."""

    @classmethod
    def parse_version(cls, content: str, *, regex: re.Pattern) -> VersionT | None:
        """Parse version from content using regex.

        Args:
            content: Text content to parse
            regex: Regular expression to match version

        Returns:
            Parsed version or None if not found
        """
        if parts := regex.search(content):
            major, minor, build = ((int(x) if x is not None else 0) for x in parts.groups())
            return VersionT(major, minor, build)
        return None

    def __init__(self, version_fname: str, *, cfg: CiVersionConfig | None = None, vcs_tool: VcsToolP | None = None):
        """Initialize CI version tool.

        Args:
            version_fname: Path to version file
            cfg: Configuration, defaults to DEF_CI_VERSION_CONFIG
            vcs_tool: VCS tool implementation, defaults to GitTool

        Raises:
            VersionError: If version file is invalid or branch is not dev
        """
        self.cfg = cfg or DEF_CI_VERSION_CONFIG
        self.vcs_tool = vcs_tool or GitTool()
        if not self.vcs_tool.is_dev_branch():
            raise VersionError('Branch is not dev')

        try:
            tag = self.vcs_tool.get_tag()
        except VersionError:
            tag = '0.0.0'
        self.prod_ver: VersionT = self.parse_version(tag, regex=self.cfg.ver_re)  # type: ignore[assignment]
        if not self.prod_ver:
            raise VersionError('Cannot get version from tag')

        self.path = Path(version_fname).resolve()
        if not (self.path.exists() and self.path.is_file()):
            raise VersionError(f'Version file not found: {self.path}')

        self.content: str = ''
        self.dev_ver: VersionT = None  # type: ignore[assignment]
        self._scan_dev_version()

    def _scan_dev_version(self) -> None:
        """Read version file and extract development version.

        Raises:
            VersionError: If version cannot be found in file
        """
        self.content = self.path.read_text(encoding='utf-8')
        self.dev_ver = self.parse_version(self.content, regex=self.cfg.in_file_ver_re)  # type: ignore[assignment]
        if not self.dev_ver:
            raise VersionError(f'Cannot find version in file: {self.path}')

    def check_version(self) -> None:
        """Check if development version is newer than production version.

        Raises:
            VersionError: If dev version is not newer than prod
        """
        if self.dev_ver <= self.prod_ver:
            raise VersionError(f'Dev version {self.dev_ver} is not newer than prod {self.prod_ver}')

    def try_up_version(self) -> VersionT | None:
        """Try to update version if needed.

        Increments build version if development version is not
        greater than production version.

        Returns:
            New version if updated, None otherwise

        Raises:
            VersionError: If version update fails
        """
        if self.dev_ver <= self.prod_ver:
            new_ver = VersionT(
                self.prod_ver.major,
                self.prod_ver.minor,
                self.prod_ver.build + 1,
            )
            new_content = self.cfg.in_file_ver_re.sub(self.cfg.in_file_ver_tmp.format(*new_ver), self.content)
            self.path.write_text(new_content, encoding='utf-8')

            self._scan_dev_version()
            if new_ver != self.dev_ver:
                raise VersionError(f'Cannot update dev version. Expected {new_ver}, got {self.dev_ver}')
            return new_ver
        return None


def out_msg(*args, **kwargs) -> None:
    """Print message to stdout with ci-ver prefix."""
    print('ci-ver:', *args, **kwargs)


def out_err(*args, **kwargs) -> None:
    """Print error message to stdout with ci-ver-error prefix."""
    print('ci-ver-error:', *args, **kwargs)


def cli(cfg: CiVersionConfig | None = None, vcs_tool: VcsToolP | None = None) -> None:
    """Command-line interface for CI version tool."""
    parser = argparse.ArgumentParser(description='CI Version Tool - check and update version in development branches')
    parser.add_argument('cmd', choices=list(Cmds), help='Command to execute (check or up)')
    parser.add_argument('fname', type=str, help='Path to version file')
    args = parser.parse_args()

    try:
        out_msg('version file', args.fname)
        ci_version_tool = CiVersionTool(args.fname, cfg=cfg, vcs_tool=vcs_tool)
        out_msg(f'prod {ci_version_tool.prod_ver}, dev {ci_version_tool.dev_ver}')

        if args.cmd == Cmds.CHECK:
            ci_version_tool.check_version()
            out_msg('dev version is ok')
        elif args.cmd == Cmds.UP:
            if (new_ver := ci_version_tool.try_up_version()) is None:
                out_msg('dev version is ok')
            else:
                out_msg('upgraded dev version:', new_ver)

    except VersionError as exc:
        out_err(str(exc))
        raise SystemExit(1) from exc
    except Exception as exc:
        out_err(f'Unexpected error: {exc!s}')
        raise SystemExit(2) from exc


if __name__ == '__main__':
    cli()
