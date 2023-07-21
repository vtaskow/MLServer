import json

import pytest

from mlserver import ModelSettings
from mlserver.context import model_context
from mlserver.logging import (
    ModelLoggerFormatter,
    configure_logger,
    logger,
)
from mlserver.settings import ModelParameters, Settings
from tests.fixtures import SumModel
from logging import INFO


@pytest.mark.parametrize(
    "name, version, expected_fmt",
    [
        (
            "foo",
            "v1.0",
            "[foo:v1.0]",
        ),
        (
            "foo",
            "",
            "[foo]",
        ),
        (
            "foo",
            None,
            "[foo]",
        ),
    ],
)
def test_model_logging_formatter_unstructured(name, version, expected_fmt, caplog):
    caplog.handler.setFormatter(ModelLoggerFormatter(use_structured_logging=False))
    caplog.set_level(INFO)

    model_settings = ModelSettings(
        name=name, implementation=SumModel, parameters=ModelParameters(version=version)
    )

    logger.info("Before model context")
    with model_context(model_settings):
        logger.info("Inside model context")
    logger.info("After model context")

    log_records = caplog.text.strip().split("\n")
    assert len(log_records) == 3

    assert expected_fmt not in log_records[0]
    assert expected_fmt in log_records[1]
    assert expected_fmt not in log_records[2]


@pytest.mark.parametrize(
    "name, version, expected_model_details",
    [
        (
            "foo",
            "v1.0",
            {"model_name", "model_version"}
        ),
        (
            "foo",
            "",
            {"model_name"}
        ),
        (
            "foo",
            None,
            {"model_name"}
        ),
    ],
)
def test_model_logging_formatter_structured(name, version, expected_model_details, caplog):
    caplog.handler.setFormatter(ModelLoggerFormatter(use_structured_logging=True))
    caplog.set_level(INFO)

    model_settings = ModelSettings(
        name=name, implementation=SumModel, parameters=ModelParameters(version=version)
    )

    logger.info("Before model context")
    with model_context(model_settings):
        logger.info("Inside model context")
    logger.info("After model context")

    log_records = caplog.text.strip().split("\n")
    assert len(log_records) == 3

    json_log_records = [json.loads(lr) for lr in log_records]

    assert not expected_model_details <= json_log_records[0].keys()
    assert expected_model_details <= json_log_records[1].keys()
    assert not expected_model_details <= json_log_records[2].keys()


@pytest.mark.parametrize("debug", [True, False])
def test_log_level_gets_persisted(debug: bool, settings: Settings, caplog):
    settings.debug = debug
    configure_logger(settings)

    test_log_message = "foo - bar - this is a test"
    logger.debug(test_log_message)

    if debug:
        assert test_log_message in caplog.text
    else:
        assert test_log_message not in caplog.text
