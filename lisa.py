from twisted.internet import ssl, reactor
from twisted.internet.protocol import Protocol, ReconnectingClientFactory
from twisted.protocols.basic import LineReceiver
from twisted.application import internet, service
from twisted.python import log
import json, os
from OpenSSL import SSL
import speechd
import platform

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
configuration = json.load(open(os.path.normpath(dir_path + '/' + 'configuration/lisa.json')))

client = speechd.client.SSIPClient('LISA')
client.set_punctuation(speechd.PunctuationMode.SOME)
client.set_output_module(str(configuration['tts']))
client.set_language(str(configuration['lang']))

class LisaClient(LineReceiver):
    def __init__(self,factory):
        self.factory = factory

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
            client.speak(unicode(datajson['body']))

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
        client.close()
        log.msg("DOING A CLIENT CLOSE")
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

LisaFactory = LisaClientFactory()
application = service.Application("LISA-Client")
if configuration['enable_secure_mode']:
    lisaclientService =  internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port_ssl'], LisaFactory, CtxFactory())
else:
    lisaclientService =  internet.TCPClient(configuration['lisa_url'], configuration['lisa_engine_port'], LisaFactory)
lisaclientService.setServiceParent(application)
