#!/usr/bin/python3

import json


import sys
import time
import configparser
import codecs
import logging
from modules.ci_http import CiHttpServer
from modules.ci_neopixel_controller import CiNeopixelController
from modules.ci_bamboo import CiBamboo

logging.basicConfig(level=logging.DEBUG)

config = configparser.ConfigParser()
config.read('/etc/ci-status-neopixel/settings.ini')

server = None
if config['http']['enabled'] == 'True':
    server = CiHttpServer(config)
    server.start()

controller = None
if config['indicator']['enabled'] == 'True':
    controller = CiNeopixelController(config)
    time.sleep(1)

bamboo = CiBamboo(config)    

fail_count = 0

while True:
    status = bamboo.get_status()
    if status:
        fail_count = 0
        server.set_status(status)
        if 'red_for' in status:
            controller.set_seconds_failed(status['red_for']['seconds'])   
        else:
            controller.set_seconds_failed(-status['green_for']['seconds'])      
    else:   
        logging.info('Can\'t read detailed status')
        fail_count = fail_count + 1
        if fail_count > 10:
            controller.set_disconnected()
            server.set_status({}) 

    time.sleep(config['misc'].getint('poling_interval_seconds'))
