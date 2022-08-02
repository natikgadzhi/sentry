#!.venv/bin/python

from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Iterable, List, Mapping, Set, Tuple

"""Add server mode decorators to unit test cases en masse.

Unlike `audit_mode_limits`, this script can't really reflect on interpreted
Python code in order to distinguish unit tests. It instead relies on an external
`pytest` run to collect the list of test cases, and some does kludgey regex
business in order to apply the decorators.


Instructions for use:

From the Sentry project root, do
    ./scripts/servermode/audit_unit_tests.py

Running `pytest` to collect unit test cases can be quite slow. To speed up
repeated runs, first do
    pytest --collect-only > pytest-collect.txt
to cache the description of test cases on disk. Delete the file to refresh.
"""


@dataclass(frozen=True, eq=True)
class TestCaseFunction:
    """Model a function representing a test case.

    The function may be either a top-level function or a test class method.
    """

    package: str | None
    module: str
    class_name: str | None
    func_name: str
    arg: str | None

    @staticmethod
    def parse(collect_output: str) -> Iterable[TestCaseFunction]:
        package = None
        module = None
        class_name = None

        for match in re.finditer(r"\n+(\s*)<(\w+)\s+(.*?)(\[.*?])?>", collect_output):
            indent, tag, value, arg = match.groups()
            if tag == "Package":
                package = value
                module = None
                class_name = None
            elif tag == "Module":
                if len(indent) == 0:
                    package = None
                module = value
                class_name = None
            elif tag in ("Class", "UnitTestCase"):
                class_name = value
            elif tag in ("Function", "TestCaseFunction"):
                if module is None:
                    raise ValueError
                yield TestCaseFunction(package, module, class_name, value, arg)
            elif tag != "frozen":
                raise ValueError(f"Unrecognized tag: {tag!r}")

    @property
    def top_level(self) -> TopLevelTestCase:
        return TopLevelTestCase(
            self.package,
            self.module,
            self.class_name or self.func_name,
            self.class_name is not None,
        )


@dataclass(frozen=True, eq=True)
class TopLevelTestCase:
    """A key for a top-level test case.

    Represents either a test class or a stand-alone test function.
    """

    package: str | None
    module: str
    name: str
    is_class: bool

    @property
    def pattern(self):
        decl = "class" if self.is_class else "def"
        return re.compile(rf"(\n@\w+\s*)*\n{decl}\s+{self.name}\s*\(")


class TestCaseMap:
    def __init__(self, cases: Iterable[TestCaseFunction]) -> None:
        self.cases = tuple(cases)

    @cached_property
    def file_map(self) -> Mapping[TestCaseFunction, List[str]]:
        groups = defaultdict(lambda: defaultdict(list))
        for c in self.cases:
            groups[c.package][c.module].append(c)

        file_map = defaultdict(list)

        for (module, cases) in groups[None].items():
            for case in cases:
                file_map[case].append(module)

        for (dirpath, dirnames, filenames) in os.walk("tests"):
            _, current_dirname = os.path.split(dirpath)
            if current_dirname in groups:
                modules = groups[current_dirname]
                for filename in filenames:
                    if filename in modules:
                        path = os.path.join(dirpath, filename)
                        for case in modules[filename]:
                            file_map[case].append(path)

        return file_map

    @cached_property
    def top_level_file_map(self) -> Mapping[TopLevelTestCase, Set[str]]:
        top_level_file_map = defaultdict(set)
        for (case, filenames) in self.file_map.items():
            for filename in filenames:
                top_level_file_map[case.top_level].add(filename)
        return top_level_file_map

    def find_all_case_matches(self) -> Iterable[TestCaseMatch]:
        for case in self.top_level_file_map:
            for path in self.top_level_file_map[case]:
                with open(path) as f:
                    src_code = f.read()
                match = case.pattern.search(src_code)
                if match:
                    decorator_matches = re.findall(r"@(\w+)", match.group())
                    decorators = tuple(str(m) for m in decorator_matches)
                    yield TestCaseMatch(path, case, decorators)

    def add_decorators(
        self, condition: Callable[[TestCaseMatch], (str | None)] | None = None
    ) -> int:
        count = 0
        for match in self.find_all_case_matches():
            decorator = condition(match)
            if decorator:
                result = match.add_decorator(decorator)
                count += int(result)
        return count


@dataclass(frozen=True, eq=True)
class TestCaseMatch:
    path: str
    case: TopLevelTestCase
    decorators: Tuple[str]

    def add_decorator(self, decorator: str) -> bool:
        if decorator in self.decorators:
            return False
        with open(self.path) as f:
            src_code = f.read()
        new_code = self.case.pattern.sub(rf"\n@{decorator}\g<0>", src_code)
        if new_code == src_code:
            raise Exception(f"Failed to find case: {decorator=}; {self.path=}; {self.case=}")
        new_code = f"from sentry.testutils.servermode import {decorator}\n{new_code}"
        with open(self.path, mode="w") as f:
            f.write(new_code)
        return True


# Do `pytest --collect-only > pytest-collect.txt` to speed up repeated local runs
LOCAL_SAVE = "pytest-collect.txt"


def main(test_root="."):
    if os.path.exists(LOCAL_SAVE):
        with open(LOCAL_SAVE) as f:
            pytest_collection = f.read()
    else:
        process = subprocess.run(["pytest", test_root, "--collect-only"], capture_output=True)
        pytest_collection = process.stdout.decode("utf-8")

    case_map = TestCaseMap(TestCaseFunction.parse(pytest_collection))

    def condition(match: TestCaseMatch) -> str | None:
        if not match.case.is_class:
            return None
        if any(
            (word in match.case.name)
            for word in ("Organization", "Project", "Team", "Group", "Event", "Issue")
        ):
            return "customer_silo_test"

    count = case_map.add_decorators(condition)
    print(f"Decorated {count} case{'' if count == 1 else 's'}")  # noqa


if __name__ == "__main__":
    main()
