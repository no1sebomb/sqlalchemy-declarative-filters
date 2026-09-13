"""The public stubs, as a type checker sees them.

The claim `Filters[Book]` makes is a static one, so the only way to test it is to
run a type checker. mypy is a development dependency; the fixture it is pointed at
is excluded from the package's own mypy run, because half of it is meant to fail.
"""

import pathlib
import re

import pytest

api = pytest.importorskip("mypy.api")

CASES = pathlib.Path(__file__).parent / "typing" / "cases.py"
ERROR = re.compile(r"^[^:]+:(\d+): error:", re.MULTILINE)


@pytest.fixture(scope="module")
def reported_lines():
    """The line numbers mypy reported an error on."""

    stdout, stderr, _ = api.run(["--no-incremental", str(CASES)])

    assert not stderr, stderr

    return {int(match.group(1)) for match in ERROR.finditer(stdout)}, stdout


@pytest.fixture(scope="module")
def expected_lines():
    """The line numbers marked `# type-error` in the fixture."""

    return {
        number
        for number, line in enumerate(CASES.read_text().splitlines(), start=1)
        if line.rstrip().endswith("# type-error")
    }


def test_the_fixture_marks_something():
    # A fixture that stopped marking anything would pass vacuously.
    assert CASES.read_text().count("# type-error") >= 2


def test_mypy_rejects_exactly_the_marked_lines(reported_lines, expected_lines):
    reported, stdout = reported_lines

    assert reported == expected_lines, stdout
