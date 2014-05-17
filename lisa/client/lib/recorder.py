import alsaaudio
from lisa.client.lib import player

class Loader():
    def __init__(self, end, every):
        self.end = end / every - 1
        self.every = every
        self.progress = '.'

    def _clear_line(self):
        ''' Clear one terminal line '''
        print '\x1b[1A',

    def __call__(self, i):
        ''' Print loader for the ith time '''
        if not i % self.every:
            return
        self._clear_line()
        print '[Recording]' + self.progress * (i/2) + ' ' * (self.end - (i/2)) + '[Recording]'


class Recorder:
    def __init__(self, configuration):
        self.configuration = configuration

        # Microphone stream config.
        self.chunk = 1024  # CHUNKS of bytes to read each time from mic
        self.channels = 1
        self.rate = 16000

        self.RECORD_SECONDS = configuration['record_seconds']
        self.SLEEP_TIME = configuration['sleep_time']


    def capture_audio(self):
        def setup_mic():
            inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL)
            inp.setchannels(self.channels)
            inp.setrate(self.rate)
            inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            inp.setperiodsize(self.chunk)
            return inp
        player.play('pi-listening')
        loader = Loader(self.SLEEP_TIME * self.RECORD_SECONDS, 2)
        inp = setup_mic()

        print "\n[*]> Starting Recording\n"
        for i in xrange(0, self.rate / self.chunk * self.RECORD_SECONDS):
            loader(i)
            _, data = inp.read()
            yield data
        print "[*]> Ready Recognize Voice\n"

class RecorderSingleton(object):
    """
    Singleton version of the Recorder.

    Being a singleton, this class should not be initialised explicitly
    and the ``get`` classmethod must be called instead.
    """

    __instance = None

    def __init__(self):
        """
        Initialisation: this class should not be initialised
        explicitly and the ``get`` classmethod must be called instead.
        """

        if self.__instance is not None:
            raise Exception("Singleton can't be created twice !")

    def get(self, configuration):
        """
        Actually create an instance
        """
        if self.__instance is None:
            self.__instance = Recorder(configuration=configuration)
        return self.__instance
    get = classmethod(get)
