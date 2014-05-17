# It fixes a bug with the pocketpshinx import. The first time it fails, but the second import is ok.
try:
    import pocketsphinx
except:
    pass
import pocketsphinx
from wit import Wit
import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from twisted.python import log
import json, os
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst
from lisa.client.lib import player
from lisa.client.lib.recorder import RecorderSingleton


path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
if os.path.exists('/etc/lisa/client/configuration/lisa.json'):
    configuration = json.load(open('/etc/lisa/client/configuration/lisa.json'))
else:
    configuration = json.load(open(os.path.normpath(dir_path + '/../' + 'configuration/lisa.json')))


class Listener:
    def __init__(self, lisaclient, botname):

        self.configuration = configuration
        self.recording_state = False
        self.botname = botname
        self.lisaclient = lisaclient
        self.failed = 0
        self.keyword_identified = 0
        self.wit = Wit(self.configuration['wit_token'])

        # The goal is to listen for a keyword. When I have this keyword, it records for few seconds and stream the
        # flow to Wit which answer by json.

        self.pipeline = gst.parse_launch('alsasrc ! audioconvert ! audioresample '
				+ '! vader name=vad auto-threshold=true '
				+ '! pocketsphinx name=asr ! fakesink')

        self.vader = self.pipeline.get_by_name('vad')

        asr = self.pipeline.get_by_name('asr')
        if os.path.isfile('/var/lib/lisa/client/pocketsphinx/lisa.dic'):
            asr.set_property("dict", '/var/lib/lisa/client/pocketsphinx/lisa.dic')
            asr.set_property("lm", '/var/lib/lisa/client/pocketsphinx/lisa.lm')
        else:
            asr.set_property("dict", "%s/lib/pocketsphinx/lisa.dic" % os.path.normpath(dir_path + '/../'))
            asr.set_property("lm", "%s/lib/pocketsphinx/lisa.lm" % os.path.normpath(dir_path + '/../'))
        asr.connect('result', self.result)
        asr.set_property('configured', True)

        self.ps = pocketsphinx.Decoder(boxed=asr.get_property('decoder'))

        self.pipeline.set_state(gst.STATE_PLAYING)

    def result(self, asr, hyp, uttid):
        print hyp.lower()
        if hyp.lower() == self.botname.lower() and not self.recording_state:
            struct = gst.Structure('result')
            dec_text, dec_uttid, dec_score = self.ps.get_hyp()

            if dec_score >= self.configuration['keyword_score']:
                log.msg("======================")
                log.msg("%s keyword detected" % self.botname)
                log.msg("score: {}".format(dec_score))

                self.failed = 0
                self.keyword_identified = 1
                self.record()
            else:
                log.msg("I recognized the %s keyword but I think it's a false positive according the %s score" %
                        (self.botname.lower(), dec_score))

    def cancel_listening(self):
        log.msg("cancel_listening : player.play('pi-cancel')")
        player.play('pi-cancel')
        self.recording_state = False

    # sound recording
    def record(self):
        self.pipeline.set_state(gst.STATE_PAUSED)
        self.recording_state = True
        # This content type (raw) allow to send data from mic directly to Wit and stream chunks
        # thanks to the generator
        CONTENT_TYPE = 'raw;encoding=signed-integer;bits=16;rate=16000;endian=little'
        result = self.wit.post_speech(data=RecorderSingleton.get(configuration=self.configuration).capture_audio(),
                                      content_type=CONTENT_TYPE)
        player.play('pi-cancel')
        log.msg(" * Contacting Wit")
        if len(result) == 0:
            log.msg("cancel_listening : player.play('pi-cancel')")
            player.play('pi-cancel')
        else:
            log.msg(result)
            self.lisaclient.sendMessage(message=result['msg_body'], type='chat', dict=result['outcome'])
        self.recording_state = False
        self.pipeline.set_state(gst.STATE_PLAYING)

    def get_pipeline(self):
        return self.pipeline