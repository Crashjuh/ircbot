import logging

class _module( object ):
	def __init__( self, manager ):
		self.mgr = manager
		logging.debug( 'Loading module {0}'.format( self.__class__.__name__ ) )
	def __del__( self ):
		logging.debug( 'Module {0} is being unloaded'.format( self.__class__.__name__ ) )
		self.stop()
	def stop( self ):
		pass
		
	def get_cmd_list( self ):
		return [ '!{0}'.format( cmd[ len( 'cmd_' ) : ] ) for cmd in dir( self ) if cmd.startswith( 'cmd_' ) ]
	def has_cmd( self, cmd ):
		return hasattr( self, 'cmd_{0}'.format( cmd ) )
	def get_cmd( self, cmd ):
		return getattr( self, 'cmd_{0}'.format( cmd ) )

	def get_admin_cmd_list( self ):
		return [ '!{0}'.format( cmd[ len( 'admin_cmd_' ) : ] ) for cmd in dir( self ) if cmd.startswith( 'admin_cmd_' ) ]
	def has_admin_cmd( self, cmd ):
		return hasattr( self, 'admin_cmd_{0}'.format( cmd ) )
	def get_admin_cmd( self, cmd ):
		return getattr( self, 'admin_cmd_{0}'.format( cmd ) )
		
	# methods that directly call the mgr

	def notice( self, target, message ):
		self.mgr.notice( target, message )
	def privmsg( self, target, message ):
		self.mgr.privmsg( target, message )
		
	def get_config( self, key ):
		return self.mgr.get_config( self.__class__.__name__, key )
	def set_config( self, key, value ):
		self.mgr.set_config( self.__class__.__name__, key, value )
