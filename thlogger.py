from time import sleep
import datetime
import logging.config
import os
import json
from argparse import ArgumentParser
import Adafruit_DHT
from influxdb import InfluxDBClient


class THLogger:
    SENSORS = {11: Adafruit_DHT.DHT11,
               22: Adafruit_DHT.DHT22,
               2302: Adafruit_DHT.AM2302}

    def __init__(self, args):
        # read config file
        self.CONFIG_FILE = args.CONFIG_FILE
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE) as f:
                self.CONFIG = json.load(f)
        else:
            raise Exception('Error opening config file {}'.format(self.CONFIG_FILE))

        # assign config items to object attributes
        for k, v in self.CONFIG.items():
            setattr(self, k, v)

        # set up config
        if hasattr(self, 'LOG_CONFIG') and self.LOG_CONFIG:
            logging.config.dictConfig(self.LOG_CONFIG)
        else:
            logging.basicConfig(level='INFO')
        self.logger = logging.getLogger(__name__)
        self.logger.info('INITIALIZING')

        self.SENSOR = self.SENSORS[self.SENSOR_MODEL]
        self.logger.info('SENSOR MODEL %s', self.SENSOR)
        self.logger.info('GPIO PIN %s', self.GPIO_PIN)
        self.logger.info('LOCATION %s', self.LOCATION)

        # init influxdb client
        self.client = InfluxDBClient(self.HOST, self.PORT)
        databases = [d.get('name') for d in self.client.get_list_database()]
        self.logger.debug('AVAILABLE DATABASES %s', databases)
        if self.DATABASE not in databases:
            self.client.create_database(self.DATABASE)
            self.logger.info('CREATED DATABASE %s', self.DATABASE)
        self.client.switch_database(self.DATABASE)
        self.logger.info('INIT InfluxDB connection')
        self.logger.info('USE DATABASE %s', self.DATABASE)

    def work(self):
        while True:
            try:
                humidity, temperature = [int(reading) if reading else None
                                         for reading in Adafruit_DHT.read_retry(self.SENSOR, self.GPIO_PIN)]
                if humidity is not None and temperature is not None:
                    ts = datetime.datetime.now(datetime.timezone.utc)
                    json_body = [
                        {
                            "measurement": "temperature",
                            "tags": {
                                "location": self.LOCATION
                            },
                            "time": str(ts),
                            "fields": {
                                "value": temperature
                            }
                        },
                        {
                            "measurement": "humidity",
                            "tags": {
                                "location": self.LOCATION
                            },
                            "time": str(ts),
                            "fields": {
                                "value": humidity
                            }
                        }
                    ]
                    self.logger.debug('JSON: %s', json_body)
                    self.client.write_points(json_body)
                    self.logger.info('Temp: %d C, hum: %d %%', temperature, humidity)
                else:
                    self.logger.warning('Failed to get a reading')
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                self.logger.error(e)

            sleep(self.SLEEP_BETWEEN_READINGS)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', dest='CONFIG_FILE', help='Path to config file',
                        default='/etc/thlogger/thlogger.conf')
    args = parser.parse_args()

    thlogger = THLogger(args)
    thlogger.work()
