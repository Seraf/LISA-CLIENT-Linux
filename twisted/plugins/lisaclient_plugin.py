from zope.interface import implements

from twisted.python import usage
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin

from lisa.client import service

class Options(usage.Options):
    optParameters = [
        ['configuration', 'c', '/etc/lisa/client/configuration/lisa.json'],
    ]

class ServiceMaker(object):
    implements(IServiceMaker, IPlugin)

    tapname = "lisa-client"
    description = "Lisa client."
    options=Options

    def makeService(self, config):
        return service.makeService(config)

serviceMaker = ServiceMaker()