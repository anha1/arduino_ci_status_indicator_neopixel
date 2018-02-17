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
import struct
import logging
import signal
logging.basicConfig(level=logging.INFO)

config = configparser.ConfigParser()
config.read('/etc/ci-status-neopixel/settings.ini')

bamboo_url = "%s/rest/api/latest/result.json?os_authType=basic" % config['bamboo']['url']
credentials = "%s:%s" % (config['bamboo']['username'], config['bamboo']['password'])
bamboo_auth_header = "Basic %s" % ((base64.b64encode( bytes(credentials, "utf-8"))).decode('ascii'))

def is_ci_failed() :
    request = urllib.request.Request(bamboo_url)    
    request.add_header("Authorization", bamboo_auth_header)
    ci_response = urllib.request.urlopen(request, 
                                         timeout=config['bamboo'].getint('request_timeout_seconds')).read().decode('utf-8')
    
    body = json.loads(ci_response)

    is_any_failed_builds = False

    for result in body['results']['result']:
        plan = result['plan']
        if plan['enabled'] and result['buildState'] == 'Failed':
            logging.info('Failed build: %s' % plan['name'] )
            is_any_failed_builds = True
    return is_any_failed_builds

def get_tty_device():
    for device in os.listdir("/dev/"):
        if device.startswith("ttyUSB"):
            return "/dev/" + device

    raise Exception('Cant detect NeoPixel Controler')

def open_controller():
    tty = get_tty_device()
    logging.info("Using serial: %s" %  tty)

    # Arduino restarts on this operation, so serial should be always opened
    logging.info("Trying to open a controller")
    return serial.Serial(
        port=tty,
        baudrate=config['indicator'].getint('baudrate'),
        timeout=config['indicator'].getint('write_timeout_seconds'))

controller = open_controller() 

def set_mode(mode, speed, brightness):  
    logging.info("Command>%d %d %d;" % (mode, speed, brightness))
    controller.write(struct.pack("BBB", mode, speed, brightness))

def get_command_val(seconds, min_val, max_val, reach_max_val_minutes):
    reach_max_val_seconds = 60. * reach_max_val_minutes;		
    val = max_val * (seconds/reach_max_val_seconds)
    return max(min_val, min(max_val, int(val))) 

def is_warn(failed_seconds):
    return failed_seconds < (config['warn'].getint('warn_before_fail_minutes') * 60)

def get_fail_speed(failed_seconds):
    return get_command_val(seconds=failed_seconds, 
                   min_val=config['fail'].getint('min_speed'), 
                   max_val=config['fail'].getint('max_speed'), 
                   reach_max_val_minutes=config['fail'].getint('max_speed_reached_in_minutes'))

def get_fail_brightness(failed_seconds):
    return get_command_val(seconds=failed_seconds, 
                min_val=config['fail'].getint('min_brightness'), 
                max_val=config['fail'].getint('max_brightness'), 
                reach_max_val_minutes=config['fail'].getint('max_brightness_reached_in_minutes'))

def do_read_and_apply_status():
    
    now = round(time.time())

    logging.info("Reading CI status...")

    red_ci_since_file = Path(config['misc']['failed_since_file_path'])
    
    try:
        is_ci_failed_now = is_ci_failed()
    except Exception as e:
        logging.error(e)
        return
    
    if is_ci_failed():        
        seconds_failed = 0;
        if red_ci_since_file.exists():
            with red_ci_since_file.open() as f:
                red_since = int(f.readline())
                seconds_failed = now - red_since;           
        else:
            red_ci_since_file.write_text(str(now))
            
        logging.info('Failing for: %f h' % (float(seconds_failed) / 3600.))
                
        if is_warn(seconds_failed):
            set_mode(mode=2,
                    speed=get_fail_speed(seconds_failed),
                    brightness=1)
            logging.info('Final status: WARN')        
        else:
            set_mode(mode=3,
                    speed=get_fail_speed(seconds_failed),
                    brightness=get_fail_brightness(seconds_failed))
            logging.info('Final status: FAIL')        
    else:
        logging.info('Final status: OK')
        set_mode(mode=1,
                speed=1,
                brightness=1)
        
        if not red_ci_since_file.exists():
            red_ci_since_file.unlink()

time.sleep(5) # giving an Arduino some to be ready to receive a command
while True:
    do_read_and_apply_status()        
    time.sleep(config['misc'].getint('poling_interval_seconds'))         
    
