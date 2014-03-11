from twisted.internet import glib2reactor # for non-GUI apps
glib2reactor.install()

import sys
import signal
import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from twisted.internet import ssl, utils
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

import urllib2
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
soundfile = os.path.normpath(dir_path + '/tmp/output.wav')
configuration = json.load(open(os.path.normpath(dir_path + '/' + 'configuration/lisa.json')))
sound_queue = DeferredQueue()

botname = ""

class keyword_spotting(object):
    def __init__(self, LisaClient):
        """Initialize the speech components"""
        self.lisaclient = LisaClient
        self.recognizer = recognizer(self)
        self.pipeline = gst.parse_launch('autoaudiosrc ! audioconvert ! audioresample '
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
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def application_message(self, bus, msg):
        """Receive application messages from the bus."""
        msgtype = msg.structure.get_name()
        self.process_result(msg.structure['hyp'], msg.structure['uttid'])
        self.pipeline.set_state(gst.STATE_PAUSED)

    def process_result(self, hyp, uttid):
        global botname
        if hyp.lower() == botname.lower():
            log.msg("======================")
            log.msg("%s keyword detected" % botname)
            self.pipeline.set_state(gst.STATE_PAUSED)
            self.recognizer.pipeline.set_state(gst.STATE_PLAYING)

class recognizer(gobject.GObject):
    __gsignals__ = {
		'finished' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
	}
    def __init__(self, ks):
        gobject.GObject.__init__(self)
        # file where we record our voice (removed at end)
        self.ks = ks
        self.flacfile='tmp/google.flac'
        self.pipeline = gst.parse_launch('autoaudiosrc ! audioconvert ! audioresample '
                                         + '! vader name=vad auto-threshold=true '
                                         + '! audio/x-raw-int,rate=16000'
                                         + '! flacenc ! filesink location=%s' % self.flacfile)


        vader = self.pipeline.get_by_name('vad')
        vader.connect('vader-start', self.on_vader_start)
        vader.connect('vader-stop', self.on_vader_stop)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.application_message)

    def application_message(self, bus, msg):
        """Receive application messages from the bus."""
        msgtype = msg.structure.get_name()
        self.process_result(msg.structure['hyp'], msg.structure['uttid'])
        self.pipeline.set_state(gst.STATE_PAUSED)

    def process_result(self, hyp, uttid):
        # get content of the file
        flacfile = open(self.flacfile, 'r').read()

        # hey, Google ! what did I said ?
        try:
            req = urllib2.Request('https://www.google.com/speech-api/v1/'
                              'recognize?client=chromium&lang=fr-FR&maxresults=1',
                              flacfile, {'Content-Type': 'audio/x-flac; rate=16000'})
            res = urllib2.urlopen(req)
            resp = res.read()
            resp = json.loads(resp)
            text = resp['hypotheses'][0]['utterance']
            print text
            self.ks.lisaclient.sendMessage(message=text)
        except:
            pass #self.pipeline.set_state(gst.STATE_NULL)
        self.ks.set_state(gst.STATE_PLAYING)

    def cancel(self):
        print " * Not a word in the past 10 seconds, cancelling"
        self.pipeline.set_state(gst.STATE_NULL)

    def on_vader_start(self, ob, message):
        """ Just to be sure that vader has reconnized that you're speaking
        we set a trace """
        log.msg("Listening...")
        gobject.timeout_add_seconds(10, self.cancel)

    def on_vader_stop(self, ob, message):
        """ This function is launched when vader stopped to listen
        That happend when you stop to talk """

        log.msg("Processing...")
        # pause pipeline to not break our file
        self.pipeline.set_state(gst.STATE_PAUSED)


@inlineCallbacks
def SoundWorker():
    data = yield sound_queue.get()
    command_create = ('-w', soundfile,
               '-l', configuration['lang'], '"'+ data.encode('UTF-8') + '"')
    create_sound = yield utils.getProcessOutputAndValue('/usr/bin/pico2wave', path='/usr/bin', args=command_create)
    command_play = ( '-P', soundfile )
    play_sound = yield utils.getProcessOutputAndValue('/usr/bin/aplay', path='/usr/bin', args=command_play)
    os.remove(soundfile)

class LisaClient(LineReceiver):
    def __init__(self,factory):
        self.factory = factory
        self.bot_name = "lisa"
        botname = "lisa"

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
                print "I found login"
                self.bot_name = unicode(datajson['bot_name'])
                global botname
                botname = unicode(datajson['bot_name'])
                print "setting botname to %s" % self.bot_name
                sound_queue.put(datajson['body'])

    def connectionMade(self):
        log.msg('Connected to Lisa.')
        if configuration['enable_secure_mode']:
            ctx = ClientTLSContext()
            self.transport.startTLS(ctx, self.factory)
        self.sendMessage(message='LOGIN', type='command')

        #init gobject threads
        gobject.threads_init()
        #we want a main loop
        main_loop = gobject.MainLoop()
        #handle sigint
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        keyword_spotting(self)


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
