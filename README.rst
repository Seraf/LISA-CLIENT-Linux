State of the project :

.. image:: https://travis-ci.org/Seraf/LISA-CLIENT-Linux.png
 :target: https://travis-ci.org/Seraf/LISA-CLIENT-Linux
 
.. image:: https://badge.waffle.io/seraf/lisa-client-linux.png?label=ready&title=Ready 
 :target: https://waffle.io/seraf/lisa-client-linux
 :alt: 'Stories in Ready'

Overview
########
Actually, it uses pocketsphinx to recognize the LISA keyword, then use Wit speech API (google used at backend) to recognize the sentence.
It sends the sentence to LISA Server.

Clients can be multiple (one per room for example) if needed.

To install it :

```
pip install lisa-client
```

To launch the client :

```
twistd -n lisa-client
```
