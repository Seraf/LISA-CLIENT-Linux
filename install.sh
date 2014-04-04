#!/bin/sh
sudo apt-get install python-dev build-essential gstreamer0.10-plugins-good python-gobject python-gi gstreamer0.10-pocketsphinx gstreamer0.10-alsa
sudo pip install -r requirements.txt
cp lisa/configuration/lisa.json.sample lisa/configuration/lisa.json
