from twisted.internet import ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.defer import inlineCallbacks, DeferredQueue
from twisted.protocols.basic import LineReceiver
from twisted.application import internet, service
from twisted.python import log
import subprocess
import json, os
from OpenSSL import SSL
import platform
from twisted.application.internet import TimerService

import gobject
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
configuration = json.load(open(os.path.normpath(dir_path + '/' + 'configuration/lisa.json')))
sound_queue = DeferredQueue()

class keyword_spotting(object):
    def __init__(self, LisaFactory):
        """Initialize the speech components"""
        self.LisaFactory = LisaFactory
        self.pipeline = gst.parse_launch('gconfaudiosrc ! audioconvert ! audioresample '
                                         + '! vader name=vad auto-threshold=true '
                                         + '! pocketsphinx name=asr '
                                         + '! appsink sync=false ')
        asr = self.pipeline.get_by_name('asr')
        asr.connect('partial_result', self.asr_partial_result)
        asr.connect('result', self.asr_result)
        asr.set_property('lm', 'lisa.lm')
        asr.set_property('dict', 'lisa.dic')
        asr.set_property('configured', True)


        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.application_message)

        self.pipeline.set_state(gst.STATE_PLAYING)

    def asr_partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def asr_result(self, asr, text, uttid):
        """Forward result signals on the bus to the main thread."""
        struct = gst.Structure('result')
        print "========================================"
        print text
        print "========================================"
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def application_message(self, bus, msg):
        """Receive application messages from the bus."""
        msgtype = msg.structure.get_name()
        self.display_result(msg.structure['hyp'], msg.structure['uttid'])
        self.pipeline.set_state(gst.STATE_PAUSED)

    def display_result(self, hyp, uttid):
        print hyp

@inlineCallbacks
def SoundWorker():
    data = yield sound_queue.get()
    soundfile = os.path.normpath(dir_path + '/tmp/output.wav')

    command_create = ['pico2wave', '-w', soundfile,
               '-l', configuration['lang'], '"'+ data.encode('UTF-8') + '"']
    create_sound = subprocess.call(command_create)

    command_play = ['aplay', soundfile]
    play_sound = subprocess.call(command_play)

    os.remove(soundfile)

class LisaClient(LineReceiver):
    def __init__(self,factory):
        self.factory = factory
        self.bot_name = "lisa"

    def sendMessage(self, message, type='chat'):
        if configuration['debug']['debug_output']:
            log.msg('OUTPUT: "from": ' + unicode(platform.node()) + ',"type": ' + type + ', "body": ' + unicode(message) +
                    ', "zone": ' + configuration['zone']
            )
        self.sendLine(json.dumps(
            {"from": unicode(platform.node()), "type": type, "body": unicode(message), "zone": configuration['zone']})
        )

    def lineReceived(self, data):
        datajson = json.loads(data)
        if configuration['debug']['debug_input']:
            log.msg("INPUT: " + unicode(datajson))
        if datajson['type'] == 'chat':
            sound_queue.put(datajson['body'])
        elif datajson['type'] == 'command':
            if datajson['command'] == 'LOGIN':
                self.bot_name = unicode(datajson['bot_name'])
                sound_queue.put(datajson['body'])

    def connectionMade(self):
        log.msg('Connected to Lisa.')
        if configuration['enable_secure_mode']:
            ctx = ClientTLSContext()
            self.transport.startTLS(ctx, self.factory)
        self.sendMessage(message='LOGIN', type='command')

class LisaClientFactory(ReconnectingClientFactory):
    def startedConnecting(self, connector):
        log.msg('Started to connect.')

    def buildProtocol(self, addr):
        self.protocol = LisaClient(self)
        log.msg('Resetting reconnection delay')
        self.resetDelay()
        return self.protocol

    def clientConnectionLost(self, connector, reason):
        log.err('Lost connection.  Reason:', reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.err('Connection failed. Reason:', reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

class ClientTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)

class CtxFactory(ssl.ClientContextFactory):
    def getContext(self):
        self.method = SSL.SSLv23_METHOD
        ctx = ssl.ClientContextFactory.getContext(self)
        ctx.use_certificate_file(os.path.normpath(dir_path + '/' + 'configuration/ssl/client.crt'))
        ctx.use_privatekey_file(os.path.normpath(dir_path + '/' + 'configuration/ssl//client.key'))

        return ctx

# Creating MultiService
application = service.Application("LISA-Client")
multi = service.MultiService()
multi.setServiceParent(application)

sound_service = TimerService(0.01, SoundWorker)
sound_service.setServiceParent(multi)

LisaFactory = LisaClientFactory()

if configuration['enable_secure_mode']:
    lisaclientService =  internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port_ssl'], LisaFactory, CtxFactory())
else:
    lisaclientService =  internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port'], LisaFactory)

lisaclientService.setServiceParent(multi)
keyword_spotting(LisaFactory)
