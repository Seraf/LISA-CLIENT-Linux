.. _install:

Install
=============

LISA Client
-----------
First, install the LISA application : ::

    git clone https://github.com/Seraf/LISA-CLIENT-Linux.git

or if you don't have git (update will be easier with git): ::

    curl -L https://github.com/Seraf/LISA-CLIENT-Linux/tarball/master | tar xz

You now have to install some things to make it working : ::

    sudo apt-get install python-dev python-openssl python-setuptools

If you don't have "pip" to install python packages, I recommend it ! : ::

    sudo easy_install pip

Then, install the python dependencies for LISA : ::

    sudo pip install twisted

Speech Dispatcher
-----------------
LISA Linux Client rely on Speech Dispatcher software. You will be able to add new tts engine in Speech Dispatcher as module. You won't have to add new code on LISA, just tell in the config file the module you want to use.

The install of Speech Dispatcher is easy : ::

    sudo apt-get install speech-dispatcher python-speechd

Be carefull, on latest packages (depending your distro), python-speechd is for python3. You need to find the python 2.7 version (maybe on old packages) or install it from sources.
The Linux client actually use python 2.7, I'm stuck to this version because of Twisted. Twisted is currently migrating to python 3, and when it will be done, it will play fine.

Now you have to "configure" new modules. If you want to use the pico libtts (best free engine on Linux) you have to edit /etc/speech-dispatcher/speechd.conf to uncomment the line : ::

    AddModule "pico-generic" "sd_generic"     "pico-generic.conf"

Raspberry
---------

Pico libtts
^^^^^^^^^^^
On raspberry pi, there is no libttspico build. You can install it with the package I have compiled on a Raspbian Wheezy : ::

    sudo dpkg -i package/libttspico0_1.0+git20110131-2_armhf.deb package/libttspico-data_1.0+git20110131-2_all.deb package/libttspico-dev_1.0+git20110131-2_armhf.deb package/libttspico-utils_1.0+git20110131-2_armhf.deb

PulseAudio
^^^^^^^^^^
Raspberry is funny but when you have to play with audio configuration (and generally on all Linux), it quickly become a nightmare. Here is what I have done to make it working :
First, install Pulseaudio : ::

    sudo apt-get install gstreamer0.10-pulseaudio libao4 libasound2-plugins libgconfmm-2.6-1c2 libglademm-2.4-1c2a libpulse-dev libpulse-mainloop-glib0 libpulse-mainloop-glib0-dbg libpulse0 libpulse0-dbg libsox-fmt-pulse paman paprefs pavucontrol pavumeter pulseaudio pulseaudio-dbg pulseaudio-esound-compat pulseaudio-esound-compat-dbg pulseaudio-module-bluetooth pulseaudio-module-gconf pulseaudio-module-jack pulseaudio-module-lirc pulseaudio-module-lirc-dbg pulseaudio-module-x11 pulseaudio-module-zeroconf pulseaudio-module-zeroconf-dbg pulseaudio-utils oss-compat -y

Setup ALSA : ::

    sudo cp -pf /etc/asound.conf /etc/asound.conf.ORIG
    sudo echo 'pcm.pulse {
        type pulse
    }

    ctl.pulse {
        type pulse
    }

    pcm.!default {
        type pulse
    }

    ctl.!default {
        type pulse
    }' > /etc/asound.conf

Change default sound driver from alsa to pulseaudio : ::

    sudo cp -fvp /etc/libao.conf /etc/libao.conf.ORIG
    sudo sed -i "s,default_driver=alsa,default_driver=pulse,g" /etc/libao.conf

    sudo cp -fvp /etc/pulse/daemon.conf /etc/pulse/daemon.conf.ORIG

    sudo echo "
    high-priority = yes
    nice-level = 5
    exit-idle-time = -1
    resample-method = src-sinc-medium-quality
    default-sample-format = s16le
    default-sample-rate = 48000
    default-sample-channels = 2" >> /etc/pulse/daemon.conf

Add pi user to the pulse access group : ::

    sudo adduser pi pulse-access

Don't forget to reboot to apply all these modifications : ::

    sudo shutdown -r now
