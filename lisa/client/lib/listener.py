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

# Client configuration
path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
if os.path.exists('/etc/lisa/client/configuration/lisa.json'):
    configuration = json.load(open('/etc/lisa/client/configuration/lisa.json'))
else:
    configuration = json.load(open(os.path.normpath(dir_path + '/../' + 'configuration/lisa.json')))


class Listener:
    """The goal is to listen for a keyword. When I have this keyword, it records for few seconds and stream the
    flow to Wit which answer by json."""
    
    def __init__(self, lisaclient, botname):
        self.configuration = configuration
        self.recording_state = False
        self.botname = botname.lower()
        self.lisaclient = lisaclient
        self.failed = 0
        self.keyword_identified = 0
        self.wit = Wit(self.configuration['wit_token'])
        self.scores = []

        # Build Gstreamer pipeline : mic->Alsa->AudioConvert->audioResample->vader->pocketsphinx
        self.pipeline = gst.parse_launch('alsasrc ! audioconvert ! audioresample '
				+ '! vader name=vad auto-threshold=true '
				+ '! pocketsphinx name=asr ! fakesink')

        # Configure vader
        self.vader = self.pipeline.get_by_name('vad')

        # Find client path
        if os.path.isfile('/var/lib/lisa/client/pocketsphinx/lisa.dic'):
            client_path = '/var/lib/lisa/client/pocketsphinx'
        else:
            client_path = "%s/lib/pocketsphinx" % os.path.normpath(dir_path + '/../')
        
        # PocketSphinx configuration
        asr = self.pipeline.get_by_name('asr')
        asr.set_property("dict", "%s/%s.dic" % (client_path, self.botname))
        asr.set_property("lm", "%s/%s.lm" % (client_path, self.botname))
        try:
            hmm_path = "%s/%s" % (client_path, self.configuration["hmm"])
            if os.path.isdir(hmm_path):
                asr.set_property("hmm", hmm_path)
        except:
            pass
        asr.connect('result', self.result)
        asr.set_property('configured', True)
        self.ps = pocketsphinx.Decoder(boxed=asr.get_property('decoder'))

        # Start pipeline
        self.pipeline.set_state(gst.STATE_PLAYING)

    def result(self, asr, hyp, uttid):
        """Result from pocketsphinx : checking keyword recognition"""
        print hyp.lower()
        
        # Check keyword detection
        if hyp.lower() == self.botname and not self.recording_state:
            struct = gst.Structure('result')
            dec_text, dec_uttid, dec_score = self.ps.get_hyp()
            
            # Detection must have a minimal score to be valid
            if dec_score >= self.configuration['keyword_score']:
                log.msg("======================")
                log.msg("%s keyword detected" % self.botname)
                log.msg("score: {}".format(dec_score))
                
                # Score stats
                self.scores.append(dec_score)
                log.msg("score: min {}, moy {}, max {}".format(min(self.scores), sum(self.scores)/len(self.scores), max(self.scores)))

                # Start voice recording
                self.failed = 0
                self.keyword_identified = 1
                self.record()
            
            # Score was too low
            else:
                log.msg("I recognized the %s keyword but I think it's a false positive according the %s score" %
                        (self.botname, dec_score))

    def stop_recording(self, play_sound = True):
        """Cancel current recording"""
        if self.recording_state == True:
            log.msg("stop_recording : player.play('pi-cancel')")
            self.recording_state = False
            self.pipeline.set_state(gst.STATE_PLAYING)

    def record(self):
        """Record voice, recognize spoken text and send it to the server"""
        self.pipeline.set_state(gst.STATE_PAUSED)
        self.recording_state = True
        # This content type (raw) allow to send data from mic directly to Wit and stream chunks
        # thanks to the generator
        log.msg(" * Contacting Wit")
        CONTENT_TYPE = 'raw;encoding=signed-integer;bits=16;rate=16000;endian=little'
        try:
            result = self.wit.post_speech(data=RecorderSingleton.get(configuration=self.configuration).capture_audio(),
                                        content_type=CONTENT_TYPE)
        except:
            # Cancel current record
            result = ""
        
        # Play record end sound
        player.play('pi-cancel')
        
        # ASR returned no text
        if len(result) == 0:
            self.stop_recording(play_sound = False)
        else:
            # Send recognized text to the server
            log.msg(result)
            self.lisaclient.sendMessage(message=result['msg_body'], type='chat', dict=result['outcome'])
            self.stop_recording(play_sound = False)

    def get_pipeline(self):
        """Return Gstreamer pipeline"""
        return self.pipeline
