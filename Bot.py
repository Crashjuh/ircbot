import ConfigParser, sys, os, signal, subprocess
import datetime,time
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_uh, is_channel
import socket
import modules
import sqlite3
import logging

from ModuleManager import ModuleManager

class BotReloadException(Exception):
	pass

class Bot( SingleServerIRCBot ):
	"""The main brain of the IRC bot."""
	def __init__( self ):
		self.last_msg = -1
		self.msg_flood_limit = 0.25
		
		self.admin_channels = []
		self.config = ConfigParser.SafeConfigParser()
		self.config.read( os.path.expanduser( "~/.ircbot" ) )
		
		self.admin = self.config.get( 'main', 'admin' ).split( ';' )
		self.admin_channels = self.config.get( 'main', 'admin_channels' ).split( ';' )
		
		self.db = sqlite3.connect( os.path.join( os.path.dirname( __file__ ), 'ircbot.sqlite3' ), check_same_thread = False )
		cursor = self.db.cursor()
		try:
			cursor.execute( 'select * from config limit 1' )
		except sqlite3.OperationalError: # table no exist
			cursor.execute( 'create table config ( `group` varchar(100), `key` varchar(100), `value` varchar(100) NULL )' )
		cursor.close()
		self.modules = ModuleManager( self )

		self.channel_ops = {}
		
		s = self.config.get( "main", "server" ).split( ":", 1 )
		server = s[0]
		if len(s) == 2:
			try:
				port = int( s[1] )
			except ValueError:
				logging.error( "Error: Erroneous port." )
				sys.exit(1)
		else:
			port = 6667

		try:
			password = self.config.get( "main", "password" )
		except:
			password = None

		channel = self.config.get( 'main', 'channel' )
		nickname = self.config.get( 'main', 'nickname' )

		if password != None:
			SingleServerIRCBot.__init__( self, [( server, port, password )], nickname, nickname )
		else:
			SingleServerIRCBot.__init__( self, [( server, port )], nickname, nickname )
		
		self.channel = channel
		
		for module_name in self.modules.get_available_modules():
			self.modules.enable_module( module_name )
		
		signal.signal( signal.SIGINT, self.sigint_handler )

	def start( self ):
		self._connect()
		
		if not self.connection.connected:
			logging.error( 'Failed to connect' )
			return False
		
		self.last_ping = None
		self.ping_timeout = 3 * 60 # 3 minutes
		while self.connection.connected:
			try:
				self.connection.process_data()
			except socket.timeout:
				logging.warning( 'Socket timeout' )
				return False
			except BotReloadException as e:
				self.connection.disconnect( "Reloading bot..." )
				self.modules.unload()
				raise e
			#except Exception as e:
			#	raise e
			#	print( 'Exception: {0}'.format( e ) )
			
	
	def die( self ):
		logging.debug( 'die()' )
		self.modules.unload()
		SingleServerIRCBot.die(self)

	def sigint_handler( self, signal, frame ):
		"""Handle SIGINT to shutdown gracefully with Ctrl+C"""
		logging.debug( 'Ctrl+C pressed, shutting down!' )
		self.die()
		sys.exit(0)

	def __prevent_flood( self ):
		if self.last_msg > 0:
			if time.time() < self.last_msg + self.msg_flood_limit:
				sleep_time = self.last_msg + self.msg_flood_limit - time.time()
				logging.debug( 'Need to sleep for {0}'.format( sleep_time ) )
				time.sleep( sleep_time )
		self.last_msg = time.time()
		
	def notice( self, target, message ):
		self.__prevent_flood()
		self.connection.notice( target, message )
	def privmsg( self, target, message ):
		self.__prevent_flood()
		self.connection.privmsg( target, message )
	def action( self, target, message ):
		self.__prevent_flood()
		self.connection.action( target, message )

	def __module_handle( self, handler, *args ):
		"""Passed the "on_*" handlers through to the modules that support them"""
		handler = 'on_' + handler
		for module in self.modules.get_loaded_modules().itervalues():
			if hasattr( module, handler ):
				try:
					getattr( module, handler )( *args )
				except Exception as e:
					logging.debug( 'Module handler {0} failed: {1}', handler, e )

	def __process_command( self, c, e ):
		"""Process a message coming from the server."""
		message = e.arguments()[0]
		# commands have to start with !
		if message[0] != '!':
			return
		# strip the ! off, and split the message
		args = message[1:].split()
		# cmd is the first item
		cmd = args.pop(0).strip()
		# test for admin
		admin = nm_to_uh( e.source() ) in self.admin
		if not admin:
			if e.target() in self.admin_channels and e.target() in self.channel_ops and nm_to_n( e.source() ) in self.channel_ops[ e.target() ]:
				admin = True

		# nick is the sender of the message, target is either a channel or the sender.
		source = nm_to_n( e.source() )
		target = e.target()
		if not is_channel( target ):
			target = source

		# see if there is a module that is willing to handle this, and make it so.
		logging.debug( '__process_command (src: {0}; tgt: {1}; cmd: {2}; args: {3}; admin: {4})'.format( source, target, cmd, args, admin ) )

		# handle die outside of module (in case module is dead :( )
		if admin:
			if cmd == 'die':
				self.notice( source, 'Goodbye cruel world!' )
				self.die()
				return
			elif cmd == 'restart_class':
				raise BotReloadException
			# config commands
			elif cmd == 'get_config' and len( args ) <= 2:
				if len( args ) == 2:
					try:
						value = self.get_config( args[0], args[1] )
						self.notice( source, 'config[{0}][{1}] = {2}'.format( args[0], args[1], value ) )
					except:
						self.notice( source, 'config[{0}][{1}] not set'.format( *args ) )
				elif len( args ) == 1:
					try:
						values = self.get_config( args[0] )
						if len( values ) > 0:
							self.notice( source, 'config[{}]: '.format( args[0] ) + ', '.join( [ '{}: "{}"'.format( k,v ) for ( k, v ) in values.iteritems() ] ) )
						else:
							self.notice( source, 'config[{}] is empty'.format( args[0] ) )
					except:
						self.notice( source, 'config[{}] not set'.format( args[0] ) )
				else:
					try:
						self.notice( source, 'config groups: ' + ', '.join( self.get_config_groups() ) )
					except Exception as e:
						self.notice( source, 'No config groups: {}'.format( e ) )
			elif cmd == 'set_config' and len( args ) >= 2:
				if len( args ) >= 3:
					config_val = ' '.join( args[2:] )
				else:
					config_val = None
				try:
					self.set_config( args[0], args[1], config_val )
					self.notice( source, 'Set config setting' if config_val else 'Cleared config setting' )
				except Exception as e:
					self.notice( source, 'Failed setting/clearing config setting: {0}'.format( e ) )
			# modules commands
			elif cmd == 'modules':
				self.notice( source, 'Modules: {0}'.format( ', '.join( self.modules.get_modules() ) ) )
			elif cmd == 'available_modules':
				self.notice( source, 'Available modules: ' + ', '.join( self.modules.get_available_modules() ) )
			elif cmd == 'reload_module' and len( args ) > 0:
				for m in args:
					self.notice( source, self.modules.reload_module( m ) )
			elif cmd == 'reload_modules':
				self.modules.reload_modules()
			elif cmd == 'enable_module' and len( args ) > 0:
				for m in args:
					self.notice( source, self.modules.enable_module( m ) )
			elif cmd == 'disable_module' and len( args ) > 0:
				for m in args:
					self.notice( source, self.modules.disable_module( m ) )
			# other base admin commands
			elif cmd == 'raw':
				self.connection.send_raw( ' '.join( args ) )
				return
			elif cmd == 'admins':
				self.notice( source, 'Current operators:' )
				self.notice( source, ' - global: {0}'.format( ' '.join( self.admin ) ) )
				for chan in [ chan for chan in self.admin_channels if chan in self.channel_ops ]:
					self.notice( source, ' - {0}: {1}'.format( chan, ' '.join( self.channel_ops[ chan ] ) ) )
				return
		
		if cmd == 'help':
			if len( args ) > 0:
				if args[0] == 'module':
					if len( args ) < 2:
						pass
					elif args[1] in self.modules.get_loaded_modules():
						module = self.modules.get_loaded_modules()[ args[1] ]
						self.notice( target, module.__doc__ )
				else:
					for ( module_name, module ) in self.modules.get_loaded_modules().iteritems():
						if module.has_cmd( args[0] ):
							self.notice( target, module.get_cmd( args[0] ).__doc__ )
			else:
				self.notice( target, '!help: this help text (send !help <command> for command help, send !help module <module> for module help)' )
				for ( module_name, module ) in self.modules.get_loaded_modules().iteritems():
					cmds = module.get_cmd_list()
					self.notice( target, ' * {0}: {1}'.format( module_name, ', '.join( cmds ) if len( cmds ) > 0 else 'No commands' ) )

		elif admin and cmd == 'admin_help':
			if len( args ) > 0:
				for ( module_name, module ) in self.modules.get_loaded_modules().iteritems():
					if module.has_admin_cmd( args[0] ):
						self.notice( source, module.get_admin_cmd( args[0] ).__doc__ )
			else:
				self.notice( source, '!admin_help: this help text (send !admin_help <command> for command help' )
				self.notice( source, '!die:                                   kill the bot' )
				self.notice( source, '!raw:                                   send raw irc command' )
				self.notice( source, '!admins:                                see who are admin' )
				self.notice( source, '!restart_class:                         restart the main Bot class' )
				self.notice( source, '!available_modules:                     see modules that are not currently loaded' )
				self.notice( source, '!reload_module <module>[ <module>...]:  reload one or more modules' )
				self.notice( source, '!enable_module <module>[ <module>...]:  enable one or more modules' )
				self.notice( source, '!disable_module <module>[ <module>...]: disable one or more modules' )
				for ( module_name, module ) in self.modules.get_loaded_modules().iteritems():
					cmds = module.get_admin_cmd_list()
					if len( cmds ) > 0:
						self.notice( source, ' * {0}: {1}'.format( module_name, ', '.join( cmds ) ) )
		else:
			for ( module_name, module ) in self.modules.get_loaded_modules().iteritems():
				try:
					if module.has_cmd( cmd ):
						lines = module.get_cmd( cmd )( args, source, target, admin )
						if lines:
							for line in lines:
								self.notice( target, line )
					elif admin and module.has_admin_cmd( cmd ):
						lines = module.get_admin_cmd( cmd )( args, source, target, admin )
						if lines:
							for line in lines:
								self.notice( source, line )
				except Exception as e:
					logging.warning( "Module '{0}' handle error: {1}".format( module_name, e ) )

	def on_privmsg( self, c, e ):
		#print( "on_privmsg" )
		
		source = nm_to_n( e.source() )
		target = e.target() if is_channel( e.target() ) else source
		message = e.arguments()[0]
		
		self.__module_handle( 'privmsg', source, target, message )
		self.__process_command( c, e )

	def on_pubmsg( self, c, e ):
		#print( "on_pubmsg" )
		self.on_privmsg( c, e )
		
	def on_join( self, c, e ):
		self.connection.names( [e.target()] )

	def on_mode( self, c, e ):
		self.connection.names( [e.target()] )

	def on_namreply( self, c, e ):
		chan = e.arguments()[1]
		people = e.arguments()[2].split( ' ' )
		ops = map( lambda p: p[1:], filter( lambda p: p[0] == '@', people ) )
		self.channel_ops[ chan ] = ops

	def on_nicknameinuse( self, c, e ):
		"""Gets called if the server complains about the name being in use. Tries to set the nick to nick + '_'"""
		logging.debug( "on_nicknameinuse" )
		c.nick( c.get_nickname() + "_" )

	def on_welcome( self, c, e ):
		logging.debug( "on_welcome" )
		c.join( self.channel )

	def get_config_groups( self ):
		resultset = self.db.execute( 'select distinct `group` from config' )
		return [ g for ( g, ) in resultset.fetchall() ]

	def get_config( self, group, key = None, default = None ):
		"""gets a config value"""
		if key == None:
			resultset = self.db.execute( 'select `key`, `value` from config where `group` = :group', { 'group': group } )
			values = {}
			for ( key, value ) in resultset.fetchall():
				values[ key ] = value
			return values
		else:
			resultset = self.db.execute( 'select `value` from config where `group` = :group and `key` = :key', { 'group': group, 'key': key } )
			value = resultset.fetchone()
			if value == None:
				if default != None:
					return default
				raise Exception
			return value[0]

	def set_config( self, group, key, value ):
		"""sets a config value"""
		cursor = self.db.cursor()
		data = { 'group': group, 'key': key, 'value': value }
		if value == None:
			cursor.execute( 'delete from config where `group` = :group and `key` = :key', data )
		else:
			try:
				self.get_config( group, key )
				cursor.execute( 'update config set `value` = :value where `group` = :group and `key` = :key', data )
			except:
				cursor.execute( 'insert into config ( `group`, `key`, `value` ) values( :group, :key, :value )', data )
		cursor.close()
		self.db.commit()
