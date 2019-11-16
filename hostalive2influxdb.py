#!/usr/bin/env python

import argparse
import json
import logging
import subprocess
import time

from influxdb import InfluxDBClient


def execute_ping(hostname, ttl=64):
    process = subprocess.Popen(
        'ping -4 -c 1 -t {ttl} -q {hostname}'.format(
            hostname=hostname,
            ttl=ttl
        ),
        shell=True,
        stdout=subprocess.PIPE
    )
    process.wait()

    return process.returncode == 0


def update(config):
    points = []

    for host in config.get('hosts', {}):
        name, address = host.get('name'), host.get('address')

        logging.debug('Send ping to %s (%s)', name, address)

        is_alive = execute_ping(address)

        if is_alive > 0:
            logging.debug('Host {} is alive'.format(name))
        else:
            logging.debug('Host {} is down'.format(name))

        points.append({
            'measurement': 'ping',
            'tags': {
                'id': name,
                'label': name
            },
            'fields': {
                'value': 1 if is_alive else 0
            }
        })

    if len(points):
        logging.debug('Writing {} point(s) to InfluxDB...'.format(
            len(points)
        ))

        try:
            client = InfluxDBClient(
                host=config.get('influxdb', {}).get('host'),
                port=config.get('influxdb', {}).get('port', 8086),
                username=config.get('influxdb', {}).get('user'),
                password=config.get('influxdb', {}).get('pass'),
                database=config.get('influxdb', {}).get('base'),
            )
            client.write_points(points)

            logging.info('Written {} point(s) to InfluxDB.'.format(
                len(points)
            ))
        except Exception as e:
            logging.error('Unable to write {} point(s) to InfluxDB'.format(
                len(points),
            ))
            logging.exception(e)
            return False

    return True


def main(args):
    # Logging
    logging_level = int(logging.INFO if not args.debug else logging.DEBUG)
    logging.basicConfig(level=logging_level, format='[%(asctime)s] (%(levelname)s) %(message)s')

    # Configuration
    try:
        with open(args.configuration) as f:
            configuration = json.load(f)
    except Exception as e:
        logging.error('Unable to load configuration: %s', str(e))
        logging.exception(e)
        return 1
    
    while True:
        if not update(configuration):
            logging.warning('Error while updating data')
        logging.debug('Waiting %d seconds before next update', args.time)
        time.sleep(args.time)

if '__main__' == __name__:
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--configuration', default='/etc/hostalive2influxdb.json')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug', default=False)
    parser.add_argument('-t', '--time', default=30)

    args = parser.parse_args()

    exit(main(args))
