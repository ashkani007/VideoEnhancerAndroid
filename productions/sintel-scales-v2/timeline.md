# Shot-by-shot timeline (v2)

Framing: per clip, faces (YuNet), characters/animals (YOLOX) and saliency are detected on the real frames; the crop is the narrowest window that keeps every subject (+12% margin), but never narrower than the 9:16 width or the upscale limit, and the full frame when the action spans the shot. Height is never cropped. Background: the same shot, blurred and darkened.

| # | Time | Source | Copy | Framing | Crop | Upscale | Subject kept | Narration |
|---|---|---|---|---|---|---|---|---|
| 1 | 00:00.00–00:01.05 | #245 10:10.66 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | She spent years hunting this dragon. |
| 2 | 00:01.05–00:02.11 | #144 05:47.60 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | She spent years hunting this dragon. |
| 3 | 00:02.11–00:02.99 | #244 10:09.42 | 512w | subject-crop (detections+saliency) | 332px | ×1.45 | 100% | She should have looked closer. |
| 4 | 00:02.99–00:03.88 | #249 10:20.40 | 512w | subject-crop (detections) | 368px | ×1.3 | 100% | She should have looked closer. |
| 5 | 00:03.88–00:05.59 | #60 03:02.27 | 720w | full-frame (detections+saliency) | 720px | ×0.67 | 100% | It started on a rooftop, with a baby dragon and a torn, bleeding wing. |
| 6 | 00:05.59–00:06.60 | #62 03:06.82 | 720w | subject-crop (detections+saliency) | 366px | ×1.31 | 100% | It started on a rooftop, with a baby dragon and a torn, bleeding wing. |
| 7 | 00:06.60–00:08.32 | #67 03:10.00 | 720w | subject-crop (detections) | 504px | ×0.95 | 100% | It started on a rooftop, with a baby dragon and a torn, bleeding wing. |
| 8 | 00:08.32–00:09.52 | #75 03:27.20 | 720w | subject-crop (detections) | 218px | ×2.2 | 100% | She carried it home, bandaged the wound, and named it Scales. |
| 9 | 00:09.52–00:10.73 | #78 03:33.26 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | She carried it home, bandaged the wound, and named it Scales. |
| 10 | 00:10.73–00:11.93 | #79 03:36.64 | 512w | subject-crop (detections) | 286px | ×1.68 | 100% | She carried it home, bandaged the wound, and named it Scales. |
| 11 | 00:11.93–00:13.53 | #117 05:09.26 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | She taught it to fly. |
| 12 | 00:13.53–00:14.91 | #124 05:17.57 | 512w | subject-crop (detections) | 218px | ×2.2 | 100% | Then one evening, a full-grown dragon dropped out of the sky, |
| 13 | 00:14.91–00:16.55 | #127 05:20.57 | 512w | subject-crop (saliency+saliency-scene) | 398px | ×1.21 | 100% | Then one evening, a full-grown dragon dropped out of the sky, |
| 14 | 00:16.55–00:17.31 | #128 05:22.32 | 512w | subject-crop (detections) | 218px | ×2.2 | 100% | Then one evening, a full-grown dragon dropped out of the sky, |
| 15 | 00:17.31–00:18.70 | #134 05:28.61 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | snatched Scales in its claws, and was gone. |
| 16 | 00:18.70–00:20.09 | #133 05:26.59 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | snatched Scales in its claws, and was gone. |
| 17 | 00:20.09–00:21.63 | #144 05:45.30 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | She didn't cry for long. |
| 18 | 00:21.63–00:23.82 | #147 05:57.00 | 512w | subject-crop (detections+saliency) | 372px | ×1.29 | 100% | She took a blade and started walking. |
| 19 | 00:23.82–00:25.01 | #152 06:11.00 | 512w | subject-crop (saliency) | 322px | ×1.49 | 100% | Through deserts. Through bamboo forests. Through blizzards that nearly buried her. |
| 20 | 00:25.01–00:26.19 | #153 06:21.19 | 512w | subject-crop (detections+saliency) | 344px | ×1.4 | 100% | Through deserts. Through bamboo forests. Through blizzards that nearly buried her. |
| 21 | 00:26.19–00:27.38 | #158 06:56.68 | 512w | subject-crop (detections+saliency) | 304px | ×1.58 | 100% | Through deserts. Through bamboo forests. Through blizzards that nearly buried her. |
| 22 | 00:27.38–00:28.56 | #156 06:40.50 | 512w | subject-crop (detections) | 342px | ×1.4 | 100% | Through deserts. Through bamboo forests. Through blizzards that nearly buried her. |
| 23 | 00:28.56–00:30.21 | #172 07:31.69 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | Finally, an old shaman told her where the dragons nest. |
| 24 | 00:30.21–00:31.86 | #180 07:50.60 | 512w | subject-crop (saliency) | 218px | ×2.2 | 100% | Finally, an old shaman told her where the dragons nest. |
| 25 | 00:31.86–00:33.24 | #183 08:04.95 | 512w | subject-crop (detections) | 218px | ×2.2 | 100% | Inside the cave, she found a baby dragon. |
| 26 | 00:33.24–00:34.63 | #199 08:56.71 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | Inside the cave, she found a baby dragon. |
| 27 | 00:34.63–00:35.20 | #203 09:01.55 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | Then its parent found her. |
| 28 | 00:35.20–00:35.70 | #204 09:02.58 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | Then its parent found her. |
| 29 | 00:35.70–00:36.27 | #206 09:04.09 | 512w | subject-crop (saliency) | 242px | ×1.98 | 100% | Then its parent found her. |
| 30 | 00:36.27–00:37.85 | #229 09:43.30 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | It had her pinned. It could have finished her right there. |
| 31 | 00:37.85–00:39.43 | #237 09:55.99 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | It had her pinned. It could have finished her right there. |
| 32 | 00:39.43–00:41.21 | #235 09:51.36 | 512w | full-frame (detections+saliency) | 512px | ×0.94 | 100% | It hesitated. |
| 33 | 00:41.21–00:42.52 | #243 10:07.30 | 512w | subject-crop (detections) | 230px | ×2.09 | 100% | She didn't. |
| 34 | 00:42.52–00:45.08 | #248 10:17.06 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | The blade went in, and the dragon fell. |
| 35 | 00:45.08–00:47.02 | #250 10:22.00 | 512w | subject-crop (detections+saliency-scene) | 386px | ×1.24 | 100% | Then she saw the scar on its wing. The wing she had healed. |
| 36 | 00:47.02–00:48.97 | #247 10:14.35 | 512w | subject-crop (saliency) | 322px | ×1.49 | 100% | Then she saw the scar on its wing. The wing she had healed. |
| 37 | 00:48.97–00:51.11 | #261 11:03.37 | 512w | full-frame (detections) | 512px | ×0.94 | 100% | It was Scales. |
| 38 | 00:51.11–00:53.75 | #250 10:31.20 | 512w | subject-crop (detections) | 240px | ×2.0 | 100% | And the face staring back from the pool of blood wasn't a girl's anymore. |
| 39 | 00:53.75–00:56.38 | #254 10:42.00 | 512w | subject-crop (detections) | 292px | ×1.64 | 100% | And the face staring back from the pool of blood wasn't a girl's anymore. |
| 40 | 00:56.38–00:58.98 | #270 11:30.00 | 512w | subject-crop (detections) | 218px | ×2.2 | 100% | (tail) |

