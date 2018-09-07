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
        # assign args to object attributes
        for k, v in vars(args).items():
            setattr(self, k, v)

        # set up config
        if os.path.exists(self.LOG_CONFIG):
            with open(self.LOG_CONFIG) as f:
                logging_config = json.load(f)
            logging.config.dictConfig(logging_config)
        else:
            logging.basicConfig(level='INFO')
        self.logger = logging.getLogger(__name__)

        self.SENSOR = self.SENSORS[self.SENSOR_MODEL]
        self.logger.info('INIT SENSOR MODEL %s', self.SENSOR)
        self.logger.info('USING PIN %s', self.SENSOR_PIN)
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
                                         for reading in Adafruit_DHT.read_retry(self.SENSOR, self.SENSOR_PIN)]
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
    parser.add_argument('-m', '--sensor-model', dest='SENSOR_MODEL', help='Model of DHT sensor used', type=int,
                        required=True, choices=[11, 22, 2302])
    parser.add_argument('-P', '--sensor-pin', dest='SENSOR_PIN', help='GPIO pin used for sensor', type=int,
                        required=True)
    parser.add_argument('-H', '--host', dest='HOST', help='InfluxDB host', required=True)
    parser.add_argument('-p', '--port', dest='PORT', help='InfluxDB port', type=int, default=8086)
    parser.add_argument('-d', '--database', dest='DATABASE', help='InfluxDB database', required=True)
    parser.add_argument('-c', '--config', dest='LOG_CONFIG', help='Log config file',
                        default='/etc/thlogger/thlogger.conf')
    parser.add_argument('-s', '--sleep', dest='SLEEP_BETWEEN_READINGS', help='Time to sleep between readings (s)',
                        type=int, default=60)
    parser.add_argument('-l', '--location', dest='LOCATION', help='Location of logger', required=True)
    args = parser.parse_args()

    thlogger = THLogger(args)
    thlogger.work()
