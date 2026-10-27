#!/bin/sh
# 2-pass ~12 Mbps H.264 High delivery encode of a master (channel upload spec); AAC 192k 48 kHz.
# usage: encode_delivery.sh master.mp4 out.mp4
set -e
T=$(mktemp -d)
ffmpeg -y -v error -i "$1" -c:v libx264 -preset slow -b:v 12M -maxrate 16M -bufsize 24M -profile:v high -pix_fmt yuv420p -pass 1 -passlogfile "$T/p" -an -f mp4 /dev/null
ffmpeg -y -v error -i "$1" -c:v libx264 -preset slow -b:v 12M -maxrate 16M -bufsize 24M -profile:v high -pix_fmt yuv420p -pass 2 -passlogfile "$T/p" -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$2"
rm -rf "$T"
