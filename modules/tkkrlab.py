from _module import _module

import httplib, urllib, urlparse

import datetime
from dateutil.tz import tzlocal
import dateutil.parser
import time

import random
import os.path

import os, signal, fcntl

class tkkrlab( _module ):
	def __init__( self, config, bot ):
		_module.__init__( self, config, bot )
		self.space_open = None
		try:
			signal.signal( signal.SIGIO, self.sigio_handler )
			self.fd = os.open( os.path.dirname( os.path.realpath( self.status_file ) ), os.O_RDONLY )
			fcntl.fcntl( self.fd, fcntl.F_SETSIG, 0 )
			fcntl.fcntl( self.fd, fcntl.F_NOTIFY, fcntl.DN_MODIFY | fcntl.DN_CREATE | fcntl.DN_MULTISHOT )
		except Exception, e:
			print( 'Failed to add signal: {0}'.format( e ) )

	def can_handle( self, cmd, admin ):
		return cmd in ( 'status', 'led', 'time', 'quote', 'help' )

	def handle( self, bot, cmd, args, source, target, admin ):
		( local_status, status_date ) = self.__get_space_status()
		if cmd == 'help':
			for line in [
				'!quote: to get a random quote',
				'!status: to get open/close status of the space',
				'!led message: put message on led matrix board',
				'!time: put current time on led matrix board',
			]:
				bot.privmsg( target, line )
		elif cmd == 'quote':
			bot.privmsg( target, 'Quote: ' + self.__random_quote() )
		elif cmd == 'status':
			if local_status not in ( True, False ):
				bot.privmsg( target, 'Error: {0}'.format( local_status ) )
			else:
				bot.privmsg( target, 'We are {0} since {1}'.format( 'Open' if local_status == True else 'Closed', datetime.datetime.fromtimestamp( status_date, tzlocal() ).strftime( '%a, %d %b %Y %H:%M:%S %Z' ) ) )
		elif cmd == 'led':
			if local_status == True:
				bot.privmsg( target, 'Led: {0}'.format( self.__send_led( ' '.join( args ) ) ) )
			elif local_status == False:
				bot.privmsg( target, 'Sorry ' + source + ', can only do this when space is open.' )
			else:
				bot.privmsg( target, 'Error: ' + local_status )
		elif cmd == 'time':
			self.__send_led( time.strftime( '%H:%M' ).center( 16 ) )

	def __get_space_status( self ):
		try:
			with open( self.status_file ) as fd:
				space_opened = fd.readline().strip()
				if self.space_open == None:
					self.space_open = space_opened == '1'

				if self.space_open != ( space_opened == '1' ):
					self.space_open = space_opened == '1'
					self.__set_topic( '#tkkrlab', 'We zijn Open' if self.space_open else 'We zijn Dicht' )
			space_date = os.path.getmtime( self.status_file )
			return ( self.space_open, space_date )
		except AttributeError:
			self.space_open = 'No status file configured'
		except IOError:
			self.space_open = 'No status file found'
		return ( self.space_open, None )

	def __set_topic( self, channel, new_topic ):
		self.bot.connection.topic( channel, new_topic )
		self.bot.privmsg( channel, new_topic )

	def __send_led( self, message):
		"""Send a command to the led board"""
		try:
			url = urlparse.urlparse( self.led_url.format( urllib.quote( message[:85] ) ) )
			conn = httplib.HTTPConnection( url.netloc, timeout=10 )
			conn.request( 'GET', url.path )
			response = conn.getresponse()
			res = response.status
			conn.close()
			if res != 200:
				return 'Error:' + res + ' - ' + response.reason
			else:
				return 'OK'
		except IOError, e:
			return 'Cannot connect to LED server: "{0}"'.format( e )
		except AttributeError:
			return 'LED URL not set'

	def __random_quote( self ):
		"""Read a quote from a text file"""
		try:
			with open( self.quote_file ) as fd:
				return random.choice( fd.readlines() )
		except AttributeError:
			return 'Error: no quote file defined'
		except IOError:
			return 'Error: quote file not found'

	def sigio_handler( self, signum, frame ):
		print( 'sigio!' )
		self.__get_space_status()