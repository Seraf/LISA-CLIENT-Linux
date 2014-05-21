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
except:
    gobjectnotimported = True
from twisted.internet import ssl, utils
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.defer import inlineCallbacks, DeferredQueue
from twisted.application.internet import TCPClient
from twisted.protocols.basic import LineReceiver
from twisted.application import internet, service
from twisted.internet import reactor
import json, os
from OpenSSL import SSL
import platform
from twisted.application.internet import TimerService
import urllib
from urllib import urlencode, urlopen, urlretrieve
import pkg_resources
from lib import Listener

# Globals
PWD = os.path.dirname(os.path.abspath(__file__))
sound_queue = DeferredQueue()
configuration = None
LisaFactory = None

def Speak(msg):
    sound_queue.put(msg)

@inlineCallbacks
def SoundWorker():
    """
    TTS engine mangement
    """

    soundfile = 'lisa-output'
    soundpath = '/tmp/'

    # Get data to speak
    data = yield sound_queue.get()
    
    # TODO manage internal messages
    if data == "no_server":
        play_sound = yield lib.player.play("no_server")
    
    # Pico TTS
    elif "tts" not in configuration or configuration["tts"].lower() == "pico":
        ext = "wav"
        file_name = soundpath + soundfile + "." + ext
        command_create = ('-w', file_name, '-l', configuration['lang'], '"'+ data.encode('UTF-8') + '"')
        create_sound = yield utils.getProcessOutputAndValue('/usr/bin/pico2wave', path='/usr/bin', args=command_create)

    # VoiceRSS
    elif configuration["tts"].lower() == "voicerss" and "voicerss_key" in configuration:
        ext = "ogg"
        file_name = soundpath + soundfile + "." + ext
        url = urlopen("http://api.voicerss.org/?%s" % urlencode({"r": 1, "c": ext.upper(), "f": "16khz_16bit_mono", "key": configuration["voicerss_key"], "src": data.encode('UTF-8'), "hl": "fr-fr"}))
        with open(os.path.basename(file_name), "wb") as f:
            yield f.write(url.read())

    # No TTS engine
    else:
        play_sound = yield lib.player.play("error_conf")
        return

    # Play synthetized file
    if os.path.exists(file_name):
        play_sound = yield lib.player.play(soundfile, path = soundpath, ext = ext)
        os.remove(file_name)
    else:
        log.err("There was an error creating the output file %s" % file_name)


class LisaClient(LineReceiver):
    """
    Lisa TCP client
    """
    def __init__(self, configuration):
        self.factory = None
        self.configuration = configuration
        self.listener = None
        self.debug_input = False
        if "debug" in configuration and "debug_input" in configuration["debug"]:
            self.debug_input = configuration["debug"]["debug_input"]
        self.debug_output = False
        if "debug" in configuration and "debug_output" in configuration["debug"]:
            self.debug_output = configuration["debug"]["debug_output"]
        self.zone = ""
        if "zone" in configuration:
            self.zone = configuration['zone']

    def sendMessage(self, message, type='chat', dict=None):
        if self.debug_output:
            log.msg('OUTPUT: "from": ' + unicode(platform.node()) + ',"type": ' + type + ', "body": ' + unicode(message) + ', "zone": ' + self.zone
            )
        if dict:
            self.sendLine(json.dumps(
                {
                    "from": unicode(platform.node()),
                    "type": type,
                    "body": unicode(message),
                    "zone": self.zone,
                    "outcome": dict
                }
            ))
        else:
            self.sendLine(json.dumps(
                {
                    "from": unicode(platform.node()),
                    "type": type,
                    "body": unicode(message),
                    "zone": self.zone
                }
            ))

    def lineReceived(self, data):
        """
        Data received callback
        """

        datajson = json.loads(data)
        if self.debug_input == True:
            log.msg("INPUT: " + unicode(datajson))

        if 'type' in datajson:
            if datajson['type'] == 'chat':
                Speak(datajson['body'])

            elif datajson['type'] == 'command':
                if datajson['command'] == 'LOGIN':
                    # Get Bot name
                    botname = unicode(datajson['bot_name'])
                    log.msg("setting botname to %s" % botname)
                    
                    # Send TTS
                    Speak(datajson['body'])
                    
                    # Create listener
                    if not 'nolistener' in datajson and not self.listener:
                        self.listener = Listener(lisa_client = self, botname = botname, configuration = self.configuration)

                # TODO seems a bit more complicated than I thought. I think the reply will be another type like "answer"
                # TODO and will contains a unique ID. On server side, the question will be stored in mongodb so it will
                # TODO let possible the multi user / multi client. Questions need to implement a lifetime too.
                # TODO For the soundqueue, I will need a callback system to be sure to play the audio before recording
                elif datajson['command'] == 'ASK':
                    Speak(datajson['body'])
                    
                    # Start record
                    if not 'nolistener' in datajson and self.listener:
                        self.listener.record()

        else:
            # Send to TTS queue
            Speak(datajson['body'])

    def connectionMade(self):
        """
        Callback on established connections
        """
        log.msg('Connected to the server.')

        # Set SSL encryption
        if 'enable_secure_mode' in self.configuration and self.configuration['enable_secure_mode'] == True:
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

    def Init(self, configuration):
        self.configuration = configuration

    def startedConnecting(self, connector):
        pass

    def buildProtocol(self, addr):
        # Reset retry delay
        self.resetDelay()
        
        # We don't need a "no connection" warning anymore
        self.first_time = False

        # Return protocol
        self.active_protocol = LisaClient(configuration = self.configuration)
        return self.active_protocol

    def clientConnectionLost(self, connector, reason):
        # Retry connection
        log.err('Lost connection.  Reason:', reason.getErrorMessage())
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        # Warn on first failure
        if self.first_time == True:
            Speak("no_server")
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
    
    # Stop factory
    LisaFactory.stopTrying()
    
    # Stop reactor
    reactor.stop()
    
    # Unregister handler, next Ctrl-C will kill app
    signal.signal(signal.SIGINT, signal.SIG_DFL)

# Make twisted service
def makeService(config):
    global configuration
    global LisaFactory
    
    # Client configuration
    if 'configuration' in config.keys():
        configuration = json.load(open(config['configuration']))
    elif os.path.exists("/etc/lisa/client/configuration/lisa.json"):
        configuration = json.load(open("/etc/lisa/client/configuration/lisa.json"))
    else:
        configuration = json.load(open(os.path.normpath(PWD + '/configuration/lisa.json')))

    # Check vial configuration
    if not 'lisa_url' in configuration or not 'lisa_engine_port_ssl' in configuration:
        lib.player.play("error_conf")
        sleep(3) # until player blocks
        return
    
    # Multiservice mode
    multi = service.MultiService()
    multi.setServiceParent(application)

    # Soundworker as a timer
    sound_service = TimerService(0.1, SoundWorker)
    sound_service.setServiceParent(multi)

    # Ctrl-C handler
    signal.signal(signal.SIGINT, sigint_handler)

    # Create factory
    LisaFactory = LisaClientFactory()
    LisaFactory.Init(configuration)

    # Start client
    if 'enable_secure_mode' in configuration and configuration['enable_secure_mode'] == True:
        lisaclientService = internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port_ssl'], LisaFactory, CtxFactory())
    else:
        lisaclientService = internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port'], LisaFactory)
    lisaclientService.setServiceParent(multi)

    return multi
