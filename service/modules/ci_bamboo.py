from urllib import parse
import urllib.request
import json
import base64
import logging
from modules.ci_time_utils import seconds2dict
from pathlib import Path
import time
import datetime

class CiBamboo:
    
    def __init__(self, config):
        self.bamboo_url = '%s/rest/api/latest/result.json?os_authType=basic' % config['bamboo']['url']
        self.bamboo_credentials = '%s:%s' % (
            config['bamboo']['username'], config['bamboo']['password'])
        self.bamboo_auth_header = 'Basic %s' % (
            (base64.b64encode(bytes(self.bamboo_credentials, 'utf-8'))).decode('ascii'))
        self.bamboo_blacklist_keys = json.loads(config['bamboo']['blacklist_keys'])
        self.bamboo_highlight_keys = json.loads(config['bamboo']['highlight_keys'])

        self.state_file = Path(config['bamboo']['state_path'])
        self.config = config;

        self.state_old = self.read_state();

        self.save_state_counter = 100000 # flush first state


    def read_ci_failed(self):
        request = urllib.request.Request(self.bamboo_url)
        request.add_header('Authorization', self.bamboo_auth_header)
        ci_response = urllib.request.urlopen(request,
                                            timeout=self.config['bamboo'].getint('request_timeout_seconds')).read().decode('utf-8')

        body = json.loads(ci_response)
       
        failed = {}
        for entry in body['results']['result']:
            plan = entry['plan']
            if plan['enabled'] and entry['buildState'] == 'Failed':
                    logging.debug('Failed build: [%s] %s' %
                                (plan['key'], plan['name']))
                    failed[plan['key']] = plan['name']
        return failed

    def get_status(self):
        now = round(time.time())

        logging.debug('Reading CI status...')

        try:
            ci_failed = self.read_ci_failed()
        except Exception as e:
            logging.error(e)
            return None

        detailed_status = {
            'status_known': True,
            'red_projects': []
        }

       
        state_old = self.state_old

        if not state_old:
            state_old = {
                'red_since': {},
                'green_since': None
            }
                
        red_since_old = state_old['red_since']        

        red_since_new = {}

        max_non_blacklisted_failed_seconds = 0

        red_projects = [];
        
        for key in ci_failed:
            if key in red_since_old:
                red_since_new[key] = red_since_old[key]
                curr_red_for = now - red_since_old[key]
            else:
                red_since_new[key] = now
                curr_red_for = 1

            if not key in self.bamboo_blacklist_keys:
                if max_non_blacklisted_failed_seconds < curr_red_for:
                    max_non_blacklisted_failed_seconds = curr_red_for
            
            red_projects.append({
                'red_for': seconds2dict(curr_red_for),
                'key': key,                
                'highlight': key in self.bamboo_highlight_keys,
                'blacklist': key in self.bamboo_blacklist_keys,
                'name': ci_failed[key]
            })
        
        state_new = {            
            'red_since': red_since_new,
            'green_since': None
        }

        if max_non_blacklisted_failed_seconds == 0:
            if state_old['green_since']:
                state_new['green_since'] = state_old['green_since']
            else:
                state_new['green_since'] = now 
            
            green_for = now - int(state_new['green_since'])
            detailed_status['green_for'] = seconds2dict(green_for)    
        else :            
            detailed_status['red_for'] = seconds2dict(max_non_blacklisted_failed_seconds)

        
        self.state_old = state_new
        self.save_state_counter = self.save_state_counter + 1

        if self.save_state_counter > 10:
            self.save_state_counter = 0
            self.write_state(state_new)

        detailed_status['red_projects'] = sorted(
            red_projects, 
            key=lambda item: (-item['blacklist'], item['highlight'], item['red_for']['seconds']), 
            reverse=True)
        return detailed_status


    def read_state(self):
        state = None
        if self.state_file.exists():
            with self.state_file.open() as f:
                state = json.loads(f.readline())
                f.close()
        return state;

    def write_state(self, state):
        with self.state_file.open(mode='w') as f:
            f.write(json.dumps(state))
            f.close()

