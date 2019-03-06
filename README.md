[![Build Status](https://travis-ci.com/viis/thlogger.svg?branch=master)](https://travis-ci.com/viis/thlogger)
[![codecov](https://codecov.io/gh/viis/thlogger/branch/master/graph/badge.svg)](https://codecov.io/gh/viis/thlogger)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# thlogger
Data logger for use with [Raspberry Pi](https://www.raspberrypi.org)
and [DHT sensors](https://learn.adafruit.com/dht/overview).

Logs temperature and humidity to [InfluxDB](https://github.com/influxdata/influxdb). Visualization with
[Grafana](https://grafana.com).

Runs on any Raspberry Pi model.

# Installation

## Setup InfluxDB and Grafana

You'll need an always on computer to run your database. I'd recommend a Linux server. If you don't have one already,
you could use an old repurposed laptop, or a VPS (these start at around $5/month).

To make this as easy as possible, we'll use Docker.

* [Install Docker](https://docs.docker.com/install/#supported-platforms)

* Clone this repository

```bash
git clone https://github.com/viis/thlogger.git
cd thlogger
```

* Rename and add a password to the `influxdb.env` file

```bash
mv influxdb.env.example influxdb.env
# edit influxdb.env
```

* Create a directory for the database files (shared between the host and the container)

```bash
mkdir vol
```

* Start the docker containers

```bash
docker-compose up -d
```

InfluxDB is now accessible on your server's port 8086 and Grafana on 8080.

## Setup your RPi

### Hardware

**NOTE** There are a few different variants of the DHT sensors. This guide assumes you are using one with an internal
pull up resistor. If you aren't, Google is your friend :)

DHT sensors have 3 pins, labelled +, out and -. Connect them to 5V, a data pin and Ground, respectively. I used pins
2 (5V), 11 (data), and 6 (Ground). Note that pin 11 is GPIO pin number 17 (you'll need that number in your config
later). [Pinout.xyz](https://pinout.xyz) is a useful reference for the RPi GPIO layout. If you are using a RPi 1,
you'll only have the first 26 pins, but that is enough for this project.

**IMAGE**

### Operating system

* Download the [latest Raspian Lite image](https://downloads.raspberrypi.org/raspbian_lite_latest)

* Load the image onto your RPi's SD card with a tool like [Etcher](https://www.balena.io/etcher/)

### Wireless networking

**If your RPi has a wired network connection, skip this step**

* When the image is loaded, remove the SD card from your computer and re-insert it

* In the root if the SD card, create an empty file called `ssh`

* In the root if the SD card, create a file called `wpa_supplicant.conf` with the following contents:

```
country=DK
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="NETWORK-NAME"
    psk="NETWORK-PASSWORD"
}
```

**REMEMBER to replace NETWORK-NAME and NETWORK-PASSCODE with your network name and code**

**You can also replace DK with the country you're in**

### Boot and access your RPi

* Insert the SD card into the Pi and boot it by connecting it to a power source

* Find the RPi on your network with [nmap](https://nmap.org/download.html) (replace 192.168.1 with your network's
address)

```bash
sudo nmap -sS -p 22 192.168.1.1/24
```

The RPi should show up with the `Raspberry Pi Foundation` next to its MAC address. Note the IP address.

* Connect via ssh

The default password is `raspberry`, you should change it when your log in for the first time.

```bash
ssh pi@IP_ADDRESS
```

### Upgrade your RPi and install required packages

```bash
sudo apt update
sudo apt upgrade
sudo apt install git python3-pip
```

### Install thlogger

You'll need to update the `thlogger.conf` before starting the service.


* Clone this repository and edit the config file

```bash
git clone https://github.com/viis/thlogger.git
cd thlogger
cp thlogger.conf.example thlogger.conf
# edit thlogger.conf
```

The config consists of the following:

```
"SENSOR_MODEL": 11, 22, or 2302 (depending on which sensor you have)
"GPIO_PIN": The GPIO pin the sensor is connected to (17 if you followed the guide above)
"HOST": InfluxDB server IP address
"PORT": InfluxDB port (usually 8086)
"DATABASE": InfluxDB database name (thlogger)
"DB_USER": InfluxDB username (thlogger)
"DB_PASS": InfluxDB password (what you wrote in influxdb.env above)
"LOCATION": Location of your logger (garage, attic, etc)
"SLEEP_BETWEEN_READINGS": In seconds (60 for a measurement every minute)
```

* Install thlogger as a service

```bash
sudo sh INSTALL
```

The logger is now running as a service on your RPi, and is logging temperature and humidity to your database. The
service starts automatically on boot.

You can view the log file with

```
journalctl -u thlogger
```

### Visualize your measurements with Grafana

Access you Grafana installation on http://your-server-ip:8080

The default admin user/password is admin/admin. You should change the password when you log in for the first time.

Use the setup wizard to setup a data source with the following information:

```
URL: http://influxdb:8086
Database: thlogger
User: thlogger
Password: the password you wrote in influxdb.env above
```

Then setup a dashboard. If you select your newly created data source as the source, you should have measurements for
temperature and humidity available.
