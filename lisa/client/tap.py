# client/tap.py
from twisted.application import internet, service
from twisted.internet import interfaces
from twisted.python import usage
from lisa.client import service

def makeService(config):
    return service.makeService()
