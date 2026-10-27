#!/bin/sh
# 2-pass H.264 High delivery encode of a master (channel upload spec ~12 Mbps); AAC 192k 48 kHz.
# The video bitrate is capped so the file stays under ~90 MB (GitHub's 100 MB file limit) for long reels.
# usage: encode_delivery.sh master.mp4 out.mp4
set -e
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1")
KB=$(python3 -c "print(int(min(12000, 90*8*1000/float('$DUR') - 260)))")
T=$(mktemp -d)
ffmpeg -y -v error -i "$1" -c:v libx264 -preset slow -b:v ${KB}k -maxrate $((KB*4/3))k -bufsize $((KB*2))k -profile:v high -pix_fmt yuv420p -pass 1 -passlogfile "$T/p" -an -f mp4 /dev/null
ffmpeg -y -v error -i "$1" -c:v libx264 -preset slow -b:v ${KB}k -maxrate $((KB*4/3))k -bufsize $((KB*2))k -profile:v high -pix_fmt yuv420p -pass 2 -passlogfile "$T/p" -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$T/out.mp4"
mv "$T/out.mp4" "$2"          # appears only when complete
rm -rf "$T"
