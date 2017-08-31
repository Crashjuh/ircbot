from modules import Module

from datetime import datetime
from dateutil.tz import tzlocal
import dateutil.parser
# import re
import logging

import paho.mqtt.client as mqtt
import json

class tkkrlab(Module):
    CFG_KEY_STATE = 'space_state'
    CFG_KEY_STATE_TIME = 'space_state_time'
    CFG_KEY_STATE_NICK = 'space.state.nick'
    CFG_KEY_TEXT_OPEN = 'text.space_open'
    CFG_KEY_TEXT_CLOSED = 'text.space_closed'

    DEFAULT_TEXT_OPEN = 'We zijn open'
    DEFAULT_TEXT_CLOSED = 'We zijn dicht'

    class SpaceStatus:
        def __init__(self, space_open, time, who):
            self.open = space_open
            self.time = time
            self.who = who

    """Bot module to do tkkrlab things"""
    def start(self):
        status_history = self.get_config('space_state_history', False)
        if status_history:
            self.space_status_history = [f.split(':') for f in status_history.split(',')]

        try:
            cfg_state = self.get_config(self.CFG_KEY_STATE) == '1'
        except:
            cfg_state = False
        try:
            cfg_time = dateutil.parser.parse(self.get_config(self.CFG_KEY_STATE_TIME), tzinfos={'CET': 3600, 'CEST': 7200})
        except:
            cfg_time = None
        try:
            cfg_who = self.get_config(self.CFG_KEY_STATE_NICK)
        except:
            cfg_who = None

        self.status = tkkrlab.SpaceStatus(cfg_state, cfg_time, cfg_who)

        try:
            self.mqtt_config = json.loads(self.get_config('mqtt_config'))
        except:
            self.mqtt_config = {}

        mqtt_args = {}
        if 'client_id' in self.mqtt_config:
            mqtt_args['client_id'] = self.mqtt_config['client_id']

        self.mqtt_client = mqtt.Client(**mqtt_args)

        if 'userdata' in self.mqtt_config:
            self.mqtt_client.user_data_set(self.mqtt_config['userdata'])

        if 'auth' in self.mqtt_config:
            username = self.mqtt_config['auth']['username']
            password = self.mqtt_config['auth']['password']
            self.mqtt_client.username_pw_set(username, password)

        if self.mqtt_config:
            self.mqtt_client.on_connect = self.mqtt_on_connect
            self.mqtt_client.on_message = self.mqtt_on_message
            self.mqtt_client.connect_async(self.mqtt_config['host'])
            self.mqtt_client.loop_start()

    def stop(self):
        if self.mqtt_client:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logging.info('mqtt_connect')
        client.subscribe(userdata['status_topic'])

    def mqtt_on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode('utf-8')
        except UnicodeDecodeError:
            logging.warning('Error: cannot decode payload "{}"!'.format(message.payload))
            return
        logging.debug('mqtt_message, topic: {}, payload: {}'.format(message.topic, payload))

        if message.topic == userdata['status_topic']:
            try:
                self.set_space_status(payload == '1', None, 'switch')
            except:
                pass

    def admin_cmd_force_status(self, source, raw_args, **kwargs):
        """!force_status <0|1>: force space status to closed/open"""
        if len(raw_args) == 0: return
        logging.debug('force_status: {}'.format(raw_args))
        new_status = raw_args[0] == '1'

        if self.mqtt_config:
            self.mqtt_client.publish(self.mqtt_config['status_topic'], '1' if new_status else '0', retain=True)
        else:
            return ['Cannot set status, MQTT not configured.']

    def cmd_status(self, raw_args, target, **kwargs):
        """!status: to get open/close status of the space"""
        if 'lock' in raw_args:
            self.privmsg(target, '!lockstatus')
            return
        open_text = 'Open' if self.status.open else 'Closed'
        time = self.status.time.strftime('%a, %d %b %Y %H:%M:%S %Z') if self.status.time else '<unknown>'
        if self.status.who:
            return ['We are {0} since {1} by {2}'.format(open_text, time, self.status.who)]
        else:
            return ['We are {0} since {1}'.format(open_text, time)]

    def set_space_status(self, status, aTime=None, who=None):
        if aTime is None:
            aTime = datetime.now().replace(tzinfo=tzlocal())

        self.status.open = status
        self.status.time = aTime
        self.status.who = who
        logging.debug('set_space_status [open: {}, who: {}]'.format(self.status.open, self.status.who))

        self.__save_config()

        self.notice(self.__get_channel(), self.__get_state_text())

    def __save_config(self):
        self.set_config(self.CFG_KEY_STATE, self.status.open)
        self.set_config(self.CFG_KEY_STATE_TIME, self.status.time.strftime('%Y-%m-%dT%H:%M:%S %Z'))
        self.set_config(self.CFG_KEY_STATE_NICK, self.status.who)

    def __get_channel(self):
        return self.get_config('main_channel', '#tkkrlab')

    def __get_state_text(self):
        key = self.CFG_KEY_TEXT_OPEN if self.status.open else self.CFG_KEY_TEXT_CLOSED
        default = self.DEFAULT_TEXT_OPEN if self.status.open else self.DEFAULT_TEXT_CLOSED
        return self.get_config(key, default)
