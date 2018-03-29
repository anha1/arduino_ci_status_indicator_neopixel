#!/usr/bin/python3
import urllib.request
import json
from pathlib import Path
import time
import datetime
import serial
import os
import sys
import time
import configparser
import base64
import codecs
import logging
import signal
import json
import http.server
import socketserver
from http.server import BaseHTTPRequestHandler
from urllib import parse
import json
import threading
import pystache
import math

logging.basicConfig(level=logging.INFO)

config = configparser.ConfigParser()
config.read('/etc/ci-status-neopixel/settings.ini')

failed_projects_global = []

if config['http']['enabled'] == 'True':
    port = int(config['http']['port'])

    class GetHandler(BaseHTTPRequestHandler):

        def do_GET(self):

            template = ""
            with open(config['http']['template'], 'r') as template_file:
                template = template_file.read()

            message = pystache.render(template, {
                'projects': failed_projects_global
            })

            self.send_response(200)
            self.send_header('Content-Type',
                             'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(message.encode('utf-8'))

    server = socketserver.TCPServer(("", port), GetHandler)
    logging.info("serving at port %d" % port)
    thread = threading.Thread(target=server.serve_forever)
    thread.setDaemon(True)
    thread.start()

bamboo_url = "%s/rest/api/latest/result.json?os_authType=basic" % config['bamboo']['url']
bamboo_credentials = "%s:%s" % (
    config['bamboo']['username'], config['bamboo']['password'])
bamboo_auth_header = "Basic %s" % (
    (base64.b64encode(bytes(bamboo_credentials, "utf-8"))).decode('ascii'))
bamboo_blacklist_keys = json.loads(config['bamboo']['blacklist_keys'])
bamboo_highlight_keys = json.loads(config['bamboo']['highlight_keys'])

logging.info("Blacklisted keys: %s", bamboo_blacklist_keys)
logging.info("Highlighted keys: %s", bamboo_highlight_keys)

def get_ci_failed():
    request = urllib.request.Request(bamboo_url)
    request.add_header("Authorization", bamboo_auth_header)
    ci_response = urllib.request.urlopen(request,
                                         timeout=config['bamboo'].getint('request_timeout_seconds')).read().decode('utf-8')

    body = json.loads(ci_response)

    failed = {}
    for entry in body['results']['result']:
        plan = entry['plan']
        if plan['enabled'] and entry['buildState'] == 'Failed':
                logging.info('Failed build: [%s] %s' %
                             (plan['key'], plan['name']))
                failed[plan['key']] = plan['name']

    return failed

def get_tty_device():
    for device in os.listdir("/dev/"):
        if device.startswith("ttyUSB"):
            return "/dev/" + device

    raise Exception('Cant detect NeoPixel Controler')

def open_controller():
    tty = get_tty_device()
    logging.info("Using serial: %s" % tty)

    # Arduino restarts on this operation, so serial should be always opened
    logging.info("Trying to open a controller")
    return serial.Serial(
        port=tty,
        baudrate=config['indicator'].getint('baudrate'),
        timeout=config['indicator'].getint('write_timeout_seconds'))

if config['indicator']['enabled'] == 'True':
    controller = open_controller()
else:
    controller = None    

def set_mode(mode, speed, brightness):
    command = "%d %d %d;" % (mode, speed, brightness)
    logging.info("Command: %s" % command)
    if controller:
        controller.write(command.encode())


def get_command_val(seconds, min_val, max_val, reach_max_val_hours):
    reach_max_val_seconds = 3600. * reach_max_val_hours
    val = max_val * (seconds/reach_max_val_seconds)
    return max(min_val, min(max_val, int(val)))


def is_warn(failed_seconds):
    return failed_seconds < (config['warn'].getint('warn_before_fail_hours') * 3600)


def get_fail_speed(failed_seconds):
    return get_command_val(seconds=failed_seconds,
                           min_val=config['fail'].getint('min_speed'),
                           max_val=config['fail'].getint('max_speed'),
                           reach_max_val_hours=config['fail'].getint('max_speed_reached_hours'))


def get_fail_brightness(failed_seconds):
    return get_command_val(seconds=failed_seconds,
                           min_val=config['fail'].getint('min_brightness'),
                           max_val=config['fail'].getint('max_brightness'),
                           reach_max_val_hours=config['fail'].getint('max_brightness_reached_hours'))


def get_failed_projects():
    now = round(time.time())

    logging.info("Reading CI status...")

    red_ci_since_file = Path(config['misc']['failed_since_file_path'])

    try:
        ci_failed = get_ci_failed()
    except Exception as e:
        logging.error(e)
        return

    failed_projectes = []

    if ci_failed:
        red_since_old = {}
        if red_ci_since_file.exists():
            with red_ci_since_file.open() as f:
                red_since_old = json.loads(f.readline())

        red_since_new = {}
        for key in ci_failed:
            if key in red_since_old:
                red_since_new[key] = red_since_old[key]
                curr_red_for = now - red_since_old[key]
            else:
                red_since_new[key] = now
                curr_red_for = 1

            failed_projectes.append({
                'failed_seconds': int(curr_red_for),
                'failed_description': seconds_to_description(int(curr_red_for)),
                'key': key,
                'highlight': key in bamboo_highlight_keys,
                'blacklist': key in bamboo_blacklist_keys,
                'name': ci_failed[key]
            })

        with red_ci_since_file.open(mode='w') as f:
            f.write(json.dumps(red_since_new))
    else:
        if red_ci_since_file.exists():
            red_ci_since_file.unlink()

    return sorted(failed_projectes, key=lambda item: (-item['blacklist'], item['highlight'], item['failed_seconds']), reverse=True)

def seconds_to_hours(seconds):
    return (float(seconds) / 3600.)


def seconds_to_description(seconds):
    hours = math.floor(seconds / 3600.)
    minutes = math.floor((seconds - 3600 * hours) / 60)
    if hours > 0:
        return "%s h %s m" % (hours, minutes)
    else:
        return "%s m" % (minutes)


def apply_failed_projects_to_indicator(failed_projects):

    max_failed_seconds = 0

    for failed_project in failed_projects:
        if failed_project['failed_seconds'] > max_failed_seconds and not failed_project['blacklist']:
            max_failed_seconds = failed_project['failed_seconds']

    logging.info('Failing for: %f h' % seconds_to_hours(max_failed_seconds))

    if max_failed_seconds > 0:
        if is_warn(max_failed_seconds):
            set_mode(mode=2,
                     speed=get_fail_speed(max_failed_seconds),
                     brightness=1)
            logging.info('Final status: WARN')
        else:
            set_mode(mode=3,
                     speed=get_fail_speed(max_failed_seconds),
                     brightness=get_fail_brightness(max_failed_seconds))
            logging.info('Final status: FAIL')
    else:
        logging.info('Final status: OK')
        set_mode(mode=1,
                 speed=1,
                 brightness=1)


time.sleep(5)  # giving an Arduino some to be ready to receive a command

while True:
    failed_projects = get_failed_projects()

    failed_projects_global = failed_projects

    apply_failed_projects_to_indicator(failed_projects)
    time.sleep(config['misc'].getint('poling_interval_seconds'))