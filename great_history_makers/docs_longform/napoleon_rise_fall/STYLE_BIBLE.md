# Visual style bible: *Napoleon: The Rise and Fall of an Emperor* (long-form, 16:9)

**Status:** proposal. It becomes binding after the client approves the proof of concept.
**Replaces:** the minimalist stand-in look of the Shorts preview, which the client rejected. The flat vector church, the simplified skyline and the empty snowfields are **never** used again.
**Machine-readable version:** `comfyui/bible/style_ghm_painterly_v2.json`.

## 1. The look in one sentence
Cinematic historical digital paintings in the tradition of nineteenth-century academic battle painting, brought to life with subtle camera moves, parallax and weather, held together by animated campaign maps.

**Visual references** (all public domain, for look only; we never copy compositions):
- Meissonier, *1814, Campagne de France* and *1807, Friedland*;
- Horace Vernet;
- Édouard Detaille, *Le Rêve*;
- Vasily Vereshchagin's 1812 series;
- Adolph Northen, *Napoleon's Retreat from Moscow*;
- Lady Butler, *Scotland Forever!*;
- Gros, *Bonaparte at Arcole* (portrait mood).

## 2. Rules for every painted plate
| Topic | Rule |
|---|---|
| Drawing | Realistic anatomy and proportions; horses with correct gait and legs; no stylisation, no cel shading, no vector shapes, no "poster" flatness |
| Detail | Rich environment in every frame: terrain, weather, architecture of the right period, equipment, crowds with individual figures. **No empty backgrounds** |
| Light | One motivated key light per plate (sun, fire, overcast sky); atmospheric perspective; volumetric haze and smoke. The time of day follows the chapter's palette (§4) |
| Texture | Visible but fine brushwork at full size; light canvas texture; one shared grain level in the renderer (0.006) |
| Composition | 16:9, rule-of-thirds focus, **three depth layers** (foreground / midground / background) so the renderer can add parallax; the lower fifth stays calm for subtitles; titles go in the upper band |
| Costume | Period-accurate uniforms per year and nation (§5); Napoleon's dress follows his age variant (CHARACTERS.md) |
| Height | Napoleon is about 1.69 m: average for his time. Never caricature-short |
| Gore | Wounded and dead are shown with restraint: no blood close-ups (YouTube suitability) |
| Text in images | None. All text is added by the renderer |
| Reconstruction | Every plate is an artistic reconstruction; the first plate of each chapter carries a small "artistic reconstruction" note when it shows a specific scene |

## 3. Motion language (renderer: `ghm4`, landscape format)
- **Camera:** one motivated move per plate: a slow push-in for tension, a pull-back for reveals, a lateral drift for panoramas. Zoom range 3–8 %; ease in/out; no fast whip-pans inside a scene.
- **Depth:**
  - an automatic matte (BiRefNet hybrid, QA-gated) separates foreground figures for parallax 0.4–0.6;
  - plates whose matte fails QA play as one layer, never with a wrong matte.
- **Atmosphere:**
  - smoke bands and cannon puffs (Austerlitz, Borodino, Waterloo);
  - snow particles and wind (Russia);
  - embers and flicker (Moscow);
  - drifting fog (dawn scenes);
  - cloud drift; flags; marching ranks.
- **Characters:**
  - at most a blink in close-ups, plus subtle hand or cloth motion;
  - no 2.5D or 3D character animation, no lip-sync, no paid image-to-video.
- **Transitions:** dissolve between paintings of the same chapter; ink wipe into maps; a soft flash (strength ≤ 0.5) only on chapter breaks; cut on narration pauses.

