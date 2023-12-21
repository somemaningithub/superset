# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest

from superset.exceptions import SupersetException
from superset.utils.core import (
    cast_to_boolean,
    check_is_safe_zip,
    DateColumn,
    is_test,
    normalize_dttm_col,
    parse_boolean_string,
    QueryObjectFilterClause,
    remove_extra_adhoc_filters,
)

ADHOC_FILTER: QueryObjectFilterClause = {
    "col": "foo",
    "op": "==",
    "val": "bar",
}

EXTRA_FILTER: QueryObjectFilterClause = {
    "col": "foo",
    "op": "==",
    "val": "bar",
    "isExtra": True,
}


@dataclass
class MockZipInfo:
    file_size: int
    compress_size: int


@pytest.mark.parametrize(
    "original,expected",
    [
        ({"foo": "bar"}, {"foo": "bar"}),
        (
            {"foo": "bar", "adhoc_filters": [ADHOC_FILTER]},
            {"foo": "bar", "adhoc_filters": [ADHOC_FILTER]},
        ),
        (
            {"foo": "bar", "adhoc_filters": [EXTRA_FILTER]},
            {"foo": "bar", "adhoc_filters": []},
        ),
        (
            {
                "foo": "bar",
                "adhoc_filters": [ADHOC_FILTER, EXTRA_FILTER],
            },
            {"foo": "bar", "adhoc_filters": [ADHOC_FILTER]},
        ),
        (
            {
                "foo": "bar",
                "adhoc_filters_b": [ADHOC_FILTER, EXTRA_FILTER],
            },
            {"foo": "bar", "adhoc_filters_b": [ADHOC_FILTER]},
        ),
        (
            {
                "foo": "bar",
                "custom_adhoc_filters": [
                    ADHOC_FILTER,
                    EXTRA_FILTER,
                ],
            },
            {
                "foo": "bar",
                "custom_adhoc_filters": [
                    ADHOC_FILTER,
                    EXTRA_FILTER,
                ],
            },
        ),
    ],
)
def test_remove_extra_adhoc_filters(
    original: Dict[str, Any], expected: Dict[str, Any]
) -> None:
    remove_extra_adhoc_filters(original)
    assert expected == original


def test_is_test() -> None:
    orig_value = os.getenv("SUPERSET_TESTENV")

    os.environ["SUPERSET_TESTENV"] = "true"
    assert is_test()
    os.environ["SUPERSET_TESTENV"] = "false"
    assert not is_test()
    os.environ["SUPERSET_TESTENV"] = ""
    assert not is_test()

    if orig_value is not None:
        os.environ["SUPERSET_TESTENV"] = orig_value


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("y", True),
        ("Y", True),
        ("yes", True),
        ("True", True),
        ("t", True),
        ("true", True),
        ("On", True),
        ("on", True),
        ("1", True),
        ("n", False),
        ("N", False),
        ("no", False),
        ("False", False),
        ("f", False),
        ("false", False),
        ("Off", False),
        ("off", False),
        ("0", False),
        ("foo", False),
        (None, False),
    ],
)
def test_parse_boolean_string(test_input: Optional[str], expected: bool) -> None:
    assert parse_boolean_string(test_input) == expected


def test_int_values() -> None:
    assert cast_to_boolean(1) is True
    assert cast_to_boolean(0) is False
    assert cast_to_boolean(-1) is True
    assert cast_to_boolean(42) is True
    assert cast_to_boolean(0) is False


def test_float_values() -> None:
    assert cast_to_boolean(0.5) is True
    assert cast_to_boolean(3.14) is True
    assert cast_to_boolean(-2.71) is True
    assert cast_to_boolean(0.0) is False


def test_string_values() -> None:
    assert cast_to_boolean("true") is True
    assert cast_to_boolean("TruE") is True
    assert cast_to_boolean("false") is False
    assert cast_to_boolean("FaLsE") is False
    assert cast_to_boolean("") is False


def test_none_value() -> None:
    assert cast_to_boolean(None) is None


def test_boolean_values() -> None:
    assert cast_to_boolean(True) is True
    assert cast_to_boolean(False) is False


def test_other_values() -> None:
    assert cast_to_boolean([]) is False
    assert cast_to_boolean({}) is False
    assert cast_to_boolean(object()) is False


def test_normalize_dttm_col() -> None:
    """
    Tests for the ``normalize_dttm_col`` function.

    In particular, this covers a regression when Pandas was upgraded from 1.5.3 to
    2.0.3 and the behavior of ``pd.to_datetime`` changed.
    """
    df = pd.DataFrame({"__time": ["2017-07-01T00:00:00.000Z"]})
    assert (
        df.to_markdown()
        == """
|    | __time                   |
|---:|:-------------------------|
|  0 | 2017-07-01T00:00:00.000Z |
    """.strip()
    )

    # in 1.5.3 this would return a datetime64[ns] dtype, but in 2.0.3 we had to
    # add ``exact=False`` since there is a leftover after parsing the format
    dttm_cols = (DateColumn("__time", "%Y-%m-%d"),)

    # the function modifies the dataframe in place
    normalize_dttm_col(df, dttm_cols)

    assert df["__time"].astype(str).tolist() == ["2017-07-01"]


def test_check_if_safe_zip_success(app_context: None) -> None:
    """
    Test if ZIP files are safe
    """
    ZipFile = MagicMock()
    ZipFile.infolist.return_value = [
        MockZipInfo(file_size=1000, compress_size=10),
        MockZipInfo(file_size=1000, compress_size=10),
        MockZipInfo(file_size=1000, compress_size=10),
        MockZipInfo(file_size=1000, compress_size=10),
        MockZipInfo(file_size=1000, compress_size=10),
    ]
    check_is_safe_zip(ZipFile)


def test_check_if_safe_zip_high_rate(app_context: None) -> None:
    """
    Test if ZIP files is not highly compressed
    """
    ZipFile = MagicMock()
    ZipFile.infolist.return_value = [
        MockZipInfo(file_size=1000, compress_size=1),
        MockZipInfo(file_size=1000, compress_size=1),
        MockZipInfo(file_size=1000, compress_size=1),
        MockZipInfo(file_size=1000, compress_size=1),
        MockZipInfo(file_size=1000, compress_size=1),
    ]
    with pytest.raises(SupersetException):
        check_is_safe_zip(ZipFile)


def test_check_if_safe_zip_hidden_bomb(app_context: None) -> None:
    """
    Test if ZIP file does not contain a big file highly compressed
    """
    ZipFile = MagicMock()
    ZipFile.infolist.return_value = [
        MockZipInfo(file_size=1000, compress_size=100),
        MockZipInfo(file_size=1000, compress_size=100),
        MockZipInfo(file_size=1000, compress_size=100),
        MockZipInfo(file_size=1000, compress_size=100),
        MockZipInfo(file_size=1000 * (1024 * 1024), compress_size=100),
    ]
    with pytest.raises(SupersetException):
        check_is_safe_zip(ZipFile)
