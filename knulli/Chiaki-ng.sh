#!/bin/bash
# Chiaki-ng.sh — launcher Tools trên Knulli (Brick Pro).
# Payload tại /userdata/system/chiaki (files/ của repo chiaki-ng).
APP=/userdata/system/chiaki

if [ ! -e /mnt/SDCARD ]; then
  mkdir -p /mnt 2>/dev/null
  ln -sfn /userdata /mnt/SDCARD 2>/dev/null
fi

exec sh "$APP/launch.sh"