## 4. Chapter palettes (light and colour script)
| Chapter | Light | Palette |
|---|---|---|
| Cold open: Waterloo | Wet grey morning, storm light by evening | Mud umber, slate, faded scarlet, gunsmoke white |
| Corsica and the Revolution | Mediterranean sun → candle-lit schoolrooms → Paris street smoke | Ochre, olive, cream, tricolour accents |
| Italy and Egypt | Hard spring sun; desert gold | Alpine green, sand, cobalt sky |
| Coronation and Austerlitz | Cathedral gold; winter dawn and mist | Crimson and gold → frost blue and sunrise amber |
| Master of Europe | Clear daylight, parade grandeur; Spanish sun with dark shadow | Imperial blue, white, brass; burnt sienna for Spain |
| Russia | Dust and heat → fire at night | Wheat gold, smoke brown → furnace orange |
| Retreat and collapse | Overcast, freezing, low sun | Blue-grey, dirty white, small warm fire accents |
| Hundred Days and Waterloo | Spring Provence; rain and evening light | Lavender, green → mud, smoke, red sunset |
| Saint Helena and legacy | Atlantic dusk; marble interiors of Les Invalides | Ocean blue, violet, gold dome light |

## 5. Uniform and object reference (per year)
- **French line infantry:**
  - **1796:** mixed, ragged dress in Italy.
  - **1805–1812:** dark blue habit-veste, white lapels, red collar and cuffs, white breeches, black gaiters, shako with brass plate (bicorne until about 1807 in some regiments).
  - **1812 onward:** the 1812 "Bardin" short-tailed jacket.
- **Imperial Guard:** Grenadiers à pied in bearskins with red plumes; Chasseurs à cheval in green with colpack (Napoleon's escort).
- **Standards:**
  - **1804 pattern:** white lozenge, blue and red corner triangles.
  - **1812 onward:** vertical tricolour.
  - Gilt eagle finial throughout.
- **Austria:** white coats, black helmets or shakos.
- **Russia:** dark green coats, white or green trousers, shakos (1812).
- **Prussia:** dark blue.
- **Britain:** red coats, Belgic shako (1815), Highlanders in kilts; Wellington in a plain dark blue civilian-cut coat.
- **Artillery and horses:** French Gribeauval guns in olive green; Napoleon's greys (Marengo, Vizir) as era-appropriate options.

## 6. Maps (the client's favourite element: a major storytelling device, not a transition)
- **Look:** the approved parchment campaign atlas:
  - sand-coloured land, navy sea with shoreline ripples, river blue;
  - relief hatching for mountains;
  - Natural Earth 1:50m coastlines (public domain).
- **Content:**
  - campaign routes as thick arrows with marching dashes;
  - **moving army positions** as unit blocks (NATO-style infantry cross), with corps numerals (I–VI, CAV) and a legend;
  - date ticker, battle stars, encirclement rings, territorial reveals spreading from the capital.
- **Colour code:**

  | Side | Colour |
  |---|---|
  | France and allies | Imperial blue |
  | Austria | White |
  | Russia | Green |
  | Prussia | Black |
  | Britain | Red |
  | Generic enemy movement | Red arrow |
  | Encirclement / defeat | Red ring |

- **Layout (16:9):**
  - kicker and date top centre; legend top left;
  - labels never cross the frame edge, enter the title band or sit under the subtitles (`safe_labels`, checked by `ghm4.qc`).
- **Accuracy:**
  - dates and places from the cited sources;
  - routes simplified, with the simplification stated in each map's `_about` and in the production notes;
  - schematic positions labelled as such.

## 7. Typography and subtitles
- **Typeface:** Caladea (serif).
  - Gold tracked kicker over an ivory title.
  - Chapter cards: number + title + years, 3 s, over a darkened plate.
- **Subtitles:** ivory with a dark outline, y 975/1080, at most two lines, timed to the forced-aligned narration.
- **Branding:** the original gold emblem at the upper left; end signature at the end.

## 8. Sound
- **Narration:** the approved ElevenLabs voice Max (`Gfpl8Yo74Is0W6cPUWWT`), only after the client approves the script and the credits.
- **Music:** orchestral, minor-key, procedurally generated (`mosaic.audio`, no licences), ducked under the voice; chapter stings on map reveals.
- **Sound effects:** procedural. Drums and marching on maps; cannon, volleys and flutter on battlefields; wind and snow in Russia; fire in Moscow; sea on Saint Helena; bells in Notre-Dame.

## 9. Never again (client feedback, 2026-10-26)
- Flat vector or minimalist environment stand-ins.
- Empty landscapes.
- Code-drawn buildings or characters.
- Placeholder illustrations presented in a video.
- Generic slideshows (each plate gets one motivated move and its own atmosphere).
