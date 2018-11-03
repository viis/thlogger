from collections import namedtuple
from unittest.mock import MagicMock, patch
import tempfile
import json
import pytest
import os
import sys
from requests.exceptions import ConnectionError

sys.modules["Adafruit_DHT"] = MagicMock()
from thlogger import THLogger  # noqa

CONFIG_FILE_PATH = "thlogger.conf.example"
NETWORK_RESTARTED = False


def init_logger(config_file_path=None):
    Args = namedtuple("Args", ["CONFIG_FILE", "MAX_CONNECTION_RETRIES"])
    if not config_file_path:
        config_file_path = CONFIG_FILE_PATH
    args = Args(config_file_path, 1)
    thlogger = THLogger(args)

    # reduce sleep to speed up tests runtime
    thlogger.SLEEP_BETWEEN_READINGS = 0.1

    return thlogger


def raise_keyboardinterrupt():
    raise KeyboardInterrupt


def conditionally_raise_connectionerror():
    if not NETWORK_RESTARTED:
        raise ConnectionError
    return [{"name": "thlogger"}, {"name": "test"}]


def raise_exception():
    raise Exception


def set_network_restarted(*args):
    global NETWORK_RESTARTED
    NETWORK_RESTARTED = True


@patch("thlogger.THLogger.init_db_connection", return_value=None)
def test_init(mock_init_db):
    thlogger = init_logger()
    assert isinstance(thlogger, THLogger)
    assert thlogger.CONFIG_FILE == CONFIG_FILE_PATH
    assert thlogger.SENSOR_MODEL == 11
    assert thlogger.GPIO_PIN == 17
    assert thlogger.HOST == "localhost"
    assert thlogger.PORT == 8086
    assert thlogger.DATABASE == "thlogger"
    assert thlogger.LOCATION == "garage"
    assert thlogger.SLEEP_BETWEEN_READINGS == 0.1
    assert thlogger.measurements == []

    # test exception if config path is wrong
    assert mock_init_db.called
    with pytest.raises(Exception) as e:
        thlogger = init_logger("does_not_exist")
    assert "Error opening" in str(e.value)

    # test fallback to basic config for logging
    with open(CONFIG_FILE_PATH) as f:
        config = json.load(f)
        del config["LOG_CONFIG"]
    temp_file_name = None
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
        tf.write(json.dumps(config))
        temp_file_name = tf.name
    thlogger = init_logger(temp_file_name)
    os.remove(temp_file_name)


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", return_value=None)
def test_read_write(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    thlogger.work(max_iterations=1)
    assert mock_read.called
    assert mock_list_dbs.called
    assert not mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.called
    assert len(thlogger.measurements) == 0


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "test"}, {"name": "test2"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", return_value=None)
def test_create_database(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    thlogger.work(max_iterations=1)
    assert mock_read.called
    assert mock_list_dbs.called
    assert mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.called
    assert len(thlogger.measurements) == 0


@patch("Adafruit_DHT.read_retry", return_value=(None, None))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", return_value=None)
def test_handle_failed_read(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    thlogger.work(max_iterations=2)
    assert mock_read.call_count == 2
    assert mock_list_dbs.called
    assert not mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.call_count == 0
    assert len(thlogger.measurements) == 0


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", side_effect=raise_exception)
def test_handle_failed_write(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    thlogger.work(max_iterations=2)
    assert mock_list_dbs.call_count == 1
    assert not mock_create_db.called
    assert mock_switch_db.call_count == 1
    assert mock_read.call_count == 2
    assert mock_write.call_count == 2
    assert len(thlogger.measurements) == 2


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", side_effect=raise_exception)
@patch("thlogger.THLogger.restart_networking", return_value=None)
def test_write_failure_threshold(
    mock_restart_networking,
    mock_write,
    mock_switch_db,
    mock_create_db,
    mock_list_dbs,
    mock_read,
):
    thlogger = init_logger()
    thlogger.work(max_iterations=2, write_failure_threshold=1)
    assert mock_list_dbs.call_count == 1
    assert not mock_create_db.called
    assert mock_switch_db.call_count == 1
    assert mock_read.call_count == 2
    assert mock_write.call_count == 2
    assert len(thlogger.measurements) == 2
    assert mock_restart_networking.call_count == 1


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("thlogger.THLogger.write_measurements", side_effect=raise_keyboardinterrupt)
def test_keyboard_interrupt(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    with pytest.raises(KeyboardInterrupt):
        thlogger.work(max_iterations=2)


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    return_value=[{"name": "thlogger"}, {"name": "test"}],
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("thlogger.THLogger.write_measurements", side_effect=raise_exception)
def test_other_exception_handling(
    mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read
):
    thlogger = init_logger()
    thlogger.work(max_iterations=2)
    assert mock_read.call_count == 2
    assert mock_list_dbs.called
    assert not mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.call_count == 2
    assert len(thlogger.measurements) == 2


@patch("Adafruit_DHT.read_retry", return_value=(50, 20))
@patch(
    "influxdb.InfluxDBClient.get_list_database",
    side_effect=conditionally_raise_connectionerror,
)
@patch("influxdb.InfluxDBClient.create_database", return_value=None)
@patch("influxdb.InfluxDBClient.switch_database", return_value=None)
@patch("influxdb.InfluxDBClient.write_points", return_value=None)
@patch("subprocess.call", side_effect=set_network_restarted)
def test_network_restart(
    mock_system_call,
    mock_write,
    mock_switch_db,
    mock_create_db,
    mock_list_dbs,
    mock_read,
):
    thlogger = init_logger()
    thlogger.work(max_iterations=1)
    assert mock_list_dbs.call_count == 2
    assert mock_create_db.call_count == 0
    assert mock_switch_db.call_count == 1
    assert mock_system_call.call_count == 2
