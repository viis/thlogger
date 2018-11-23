from time import sleep
import datetime
import logging.config
import os
import json
from argparse import ArgumentParser
import subprocess
import Adafruit_DHT
from influxdb import InfluxDBClient
from tenacity import retry, retry_if_exception_type, wait_fixed, wait_chain
from requests.exceptions import ConnectionError


class THLogger:
    SENSORS = {
        11: Adafruit_DHT.DHT11,
        22: Adafruit_DHT.DHT22,
        2302: Adafruit_DHT.AM2302,
    }

    def __init__(self, args):
        # container for the measurements
        self.measurements = []

        # init counter for connection retries
        self.CONNECTION_RETRIES = 0
        # default to 10 retries
        self.MAX_CONNECTION_RETRIES = getattr(args, "MAX_CONNECTION_RETRIES", 10)

        # read config file
        self.CONFIG_FILE = args.CONFIG_FILE
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE) as f:
                self.CONFIG = json.load(f)
        else:
            raise Exception("Error opening config file {}".format(self.CONFIG_FILE))

        # assign config items to object attributes
        for k, v in self.CONFIG.items():
            setattr(self, k, v)

        # set up config
        if hasattr(self, "LOG_CONFIG") and self.LOG_CONFIG:
            logging.config.dictConfig(self.LOG_CONFIG)
        else:
            logging.basicConfig(level="INFO")
        self.logger = logging.getLogger(__name__)
        self.logger.info("INITIALIZING")

        self.SENSOR = self.SENSORS[self.SENSOR_MODEL]
        self.logger.info("SENSOR MODEL %s", self.SENSOR)
        self.logger.info("GPIO PIN %s", self.GPIO_PIN)
        self.logger.info("LOCATION %s", self.LOCATION)

        # init influxdb client
        self.client = None
        self.logger.info("INIT InfluxDB connection")
        self.init_db_connection()

    @retry(
        retry=retry_if_exception_type(ConnectionError),
        wait=wait_chain(*[wait_fixed(0.1) for i in range(1)] + [wait_fixed(10)]),
    )
    def init_db_connection(self):
        self.CONNECTION_RETRIES += 1
        if self.CONNECTION_RETRIES > self.MAX_CONNECTION_RETRIES:
            self.restart_networking()
            self.CONNECTION_RETRIES = 0

        databases = []
        self.logger.debug("CONNECTING TO %s:%s", self.HOST, self.PORT)
        self.client = InfluxDBClient(self.HOST, self.PORT, self.DB_USER, self.DB_PASS)
        databases = [d.get("name") for d in self.client.get_list_database()]
        self.logger.debug("AVAILABLE DATABASES %s", databases)

        if self.DATABASE not in databases:
            self.client.create_database(self.DATABASE)
            self.logger.info("CREATED DATABASE %s", self.DATABASE)
        self.client.switch_database(self.DATABASE)
        self.logger.info("USE DATABASE %s", self.DATABASE)

    def restart_networking(self):
        self.logger.info("RESTARTING NETWORKING")
        subprocess.call(["systemctl", "daemon-reload"])
        subprocess.call(["systemctl", "restart", "dhcpcd"])

    def write_measurements(self):
        # write measurements to db
        for measurement in self.measurements:
            json_body = [
                {
                    "measurement": "temperature",
                    "tags": {"location": self.LOCATION},
                    "time": str(measurement["timestamp"]),
                    "fields": {"value": measurement["temperature"]},
                },
                {
                    "measurement": "humidity",
                    "tags": {"location": self.LOCATION},
                    "time": str(measurement["timestamp"]),
                    "fields": {"value": measurement["humidity"]},
                },
            ]
            self.logger.debug("JSON: %s", json_body)
            self.client.write_points(json_body)
            self.logger.info(
                "Temp: %d C, hum: %d %%",
                measurement["temperature"],
                measurement["humidity"],
            )
        self.logger.debug("Wrote %d measurement(s)" % len(self.measurements))
        self.measurements = []

    def work(self, max_iterations=None, write_failure_threshold=10):
        iterations = 0
        stop = False
        while not stop:
            try:
                humidity, temperature = [
                    int(reading) if reading else None
                    for reading in Adafruit_DHT.read_retry(self.SENSOR, self.GPIO_PIN)
                ]
                if humidity is not None and temperature is not None:
                    ts = datetime.datetime.now(datetime.timezone.utc)
                    measurement = {
                        "timestamp": ts,
                        "temperature": temperature,
                        "humidity": humidity,
                    }
                    self.logger.debug("MEASURED %s" % measurement)
                    self.measurements.append(measurement)
                    self.write_measurements()
                else:
                    self.logger.warning("FAILED TO GET A READING")
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                self.logger.error(e)

                # if failure threshold is reached, try restarting
                # the network to re-connect WiFi
                if (
                    write_failure_threshold is not None
                    and len(self.measurements) > write_failure_threshold
                ):
                    self.restart_networking()

            sleep(self.SLEEP_BETWEEN_READINGS)
            iterations += 1
            if max_iterations and iterations >= max_iterations:
                stop = True


if __name__ == "__main__":  # pragma: no cover
    parser = ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        dest="CONFIG_FILE",
        help="Path to config file",
        default="/etc/thlogger/thlogger.conf",
    )
    args = parser.parse_args()

    thlogger = THLogger(args)
    thlogger.work()