## Music cue sheet

| Cue | Start | End | Mood | Motivated by |
|---|---|---|---|---|
| 1 | 0.00 | 3.75 | mystery | "She spent years hunting this dragon." |
| 2 | 3.75 | 11.80 | tender | "It started on a rooftop, with a baby dragon and a torn, bleeding wing." |
| 3 | 11.80 | 13.40 | wonder | "She taught it to fly." |
| 4 | 13.40 | 19.96 | tension | "Then one evening, a full-grown dragon dropped out of the sky," |
| 5 | 19.96 | 28.43 | journey | "She didn't cry for long." |
| 6 | 28.43 | 31.73 | mystery | "Finally, an old shaman told her where the dragons nest." |
| 7 | 31.73 | 34.50 | dread | "Inside the cave, she found a baby dragon." |
| 8 | 34.50 | 39.30 | action | "Then its parent found her." |
| 9 | 39.30 | 41.08 | silence | "It hesitated." |
| 10 | 41.08 | 42.39 | action | "She didn't." |
| 11 | 42.39 | 44.95 | dread | "The blade went in, and the dragon fell." |
| 12 | 44.95 | 48.84 | mystery | "Then she saw the scar on its wing. The wing she had healed." |
| 13 | 48.84 | 58.98 | grief | "It was Scales." |

Braam hits at 0.10s, 34.75s, 41.33s, 49.09s. Score sits -7 dB under the narration level between lines and -17 dB under it while the narrator speaks (60 ms attack / 450 ms release); master -14 LUFS.
