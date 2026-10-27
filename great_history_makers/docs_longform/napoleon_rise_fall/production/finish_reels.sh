#!/bin/sh
# For each chapter reel as its render finishes: decode check, black/freeze scan, QC stage, delivery encode.
cd "$(dirname "$0")/../../.."
P=docs_longform/napoleon_rise_fall/production
LOG=$1
for spec in "ch2:Corsica_and_the_Revolution" "ch3:Italy_Egypt_and_Power" "ch4:Coronation_Ulm_and_Austerlitz" "ch5:Europe_and_Russia" "ch6:Retreat_Exile_and_Return" "ch7:Waterloo_Saint_Helena_and_Legacy"; do
  ch=${spec%%:*}; name=${spec#*:}
  until grep -q "$ch EXIT" "$LOG"; do sleep 20; done
  V=$P/output/map_reels/$ch/napoleon_doc_${ch}_maps_1920x1080_preview.mp4
  ffmpeg -v error -i "$V" -f null - && echo "$ch decode OK"
  ffmpeg -i "$V" -vf blackdetect=d=0.3:pix_th=0.05,freezedetect=n=0.002:d=2.5 -an -f null - 2>&1 | grep -E "black_start|freeze_start" | sed "s/^/$ch /"
  python3 -m ghm4.qc $P/chapters/$ch/maps_storyboard.json "$V" --out $P/output/map_reels/${ch}_qc 2>&1 | tail -1 | sed "s/^/$ch QC /"
  N=$(echo $ch | tr -d c | tr -d h)
  sh $P/encode_delivery.sh "$V" "$P/output/Napoleon_Doc_Ch${N}_${name}_MAPS_1080p.mp4" && echo "$ch encoded"
done
echo ALL DONE
