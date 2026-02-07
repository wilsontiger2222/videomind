# tests/test_logging_config.py
import logging
from app.logging_config import setup_logging


def test_setup_logging_returns_logger():
    logger = setup_logging("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_logger_has_handler():
    logger = setup_logging("test_handler")
    assert len(logger.handlers) > 0


def test_logger_level_is_info():
    logger = setup_logging("test_level")
    assert logger.level == logging.INFO
