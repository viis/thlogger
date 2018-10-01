from collections import namedtuple
from unittest.mock import MagicMock, patch
import sys
sys.modules['Adafruit_DHT'] = MagicMock()
from thlogger import THLogger  # noqa

CONFIG_FILE_PATH = 'thlogger.conf.example'


def init_logger():
    Args = namedtuple('Args', 'CONFIG_FILE')
    args = Args(CONFIG_FILE_PATH)
    thlogger = THLogger(args)

    # reduce sleep to speed up tests runtime
    thlogger.SLEEP_BETWEEN_READINGS = 0.1

    return thlogger


@patch('thlogger.THLogger.init_db_connection', return_value=None)
def test_init(mock_init_db):
    thlogger = init_logger()
    assert isinstance(thlogger, THLogger)
    assert thlogger.CONFIG_FILE == CONFIG_FILE_PATH
    assert thlogger.SENSOR_MODEL == 11
    assert thlogger.GPIO_PIN == 17
    assert thlogger.HOST == 'localhost'
    assert thlogger.PORT == 8086
    assert thlogger.DATABASE == 'thlogger'
    assert thlogger.LOCATION == 'garage'
    assert thlogger.SLEEP_BETWEEN_READINGS == 0.1
    assert thlogger.measurements == []
    assert mock_init_db.called


@patch('Adafruit_DHT.read_retry', return_value=(50, 20))
@patch('influxdb.InfluxDBClient.get_list_database', return_value=[{'name': 'thlogger'}, {'name': 'test'}])
@patch('influxdb.InfluxDBClient.create_database', return_value=None)
@patch('influxdb.InfluxDBClient.switch_database', return_value=None)
@patch('influxdb.InfluxDBClient.write_points', return_value=None)
def test_read_write(mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read):
    thlogger = init_logger()
    thlogger.work(max_iterations=1)
    assert mock_read.called
    assert mock_list_dbs.called
    assert not mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.called
    assert len(thlogger.measurements) == 0


@patch('Adafruit_DHT.read_retry', return_value=(50, 20))
@patch('influxdb.InfluxDBClient.get_list_database', return_value=[{'name': 'test'}, {'name': 'test2'}])
@patch('influxdb.InfluxDBClient.create_database', return_value=None)
@patch('influxdb.InfluxDBClient.switch_database', return_value=None)
@patch('influxdb.InfluxDBClient.write_points', return_value=None)
def test_create_database(mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read):
    thlogger = init_logger()
    thlogger.work(max_iterations=1)
    assert mock_read.called
    assert mock_list_dbs.called
    assert mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.called
    assert len(thlogger.measurements) == 0


def mock_write_points():
    raise Exception


@patch('Adafruit_DHT.read_retry', return_value=(50, 20))
@patch('influxdb.InfluxDBClient.get_list_database', return_value=[{'name': 'thlogger'}, {'name': 'test'}])
@patch('influxdb.InfluxDBClient.create_database', return_value=None)
@patch('influxdb.InfluxDBClient.switch_database', return_value=None)
@patch('influxdb.InfluxDBClient.write_points', side_effect=mock_write_points)
def test_handle_failed_write(mock_write, mock_switch_db, mock_create_db, mock_list_dbs, mock_read):
    thlogger = init_logger()
    thlogger.work(max_iterations=2)
    assert mock_read.call_count == 2
    assert mock_list_dbs.called
    assert not mock_create_db.called
    assert mock_switch_db.called
    assert mock_write.call_count == 2
    assert len(thlogger.measurements) == 2
