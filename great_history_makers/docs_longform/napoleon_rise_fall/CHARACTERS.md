# Character references: *Napoleon: The Rise and Fall of an Emperor*

**Machine-readable version:** `comfyui/bible/characters/napoleon.json` (variants), used by `ghm4.illustrate` (`"variants": {"napoleon": "<variant>"}`).

## Consistency method (no InsightFace: its models are non-commercial)
1. **Look development (queued: `jobs/queue/napoleon_longform_poc_v1.json`).**
   - Four head-and-shoulders references (1796, 1805, 1812, 1815), four seeds each.
   - Identical face descriptor; only the age, build, hair and costume change.
2. **Client picks one reference per age.** It becomes that age's `face_reference`, used by the IP-Adapter Plus-Face, plus the style reference for the chapter.
3. **Generation:** every plate with Napoleon uses the same face descriptor + its age variant + the face adapter (weight 0.45). The reviewer rejects candidates whose face drifts.
4. **After about 20 approved Napoleon plates:** train one character LoRA locally (OneTrainer or kohya_ss, 8 GB settings) with age tokens, and lower the face-adapter weight.

## Napoleon by age
| Age (year) | Chapter | Face and build | Hair | Dress |
|---|---|---|---|---|
| 9–15 (1779–85) | Brienne, École Militaire | Thin, serious boy | Long, tied | Blue school uniform with red facings (Brienne) |
| 16–24 (1785–93) | Lieutenant, Toulon | Very thin, sallow, intense | Long, unpowdered, falling to the collar | Blue artillery officer's coat, red facings, white breeches |
| 27 (1796) | Italy | Gaunt, burning eyes | Long and straight, shoulder length | General's blue coat with gold oak-leaf embroidery, tricolour sash, plumed bicorne |
| 30–31 (1799–1800) | Brumaire, Consulate | Still lean | Shortening | First Consul's red velvet coat (official) or general's uniform |
| 35 (1804) | Coronation | Fuller face | Cropped, Roman style | Crimson velvet mantle with golden bees, ermine, gold laurel wreath |
| 36 (1805) | Austerlitz | Fuller face, calm | Short | Green Chasseur à Cheval of the Guard undress coat, white waistcoat and breeches, grey redingote, plain black bicorne worn side-on ("en bataille") |
| 43 (1812) | Russia | Heavier, pale | Short, receding slightly | Same campaign dress; fur-lined greatcoat and fur cap on the retreat |
| 45 (1815) | Hundred Days, Waterloo | Heavy, tired, sallow | Thinning | Grey redingote over the green Guard coat, bicorne |
| 46–51 (1815–21) | Saint Helena | Heavy, then ill and thin at the end | Thin | Green civilian-cut coat, white waistcoat, often in a dressing gown and broad hat in the garden |

**Fixed traits at every age:**
- clean-shaven; grey-blue eyes; strong straight nose; firm mouth; pale olive complexion; dark chestnut hair;
- height about 1.69 m (average for the period);
- right hand often tucked into the waistcoat in **formal portraits only**. This is a portrait convention, not a habit: never in action scenes.

## Supporting characters (references to be generated with the chapters that need them)
| Character | Years | Key traits |
|---|---|---|
| Joséphine de Beauharnais | 1796–1809 | Curly dark hair, high-waisted Empire gowns; mid-thirties in 1796 |
| Marie-Louise of Austria | 1810–14 | Fair hair, Habsburg features, aged 18–22 |
| Wellington | 1815 | Aquiline nose, plain dark blue frock coat, cocked hat, telescope |
| Blücher | 1815 | Aged 72, white moustache, Prussian hussar general |
| Tsar Alexander I | 1805–14 | Tall, fair, balding, green Russian uniform with epaulettes |
| Kutuzov | 1805, 1812 | Elderly, heavy, blind in the right eye (head wound), white cap |
| Marshal Ney | 1812–15 | Red hair, sideburns; rearguard commander |
| Marshal Soult | 1805 | Heavy-set; IV Corps at the Pratzen |
| Pope Pius VII | 1804 | White cassock, aged 62 |

## Prompt template
`[framing], [scene with year and place], Napoleon Bonaparte, clean-shaven, lean face, strong jaw, straight nose, heavy dark brows, small grey-blue eyes, pale olive complexion, dark chestnut hair, [age variant: age, build, hair, dress], [style ghm_painterly_v2 positive], [chapter light], [16:9 composition]`.
The negative prompt adds the style negatives plus "young boy" or "old man" when the age must not drift.
