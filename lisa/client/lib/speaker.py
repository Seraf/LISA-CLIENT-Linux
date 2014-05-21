# -*- coding: UTF-8 -*-

# Imports
import threading
import time, os
from lisa.client.lib import player
from collections import deque
from time import sleep
from subprocess import call
import urllib
from urllib import urlencode, urlopen, urlretrieve
from random import randint
from twisted.python import log

soundfile = 'tts-output'
soundpath = '/tmp/'

# System utterance definition : key : {(weight1, message1), (weight2, message2)}
# Speaker will randomly choose a message in list, balanced by weights
_utterances = {
    'yes':             {(5, "Oui"),
                        (1, "Je vous écoute")
                       },
    'error_conf':      {(1, "Mon fichier de configuration est erronné"),
                        (1, "J'ai détecté une erreur dans mon fichier de configuration")
                       },
    'not_understood':  {(1, "Je n'ai pas compris votre question"),
                        (1, "Je n'ai pas compris, pouvez vous répéter")
                       },
    'ready':           {(3, "Je suis prêt"),
                        (1, "Mon initialisation est terminée"),
                        (1, "Je suis prêt à répondre à vos questions")
                       },
    'no_server':       {(1, "Désolé je n'arrive pas a me connecter au serveur"),
                        (1, "Le serveur est introuvable, veuillez vérifier la connexion")
                       },
    'lost_server':     {(1, "Il s'est produit une erreur, je ne suis plus disponible"),
                        (1, "Ma connexion au serveur est interrompue, veuillez patienter")
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

    def __init__(self, configuration):
        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

        # Init thread class
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.configuration = configuration
        self.queue = deque([])
        self.lang = "en-EN"
        if 'lang' in self.configuration:
            self.lang = self.configuration['lang']
        if "tts" not in self.configuration or self.configuration["tts"].lower() == "pico"or self.configuration["tts"].lower() == "picotts":
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

    def _start(self, configuration):
        # Create singleton
        if self.__instance is None:
            self.__instance = Speaker(configuration)

    def _speak(self, msg):
        # Queue message
        if self.__instance is not None:
            self.__instance.queue.append(msg)

    def _stop(self):
        # Raise stop event
        if self.__instance is not None:
            self.__instance._stopevent.set()
            self.__instance = None

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
            if len(self.queue) == 0:
                sleep(1)
                continue

            # Get message
            data = self.queue.popleft()
            filename = soundpath + soundfile + "." + self.ext

            # System utterances
            if data in _utterances:
                # Randomize a weight
                weight = randint(1, sum((msg[0] for msg in _utterances[data])))
                for i, msg in enumerate(_utterances[data]):
                    weight = weight - msg[0]
                    if weight <= 0:
                        break

                filename = "%s%s_%s_%d.%s" % (soundpath, self.engine, data, i, self.ext.lower())

            # Pico TTS
            elif self.engine == "pico":
                call(['/usr/bin/pico2wave', '-w', filename, '-l', self.lang, '"'+ data + '"'])

            # VoiceRSS
            elif self.engine == "voicerss":
                url = urlopen("http://api.voicerss.org/?%s" % urlencode({"r": 1, "c": self.ext.upper(), "f": "16khz_16bit_mono", "key": self.voicerss_key, "src": data.encode('UTF-8'), "hl": self.lang}))
                with open(os.path.basename(filename), "wb") as f:
                    f.write(url.read())

            # Play synthetized file
            if os.path.exists(filename):
                log.msg("Playing generated TTS")
                player.play_block(sound = filename, path = soundpath, ext = self.ext)
            else:
                print "There was an error creating the output file %s" % filename

    def _init_sys_utterance(self):
        """
        Generate system utterance
        """
        for utt in _utterances:
            for i, msg in enumerate(_utterances[utt]):
                filename = "%s%s_%s_%d.%s" % (soundpath, self.engine, utt, i, self.ext.lower())
                
                # If already generated
                if os.path.isfile(filename):
                    continue
                    
                print "Generating %s : '%s'" % (filename, msg[1])

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
