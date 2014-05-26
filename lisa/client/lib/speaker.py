# -*- coding: UTF-8 -*-

# Imports
from lisa.client.ConfigManager import ConfigManagerSingleton
import threading
import os
import gettext
from lisa.client.lib import player
from Queue import Queue
from time import sleep
from subprocess import call
import urllib
from urllib import urlencode, urlopen
from random import randint
from twisted.python import log

soundfile = 'tts-output'
soundpath = '/tmp/'

configuration = ConfigManagerSingleton.get().getConfiguration()
path = '/'.join([ConfigManagerSingleton.get().getPath(), 'lang'])
_ = translation = gettext.translation(domain='lisa', localedir=path, fallback=True,
                                              languages=[configuration['lang'].split('-')[0]]).ugettext


# System utterance definition : key : {(weight1, message1), (weight2, message2)}
# Speaker will randomly choose a message in list, balanced by weights
_utterances = {
    'yes':             {(5, _("Yes ?")),
                        (1, _("I'm listening"))
                       },
    'error_conf':      {(1, _("My configuration file is not readable")),
                        (1, _("There's an error with my configuration file"))
                       },
    'not_understood':  {(1, _("I didn't understood your question")),
                        (1, _("I didn't understood, can you repeat please ?"))
                       },
    'ready':           {(3, _("I'm ready ok")),
                        (1, _("Initialization completed")),
                        (1, _("I'm ready to answer your questions"))
                       },
    'no_server':       {(1, _("Sorry, I can't connect to the server")),
                        (1, _("I can't join the server, please check your connection"))
                       },
    'lost_server':     {(1, _("An error happened, I'm not available anymore")),
                        (1, _("My connection was interrupted, please wait"))
                       }
    }

class Speaker(threading.Thread):
    """
    Speaker class is a singleton managing TTS for the client
    Some utterance are system (ex : "I'm ready"), and are temporarily generated in /tmp, to limit TTS engine calls
    """
    # Singleton instance
    __instance = None

    # TTS engine enum
    _engines = type('Enum', (), dict({"pico": 1, "voicerss": 2}))

    def __init__(self):
        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

        # Init thread class
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.configuration = ConfigManagerSingleton.get().getConfiguration()

        self.queue = Queue([])
        self.lang = "en-EN"
        if self.configuration.has_key('lang'):
            self.lang = self.configuration['lang']
        if self.configuration.has_key("tts") == False or self.configuration["tts"].lower() == "pico"or self.configuration["tts"].lower() == "picotts":
            self.engine = "pico"
            self.ext = "wav"
        elif self.configuration["tts"].lower() == "voicerss" and "voicerss_key" in self.configuration:
            self.engine = "voicerss"
            self.ext = "ogg"
            self.voicerss_key = self.configuration["voicerss_key"]
        else:
            player.play_block("error_conf")
            return

        # Init pre-synthetized utterances
        self._init_sys_utterance()

        # Start thread
        threading.Thread.start(self)

    def _start(self):
        # Create singleton
        if self.__instance is None:
            self.__instance = Speaker()

    def _speak(self, msg, block = True):
        # Queue message
        if self.__instance is not None:
            self.__instance.queue.put(msg)

            # Waits the end
            if block == True:
                self.__instance.queue.join()

    def _stop(self):
        # Raise stop event
        if self.__instance is not None:
            self.__instance._stopevent.set()
            self.__instance = None

        # Free player
        player.play_free()

    # Export class method
    start = classmethod(_start)
    speak = classmethod(_speak)
    stop = classmethod(_stop)

    def run(self):
        """
        Recorder main loop
        """
        # Thread loop
        while not self._stopevent.isSet():
            # Wait queue
            if self.queue.empty():
                sleep(.1)
                continue

            # Get message
            data = self.queue.get()
            filename = soundpath + soundfile + "." + self.ext

            # System utterances
            if _utterances.has_key(data):
                # Randomize a weight
                weight = randint(1, sum((msg[0] for msg in _utterances[data])))
                for i, msg in enumerate(_utterances[data]):
                    weight = weight - msg[0]
                    if weight <= 0:
                        break

                # Create filename
                filename = "%s%s_%s_%d.%s" % (soundpath, self.engine, data, i, self.ext.lower())

            # Pico TTS
            elif self.engine == "pico":
                call(['/usr/bin/pico2wave', '-w', filename, '-l', self.lang, '"'+ data + '"'])

            # VoiceRSS
            elif self.engine == "voicerss":
                url = urlopen("http://api.voicerss.org/?%s" % urlencode({"r": 1, "c": self.ext.upper(),
                                                                         "f": "16khz_16bit_mono",
                                                                         "key": self.voicerss_key,
                                                                         "src": data.encode('UTF-8'),
                                                                         "hl": self.lang}))
                with open(os.path.basename(filename), "wb") as f:
                    f.write(url.read())

            # Play synthetized file
            if os.path.exists(filename):
                log.msg(_("Playing generated TTS"))
                player.play_block(sound = filename, path = soundpath, ext = self.ext)
            else:
                print _("There was an error creating the output file %(filename)s" % {'filename': str(filename)})

            # Remove message from queue
            self.queue.task_done()

    def _init_sys_utterance(self):
        """
        Generate system utterance
        """
        for utt in _utterances:
            for i, msg in enumerate(_utterances[utt]):
                filename = "%s%s_%s_%d.%s" % (soundpath, self.engine, utt, i, self.ext.lower())

                # If already generated
                if os.path.isfile(filename):
                    os.remove(filename)

                print _("Generating %(filename)s : '%(message)s'" % {'filename': str(filename), 'message': msg[1]})

                # VoiceRSS
                if self.engine == "voicerss":
                    urllib.urlretrieve("http://api.voicerss.org/?%s" % urllib.urlencode({"c": self.ext.upper(),
                                                                                         "r": 1,
                                                                                         "f": "16khz_16bit_mono",
                                                                                         "key": "03e60c7e670b405f9210cd025c2bb440",
                                                                                         "src": msg[1],
                                                                                         "hl": self.lang}), filename)

                # PicoTTS
                elif self.engine == "pico" and not os.path.isfile(filename):
                    call(['/usr/bin/pico2wave', '-w', filename, '-l', self.lang, '"'+ msg[1] + '"'])
