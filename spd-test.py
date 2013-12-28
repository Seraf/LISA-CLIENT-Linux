import speechd
import os, json

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
configuration = json.load(open(os.path.normpath(dir_path + '/' + 'configuration/lisa.json')))

client = speechd.Speaker('LISA')
client.set_punctuation(speechd.PunctuationMode.SOME)
client.set_output_module(str(configuration['tts']))
client.set_language(str(configuration['lang']))

client.speak("ceci est un test")
client.close()
