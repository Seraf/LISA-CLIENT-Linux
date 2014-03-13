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

import tempfile
import urllib2
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

from lib import Listener

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
soundfile = os.path.normpath(dir_path + '/tmp/output.wav')
configuration = json.load(open(os.path.normpath(dir_path + '/' + 'configuration/lisa.json')))
sound_queue = DeferredQueue()

botname = ""


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
                Listener(lisaclient=self, botname=botname)
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
