# -*- coding: UTF-8 -*-

# Imports
from twisted.python import log
import signal
gobjectnotimported = False
try:
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    import gobject
    import pygst
    pygst.require('0.10')
    gobject.threads_init()
    from lisa.client import lib
    from lib import Listener
    from lib import Speaker
except:
    gobjectnotimported = True
from twisted.internet import ssl, utils
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.defer import inlineCallbacks, DeferredQueue
from twisted.application.internet import TCPClient
from twisted.protocols.basic import LineReceiver
from twisted.application import internet, service
from twisted.internet import reactor
from lisa.client.ConfigManager import ConfigManagerSingleton
import json, os
from OpenSSL import SSL
import platform

# Globals
PWD = os.path.dirname(os.path.abspath(__file__))
sound_queue = DeferredQueue()
configuration = None
LisaFactory = None


class LisaClient(LineReceiver):
    """
    Lisa TCP client
    """
    def __init__(self):
        self.factory = None
        self.configuration = ConfigManagerSingleton.get().getConfiguration()
        self.listener = None
        self.debug_input = False
        self.debug_output = False
        if self.configuration.has_key("debug"):
            if self.configuration["debug"].has_key("debug_input"):
                self.debug_input = self.configuration["debug"]["debug_input"]
            if self.configuration["debug"].has_key("debug_output"):
                self.debug_output = self.configuration["debug"]["debug_output"]
        self.zone = ""
        if self.configuration.has_key("zone"):
            self.zone = self.configuration['zone']

    def sendMessage(self, message, type='chat', dict=None):
        if dict:
            line = json.dumps(
                {
                    "from": unicode(platform.node()),
                    "type": type,
                    "body": unicode(message),
                    "zone": self.zone,
                    "outcome": dict
                }
            )
        else:
            line = json.dumps(
                {
                    "from": unicode(platform.node()),
                    "type": type,
                    "body": unicode(message),
                    "zone": self.zone
                }
            )

        if self.debug_output:
            log.msg('OUTPUT: %s' % line)

        # send line to the server
        self.sendLine(line)

    def lineReceived(self, data):
        """
        Data received callback
        """

        datajson = json.loads(data)
        if self.debug_input == True:
            log.msg("INPUT: " + unicode(datajson))

        if datajson.has_key("type"):
            if datajson['type'] == 'chat':
                Speaker.speak(datajson['body'])

            elif datajson['type'] == 'command':
                if datajson['command'] == 'LOGIN':
                    # Get Bot name
                    botname = unicode(datajson['bot_name'])
                    log.msg("setting botname to %s" % botname)
                    self.botname = botname

                    # Send TTS
                    Speaker.speak(datajson['body'])
                    
                    # Create listener
                    if datajson.has_key('nolistener') == False and not self.listener:
                        self.listener = Listener(lisa_client = self, botname = botname)

                # TODO seems a bit more complicated than I thought. I think the reply will be another type like "answer"
                # TODO and will contains a unique ID. On server side, the question will be stored in mongodb so it will
                # TODO let possible the multi user / multi client. Questions need to implement a lifetime too.
                # TODO For the soundqueue, I will need a callback system to be sure to play the audio before recording
                elif datajson['command'] == 'ASK':
                    Speaker.speak(datajson['body'])
                    
                    # Start record
                    if datajson.has_key('nolistener') == False and self.listener:
                        self.listener.record()

        else:
            # Send to TTS queue
            Speaker.speak(datajson['body'])

    def connectionMade(self):
        """
        Callback on established connections
        """
        log.msg('Connected to the server.')

        # Set SSL encryption
        if self.configuration.has_key('enable_secure_mode') and self.configuration['enable_secure_mode'] == True:
            ctx = ClientTLSContext()
            self.transport.startTLS(ctx, self.factory)

        # Login to server
        self.sendMessage(message='LOGIN', type='command')

    def connectionLost(self, reason):
        """
        Callback on connection loss
        """
        # Stop listener
        log.msg("Lost connection with server : " + reason.getErrorMessage())
        if self.listener:
            self.listener.stop()


class LisaClientFactory(ReconnectingClientFactory):
    # Create protocol
    active_protocol = None

    # Warn about failure on first connection to the server
    first_time = True

    def Init(self):
        self.configuration = ConfigManagerSingleton.get().getConfiguration()


    def startedConnecting(self, connector):
        pass

    def buildProtocol(self, addr):
        # Reset retry delay
        self.resetDelay()
        
        # We don't need a "no connection" warning anymore
        self.first_time = False

        # Return protocol
        self.active_protocol = LisaClient()
        return self.active_protocol

    def clientConnectionLost(self, connector, reason):
        # Retry connection
        log.err('Lost connection.  Reason:', reason.getErrorMessage())
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        # Warn on first failure
        if self.first_time == True:
            Speaker.speak("no_server")
            self.first_time = False
            
        # Retry
        self.resetDelay()
        log.err('Connection failed. Reason:', reason.getErrorMessage())
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class ClientTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)


class CtxFactory(ssl.ClientContextFactory):
    def getContext(self):
        self.method = SSL.SSLv23_METHOD
        ctx = ssl.ClientContextFactory.getContext(self)
        ctx.use_certificate_file(os.path.normpath(PWD + '/configuration/ssl/client.crt'))
        ctx.use_privatekey_file(os.path.normpath(PWD + '/configuration/ssl/client.key'))
        return ctx


# Creating MultiService
application = service.Application("LISA-Client")

# Handle Ctrl-C
def sigint_handler(signum, frame):
    global LisaFactory
    global sound_service
    
    # Unregister handler, next Ctrl-C will kill app
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Stop factory
    LisaFactory.stopTrying()
    
    # Stop reactor
    reactor.stop()
    
    # Stop speaker
    Speaker.stop()
    
# Make twisted service
def makeService(config):
    global LisaFactory
    
    if config['configuration']:
        ConfigManagerSingleton.get().setConfiguration(config['configuration'])

    configuration = ConfigManagerSingleton.get().getConfiguration()

    # Init speaker singleton
    Speaker.start()

    # Check vial configuration
    if configuration.has_key('lisa_url') == False or configuration.has_key('lisa_engine_port_ssl') == False:
        Speaker.speak("error_conf")
        return
    
    # Multiservice mode
    multi = service.MultiService()
    multi.setServiceParent(application)

    # Ctrl-C handler
    signal.signal(signal.SIGINT, sigint_handler)

    # Create factory
    LisaFactory = LisaClientFactory()
    LisaFactory.Init()

    # Start client
    if configuration.has_key('enable_secure_mode') and configuration['enable_secure_mode'] == True:
        lisaclientService = internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port_ssl'], LisaFactory, CtxFactory())
    else:
        lisaclientService = internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port'], LisaFactory)
    lisaclientService.setServiceParent(multi)

    return multi
