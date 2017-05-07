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
    CFG_KEY_TOPIC = 'topic'

    DEFAULT_TEXT_OPEN = 'We zijn open'
    DEFAULT_TEXT_CLOSED = 'We zijn dicht'
    DEFAULT_TOPIC = 'See our activities on http://bit.ly/AsJMNc'

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
            self.mqtt_config = None

        self.mqtt_client = mqtt.Client(userdata=self.mqtt_config)

        if self.mqtt_config:
            self.mqtt_client.on_connect = self.mqtt_on_connect
            self.mqtt_client.on_message = self.mqtt_on_message
            self.mqtt_client.connect_async(self.mqtt_config['host'])
            self.mqtt_client.loop_start()
    
    def stop(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logging.info('mqtt_connect')
        client.subscribe(userdata['status_topic'])

    def mqtt_on_message(self, client, userdata, message):
        logging.info('mqtt_message')
        try:
            payload = message.payload.decode('utf-8')
        except UnicodeDecodeError:
            logging.warning('Error: cannot decode payload "{}"!'.format(message.payload))
            return
        logging.debug('topic: {}, payload: {}'.format(message.topic, payload))

        if message.topic == userdata['status_topic']:
            print('status: {}'.format(payload))
            try:
                self.set_space_status(payload == '1', None, 'switch')
            except:
                pass

    # def on_notice(self, source, target, message):
    #     if source.nick.lower() in ('duality', 'jawsper', 'lock-o-matic'):
    #         if message in ('We are open', 'We are closed'):
    #             space_open = message == 'We are open'
    #             self.set_space_status('1' if space_open else '0', None, 'Lock-O-Matic')
    #             return
    #         result = re.search('^(.+) entered the space', message)
    #         if result:
    #             nick = result.group(1)
    #             self.__led_welcome(nick)
    #         elif 'TkkrLab' in message:
    #             result = re.search(':\s+(?P<status>[a-z]+)\s*@\s*(?P<datetime>.*)$', message)
    #             if result:
    #                 status_bool = result.group('status') == 'open'
    #                 status_time = dateutil.parser.parse(result.group('datetime'), dayfirst=True).replace(tzinfo=tzlocal())
    #                 space_open = self.status.open
    #                 space_time = self.status.time
    #                 if space_open != status_bool or not space_time or abs((space_time - status_time).total_seconds()) > 100:
    #                     logging.info( 'Space status too different from Lock-O-Matic status, updating own status' )
    #                     self.set_space_status('1' if status_bool else '0', status_time, 'Lock-O-Matic')

    # def admin_cmd_led_welcome(self, raw_args, **kwargs):
    #     """!led_welcome <nickname>: send welcome message to ledboard"""
    #     if len(raw_args) == 0: return
    #     self.__led_welcome(raw_args)

    # def __led_welcome(self, user):
    #     try:
    #         self.get_module('led').send_welcome(user)
    #     except:
    #         pass

    def admin_cmd_force_status(self, source, raw_args, **kwargs):
        """!force_status <0|1>: force space status to closed/open"""
        if len(raw_args) == 0: return
        logging.debug('force_status: {}'.format(raw_args))
        new_status = raw_args[0] == '1'

        if self.mqtt_config:
            self.mqtt_client.publish(self.mqtt_config['status_topic'], '1' if new_status else '0', retain=True)
        else:
            return ['Cannot set status, MQTT not configured.']
    
    def admin_cmd_force_topic_update(self, **kwargs):
        """!force_topic_update: force topic update"""
        self.__set_default_topic()
        
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

    # def cmd_virtueleknop(self, source, **kwargs):
    #     """!virtueleknop: toggles space status"""
    #     self.set_space_status(not self.status.open, None, source)

    def set_space_status(self, status, aTime=None, who=None):
        if aTime is None:
            aTime = datetime.now().replace(tzinfo=tzlocal())

        self.status.open = status
        self.status.time = aTime
        self.status.who = who
        logging.debug('set_space_status [open: {}, who: {}]'.format(self.status.open, self.status.who))

        self.__save_config()

        self.__set_default_topic()

    def __save_config(self):
        self.set_config(self.CFG_KEY_STATE, self.status.open)
        self.set_config(self.CFG_KEY_STATE_TIME, self.status.time.strftime('%Y-%m-%dT%H:%M:%S %Z'))
        self.set_config(self.CFG_KEY_STATE_NICK, self.status.who)

    def __set_default_topic(self):
        key = self.CFG_KEY_TEXT_OPEN if self.status.open else self.CFG_KEY_TEXT_CLOSED
        default = self.DEFAULT_TEXT_OPEN if self.status.open else self.DEFAULT_TEXT_CLOSED
        channel = self.get_config('main_channel', '#tkkrlab')
        topic = self.get_config(key, default)
        self.__set_topic(channel, topic)

    def __set_topic(self, channel, new_topic):
        channel_topic = new_topic
        cfg_topic = self.get_config(self.CFG_KEY_TOPIC, self.DEFAULT_TOPIC)
        if cfg_topic:
            channel_topic += ' | ' + cfg_topic
        self.mgr.bot.connection.topic(channel, channel_topic)
        self.privmsg(channel, new_topic)
