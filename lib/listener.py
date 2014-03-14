import player
from recorder import Recorder

import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from twisted.python import log
import json, os

import tempfile
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

class Listener:
    def __init__(self, lisaclient, botname):
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        self.botname = botname
        self.lisaclient = lisaclient
        self.failed = 0
        self.keyword_identified = 0
        self.recording = tempfile.mktemp(suffix='google.wav', dir='%s/../tmp' % dir_path)

        self.pipeline = gst.Pipeline("mypipeline")

        gst.debug("Adding autoaudiosrc")
        self.source = gst.element_factory_make("autoaudiosrc", "autoaudiosrc")
        self.pipeline.add(self.source)

        # add a queue to allow pocketsphinx to recognize more data
        gst.debug("Adding encoding queue")
        self.qone = gst.element_factory_make("queue", "qone")
        self.pipeline.add(self.qone)

        # audio convert
        gst.debug("Adding encoding audioconvert")
        self.recfileconvert = gst.element_factory_make("audioconvert", "recfileconvert")
        self.pipeline.add(self.recfileconvert)

        # resample the wav
        gst.debug("Adding encoding audioresample")
        self.resampleOne = gst.element_factory_make("audioresample", "resampleOne")
        self.pipeline.add(self.resampleOne)

        # adding capsfilter
        self.capsfilterOne = gst.element_factory_make("capsfilter", "capsfilterOne")
        self.capsfilterOne.set_property('caps', gst.caps_from_string('audio/x-raw-int, rate=16000, width=16, depth=16, channels=1'))
        self.pipeline.add(self.capsfilterOne)

        # Add our tee
        gst.debug("Adding tee")
        self.rectee = gst.element_factory_make("tee", "rectee")
        self.pipeline.add(self.rectee)

        # Add another queue
        gst.debug("Adding encoding queue")
        self.qtwo = gst.element_factory_make("queue", "qtwo")
        self.pipeline.add(self.qtwo)

        # Add another audio resample
        gst.debug("Adding encoding audioresample")
        self.resampleTwo = gst.element_factory_make("audioresample", "resampleTwo")
        self.pipeline.add(self.resampleTwo)

        # adding capsfiltertwo
        self.capsfilterTwo = gst.element_factory_make("capsfilter", "capsfilterTwo")
        self.capsfilterTwo.set_property('caps', gst.caps_from_string('audio/x-raw-int, rate=8000'))
        self.pipeline.add(self.capsfilterTwo)

        # Add another vader
        gst.debug("Adding vader element")
        self.vader = gst.element_factory_make("vader","vader")
        self.vader.set_property("auto-threshold",False)
        self.pipeline.add(self.vader)

        # add pocketsphinx
        gst.debug("Adding pocketsphinx element")
        self.pocketsphinx = gst.element_factory_make("pocketsphinx","listener")
        #print "Pocketsphinx: "
        #print dir( self.pocketsphinx )
        self.pocketsphinx.set_property("lm",'%s/pocketsphinx/lisa.lm' % dir_path)
        self.pocketsphinx.set_property("dict",'%s/pocketsphinx/lisa.dic' % dir_path)
        self.pipeline.add(self.pocketsphinx)

        # Add Fakesink
        gst.debug("Adding fakesink")
        self.fakesink = gst.element_factory_make("fakesink", "fakesink")
        self.fakesink.set_property("dump", True)
        self.pipeline.add(self.fakesink)

        # creating valve now
        gst.debug("Adding Valve element")
        self.recording_valve = gst.element_factory_make('valve')
        self.recording_valve.set_property("drop",True)
        self.pipeline.add(self.recording_valve)

        # another qthree
        gst.debug("Adding encoding queue")
        self.qthree = gst.element_factory_make("queue", "qthree")
        self.pipeline.add(self.qthree)

        # adding wavenc element
        gst.debug("Adding wavenc")
        self.wavenc = gst.element_factory_make("wavenc", "wavenc")
        self.pipeline.add(self.wavenc)

        # adding filesink element
        gst.debug("Adding filesink")
        self.filesink = gst.element_factory_make("filesink", "filesink")
        self.filesink.set_property("location", self.recording)
        self.filesink.set_property("async", False)
        self.pipeline.add(self.filesink)

        # link everything needed for listener here

        # initiate the microphone
        self.source.link(self.qone)
        self.qone.link(self.recfileconvert)
        self.recfileconvert.link(self.resampleOne)
        self.resampleOne.link(self.rectee)

        # Take audio source and tee it into pocketsphinx
        self.rectee.get_request_pad('src%d').link(self.capsfilterOne.get_pad('sink'))
        self.capsfilterOne.link(self.qtwo)
        self.qtwo.link(self.resampleTwo)
        self.resampleTwo.link(self.capsfilterTwo)
        self.capsfilterTwo.link(self.vader)
        self.vader.link(self.pocketsphinx)
        self.pocketsphinx.link(self.fakesink)

        # Trying to use this here in listener. then only turn on the recorder when we need it on
        self.rectee.get_request_pad('src%d').link(self.recording_valve.get_pad('sink'))
        self.recording_valve.set_property('drop',True)
        self.recording_valve.link(self.qthree)
        self.qthree.link(self.wavenc)
        self.wavenc.link(self.filesink)

        listener = self.pipeline.get_by_name('listener')
        listener.connect('result', self.__result__)
        listener.set_property('configured', True)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        self.pipeline.set_state(gst.STATE_PLAYING)

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""

    def result(self, hyp, uttid):
        if hyp.lower() == self.botname.lower():
            log.msg("======================")
            log.msg("%s keyword detected" % self.botname)
            self.failed = 0
            self.keyword_identified = 1
            player.play('pi-listening')
            self.listen()

    def listen(self):
        self.pipeline.set_state(gst.STATE_PAUSED)
        player.play('pi-listening')
        log.msg("Hello Seraf")
        self.recording_valve.set_property('drop',False)
        Recorder(self,self.vader)
        self.recording_valve.set_property('drop',True)

    def cancel_listening(self):
        player.play('pi-cancel')
        self.recording_valve.set_property('drop',False)
        self.pipeline.set_state(gst.STATE_PLAYING)

    # question - sound recording
    def answer(self, question):
        player.play('pi-cancel')
        print " * Contacting Google"
        destf = tempfile.mktemp(suffix='piresult')
        os.system('wget --post-file %s --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.7 (KHTML, like Gecko) Chrome/16.0.912.77 Safari/535.7" --header="Content-Type: audio/x-flac; rate=16000" -O %s -q "https://www.google.com/speech-api/v1/recognize?client=chromium&lang=en-US"' % (question, destf))
        #os.system("speech2text %s > %s" % (question, destf))
        b = open(destf)
        result = b.read()
        b.close()

        os.unlink(question)
        os.unlink(destf)

        if len(result) == 0:
            print " * nop"
            player.play('pi-cancel')
        else:
            print "intelligency here"
        self.pipeline.set_state(gst.STATE_PLAYING)

    def get_pipeline(self):
        return self.pipeline

    def get_wav_file_location(self):
        return self.recording

    def __result__(self, listener, text, uttid):
        """We're inside __result__"""
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __partial_result__(self, listener, text, uttid):
        """We're inside __partial_result__"""
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __application_message__(self, bus, msg):
        msgtype =  msg.structure.get_name()
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            self.result(msg.structure['hyp'], msg.structure['uttid'])
