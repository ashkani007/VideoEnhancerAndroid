"""Map sources for *Napoleon: The Rise and Fall of an Emperor*, in the APPROVED, LOCKED map style
(ghm4/data/map_presets/ghm_original_v1.json; reference render Napoleon_Longform_MapSample_Ulm_Austerlitz_ORIGINAL_STYLE_v2_1080p.mp4).

Only map DATA is authored here: places, routes, rings, stars, labels, dates, camera. The look (land, sea, terrain,
colours, typography, arrows, legend, kicker, date ticker) comes unchanged from ghm4.mapshot. Every map keeps the
graphics scale and arrow stroke inside the preset's measured ranges (checked by build.py and the map_lock test).

Times are either seconds (map-local) or anchors "@<words of the narration>[+/-seconds]": the time at which that phrase
is spoken, relative to the start of the map's first shot. build.py resolves anchors from the planned word timing now,
and from the forced-aligned narration once it exists, so every map event stays on its words.

Coordinates: decimal degrees (lon, lat), WGS84, checked against modern gazetteers. Simplified campaign routes follow
Chandler (Campaigns of Napoleon, S1), Zamoyski / Lieven (1812, S7/S8) and Barbero / Hofschroer (1815, S10/S11).
"""

RHINE = [[9.5, 47.6], [8.6, 47.6], [7.6, 47.56], [7.75, 48.58], [8.47, 49.49], [8.27, 50.0], [7.6, 50.36], [6.96, 50.94],
         [6.77, 51.23], [5.86, 51.84], [4.3, 51.9]]
DANUBE = [[8.5, 47.95], [9.99, 48.4], [11.42, 48.76], [12.1, 49.02], [13.46, 48.57], [14.29, 48.31], [16.37, 48.21],
          [17.1, 48.14], [17.6, 47.7], [19.04, 47.5], [18.9, 46.0]]
ALPS = [[5.8, 44.6], [6.6, 45.5], [7.3, 45.95], [8.5, 46.35], [10.0, 46.55], [11.8, 46.9], [13.6, 47.15], [15.4, 47.45]]
CARPATHIANS = [[17.6, 48.9], [19.2, 49.35], [20.9, 49.3], [22.4, 49.0], [23.8, 48.1], [24.9, 47.1]]
APENNINES = [[8.4, 44.25], [9.4, 44.45], [10.3, 44.2], [11.3, 43.85], [12.3, 43.45]]
PO = [[7.1, 44.85], [7.69, 45.07], [8.6, 45.13], [9.69, 45.05], [10.8, 45.02], [11.9, 44.95], [12.4, 44.96]]
ADIGE = [[11.12, 46.07], [10.92, 45.6], [10.99, 45.44], [11.35, 45.25], [12.3, 45.18]]
NILE = [[31.0, 27.2], [31.2, 29.0], [31.24, 30.04], [30.9, 30.7], [30.42, 31.42]]
DYLE = [[4.55, 50.55], [4.61, 50.72], [4.7, 50.88], [4.48, 51.03]]
SAMBRE = [[3.9, 50.27], [4.25, 50.38], [4.44, 50.41], [4.86, 50.465]]
DNIEPER = [[33.6, 55.0], [32.05, 54.78], [30.4, 54.5], [30.33, 53.9], [30.4, 52.6]]
BEREZINA = [[28.9, 55.4], [28.5, 54.33], [28.65, 53.3], [29.2, 52.6]]
NIEMEN = [[26.9, 53.6], [25.6, 54.15], [24.3, 54.85], [23.9, 54.9], [22.6, 55.05], [21.3, 55.3]]

COAST = "ghm4/data/europe_ne50m.json"
REGIONS = "ghm2/data/napoleonic_regions.json"

MAPS = {}

# ---------------------------------------------------------------- Chapter 1: the morning of Waterloo (cold open)
MAPS["ch1_waterloo_18jun"] = {
    "_about": "Waterloo, 18 June 1815: the French army south of the ridge, Wellington's army on it (having fallen back "
              "from Quatre Bras toward Brussels), and Blucher's Prussians, beaten at Ligny on 16 June, marching from "
              "Wavre to the French right flank. Positions simplified to army level (Barbero S10, Hofschroer S11). Camera "
              "1.9 -> 1.2 (graphics scale held in the approved range with element_scale 0.15).",
    "bounds": [2.5, 6.5, 49.6, 51.6], "ref_lat": 50.7, "ppu": 920, "coast": COAST, "element_scale": 0.15, "star_scale": 0.62,
    "rivers": [DYLE, SAMBRE],
    "region_labels": [["FRANCE", 3.3, 49.85, 62, "land"], ["NORTH SEA", 2.4, 51.75, 60, "sea"],
                      ["Dyle", 4.73, 50.86, 48, "river"]],
    "places": {"BRUSSELS": [4.35, 50.85], "WATERLOO": [4.41, 50.68], "WAVRE": [4.61, 50.717], "LIGNY": [4.58, 50.51],
               "CHARLEROI": [4.44, 50.41]},
    "routes": [
        {"color": "blue", "points": [[4.44, 50.41], [4.43, 50.52], [4.42, 50.63]], "draw": ["@A Prussian army under", "@A Prussian army under+2.2"],
         "width": 34, "head": 92},
        {"color": "red", "points": [[4.35, 50.85], [4.38, 50.77], [4.40, 50.71]], "draw": ["@A Prussian army under+0.6", "@A Prussian army under+2.6"],
         "width": 34, "head": 92},
        {"color": "red", "points": [[4.58, 50.51], [4.6, 50.62], [4.61, 50.717], [4.53, 50.69], [4.46, 50.665]],
         "legs": [["@beaten by Napoleon only", "@beaten by Napoleon only+2.4", 2], ["@was marching toward the", "@from the east", 4]],
         "width": 30, "head": 84},
    ],
    "dots": [["BRUSSELS", 0.2], ["CHARLEROI", 0.35], ["WAVRE", "@beaten by Napoleon only+2.2", 13]],
    "stars": [["LIGNY", "@beaten by Napoleon only"], ["WATERLOO", "@Wellington had chosen"]],
    "labels": [
        {"place": "BRUSSELS", "dy": -28, "at": 0.3},
        {"place": "CHARLEROI", "dy": 40, "at": 0.45},
        {"place": "LIGNY", "text": "LIGNY · 16 JUNE", "dx": 44, "dy": 8, "align": "l", "at": "@beaten by Napoleon only+0.2", "size": 24},
        {"place": "WAVRE", "dx": 20, "dy": -18, "align": "l", "at": "@beaten by Napoleon only+2.4"},
        {"place": "WAVRE", "text": "PRUSSIANS", "dx": 20, "dy": 10, "align": "l", "at": "@was marching toward the", "preset": "map_label", "size": 20},
        {"place": "WATERLOO", "text": "WATERLOO", "dx": -46, "dy": 10, "align": "r", "at": "@Wellington had chosen+0.2", "size": 29},
    ],
    "camera": [[0.0, 4.42, 50.64, 1.9], ["@beaten by Napoleon only", 4.48, 50.63, 1.5], ["@Wellington had chosen", 4.49, 50.65, 1.25],
               ["@END", 4.49, 50.65, 1.2]],
    "kicker": ["THE BATTLE OF WATERLOO", 0.2],
    "dates": [[0.0, "18 JUNE 1815"]],
    "legend": [["FRENCH ARMY", "blue", 0.8], ["ALLIED & PRUSSIAN ARMIES", "red", 1.4]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 2: Corsica to Paris
MAPS["ch2_corsica_france"] = {
    "_about": "Corsica ceded by Genoa to France (Treaty of Versailles, May 1768) and conquered in 1769 (Ponte Novu); "
              "Napoleone's schooling: Brienne 1779-84, Ecole Militaire, Paris 1784-85 (Dwyer S5, Roberts S2). The route "
              "to Brienne is schematic (the 1778-79 journey went by sea to the mainland and on via Autun).",
    "bounds": [-4.0, 16.0, 39.0, 52.0], "ref_lat": 45.5, "ppu": 170, "coast": COAST, "element_scale": 0.9,
    "rivers": [RHINE], "relief": [ALPS, APENNINES],
    "region_labels": [["KINGDOM OF FRANCE", 2.2, 46.6, 70, "land"], ["MEDITERRANEAN", 4.6, 41.0, 62, "sea"]],
    "places": {"AJACCIO": [8.74, 41.92], "GENOA": [8.93, 44.41], "TOULON": [5.93, 43.12], "BRIENNE": [4.53, 48.39],
               "PARIS": [2.35, 48.86], "CORSICA": [9.05, 42.15]},
    "routes": [
        {"color": "red", "points": [[8.93, 44.41], [9.2, 43.6], [9.15, 42.75]], "draw": ["@the Republic of Genoa", "@handed the island to France"],
         "width": 26, "head": 76},
        {"color": "blue", "points": [[5.93, 43.12], [7.3, 42.7], [8.6, 42.45]], "draw": ["@and French troops had", "@crushed the Corsican fight"],
         "width": 26, "head": 76},
        {"color": "blue", "points": [[8.74, 41.92], [7.4, 42.6], [5.6, 43.25], [4.85, 45.75], [4.4, 47.2], [4.53, 48.39], [2.35, 48.86]],
         "legs": [["@at the age of nine", "@first to the military school", 5], ["@then to the École Militaire", "@then to the École Militaire+2.0", 6]],
         "width": 28, "head": 80},
    ],
    "dots": [["AJACCIO", 0.3], ["GENOA", 0.5], ["TOULON", "@and French troops had"], ["BRIENNE", "@first to the military school"],
             ["PARIS", "@then to the École Militaire+1.8"]],
    "rings": [],
    "labels": [
        {"place": "AJACCIO", "text": "AJACCIO · 1769", "dx": -22, "dy": 8, "align": "r", "at": 0.4},
        {"place": "GENOA", "dy": -28, "at": 0.6},
        {"place": "CORSICA", "text": "CORSICA: FRENCH FROM 1768", "dx": 34, "dy": -64, "align": "l", "at": "@handed the island to France", "preset": "map_label", "size": 20},
        {"place": "TOULON", "dx": -16, "dy": 30, "align": "r", "at": "@and French troops had+0.2"},
        {"place": "BRIENNE", "text": "BRIENNE · 1779", "dx": 22, "dy": 30, "align": "l", "at": "@first to the military school+0.2"},
        {"place": "PARIS", "text": "PARIS · 1784", "dx": -22, "dy": 30, "align": "r", "at": "@then to the École Militaire+2.0"},
    ],
    "camera": [[0.0, 8.6, 43.0, 5.4], ["@His father, Carlo", 8.0, 43.4, 6.2], ["@at the age of nine", 6.4, 45.2, 9.0],
               ["@then to the École Militaire", 5.2, 46.4, 10.4], ["@END", 5.0, 46.6, 10.6]],
    "kicker": ["CORSICA AND FRANCE", 0.2],
    "dates": [[0.0, "1768"], ["@crushed the Corsican fight", "1769"], ["@at the age of nine", "1779"], ["@then to the École Militaire", "1784"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 3: Italy 1796-97
MAPS["ch3_italy_1796"] = {
    "_about": "First Italian campaign (Chandler S1): from Nice and the Riviera through Montenotte (12 Apr 1796) to the "
              "armistice of Cherasco with Piedmont (28 Apr), across the Po to Lodi (10 May), the siege of Mantua "
              "(Jul 1796 - 2 Feb 1797), Arcole (15-17 Nov 1796), Rivoli (14-15 Jan 1797); Austrian relief armies from "
              "the Tyrol along the Adige. Routes simplified.",
    "bounds": [3.0, 17.0, 41.5, 48.5], "ref_lat": 45.0, "ppu": 380, "coast": COAST, "element_scale": 0.5, "star_scale": 0.62,
    "rivers": [PO, ADIGE], "relief": [ALPS, APENNINES],
    "region_labels": [["PIEDMONT", 7.2, 45.35, 50, "land"], ["GULF OF GENOA", 8.9, 43.75, 50, "sea"],
                      ["ADRIATIC", 13.2, 44.4, 54, "sea"], ["Po", 11.7, 44.82, 46, "river"]],
    "places": {"NICE": [7.27, 43.70], "MONTENOTTE": [8.40, 44.40], "CHERASCO": [7.86, 44.65], "LODI": [9.50, 45.31],
               "MILAN": [9.19, 45.46], "MANTUA": [10.79, 45.16], "ARCOLE": [11.28, 45.36], "RIVOLI": [10.81, 45.57],
               "TRENTO": [11.12, 46.07]},
    "routes": [
        {"color": "blue", "points": [[7.27, 43.70], [8.0, 43.95], [8.40, 44.40], [7.86, 44.65], [9.0, 45.0], [9.50, 45.31], [10.2, 45.25], [10.79, 45.16]],
         "legs": [["@Within weeks, he had split", "@Within weeks, he had split+2.6", 2], ["@and forced Piedmont out", "@of the war", 3],
                  ["@Then he drove the Austrians", "@at Lodi", 5], ["@at Lodi+0.6", "@and besieged their great", 7]],
         "width": 27, "head": 74},
        {"color": "red", "points": [[11.12, 46.07], [10.95, 45.75], [10.85, 45.58]], "draw": ["@and at Rivoli-1.6", "@and at Rivoli+0.2"],
         "width": 24, "head": 66},
        {"color": "red", "points": [[12.3, 45.7], [11.75, 45.45], [11.35, 45.37]], "draw": ["@at Arcole-1.6", "@at Arcole+0.1"],
         "width": 24, "head": 66},
    ],
    "dots": [["NICE", 0.3], ["CHERASCO", "@and forced Piedmont out"], ["MILAN", "@at Lodi+0.6", 13], ["MANTUA", "@and besieged their great"]],
    "stars": [["MONTENOTTE", "@Within weeks, he had split+2.6"], ["LODI", "@at Lodi"], ["ARCOLE", "@at Arcole+0.2"], ["RIVOLI", "@and at Rivoli+0.3"]],
    "rings": [["MANTUA", "@and besieged their great+0.4", "@until it surrendered", "red"]],
    "labels": [
        {"place": "NICE", "dy": 34, "at": 0.4},
        {"place": "MONTENOTTE", "dx": 22, "dy": 6, "align": "l", "at": "@Within weeks, he had split+2.8", "size": 22},
        {"place": "CHERASCO", "dx": -22, "dy": 6, "align": "r", "at": "@and forced Piedmont out+0.2", "size": 22},
        {"place": "MILAN", "dy": -26, "at": "@at Lodi+0.8", "size": 22},
        {"place": "LODI", "text": "LODI", "dx": -18, "dy": 30, "align": "r", "at": "@at Lodi+0.2", "size": 24},
        {"place": "MANTUA", "text": "MANTUA", "dx": -22, "dy": 40, "align": "r", "at": "@and besieged their great+0.2", "size": 24},
        {"place": "ARCOLE", "text": "ARCOLE", "dx": 24, "dy": 22, "align": "l", "at": "@at Arcole+0.4", "size": 24},
        {"place": "RIVOLI", "text": "RIVOLI", "dx": -22, "dy": -10, "align": "r", "at": "@and at Rivoli+0.5", "size": 24},
    ],
    "camera": [[0.0, 8.4, 44.6, 4.2], ["@Then he drove the Austrians", 9.4, 45.0, 3.8], ["@and besieged their great", 10.1, 45.2, 3.2],
               ["@He moved faster", 10.0, 45.15, 3.1], ["@END", 9.9, 45.15, 3.3]],
    "kicker": ["THE ITALIAN CAMPAIGN", 0.2],
    "dates": [[0.0, "APRIL 1796"], ["@at Lodi", "MAY 1796"], ["@at Arcole", "NOVEMBER 1796"], ["@and at Rivoli", "JANUARY 1797"],
              ["@until it surrendered", "FEBRUARY 1797"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 3: Egypt 1798-99 (two shots: outward, then Syria and return)
MAPS["ch3_egypt_1798"] = {
    "_about": "Egyptian expedition (Chandler S1, Roberts S2): Toulon (19 May 1798) - Malta (taken 11-12 Jun) - Alexandria "
              "(1-2 Jul) - Cairo / Battle of the Pyramids (21 Jul); Syrian campaign: Jaffa (Mar 1799), siege of Acre "
              "(Mar-May 1799, failed); Bonaparte sailed from near Alexandria on 23 Aug 1799 and landed at Saint-Raphael "
              "near Frejus on 9 Oct. Sea routes schematic.",
    "bounds": [0.0, 38.0, 27.0, 47.0], "ref_lat": 37.0, "ppu": 140, "coast": COAST, "element_scale": 1.2, "star_scale": 0.62,
    "rivers": [NILE],
    "region_labels": [["MEDITERRANEAN", 19.0, 33.0, 70, "sea"], ["EGYPT", 29.0, 28.0, 60, "land"],
                      ["OTTOMAN EMPIRE", 33.5, 38.6, 60, "land"], ["FRANCE", 3.0, 45.6, 60, "land"], ["Nile", 31.55, 28.5, 46, "river"]],
    "places": {"TOULON": [5.93, 43.12], "MALTA": [14.51, 35.90], "ALEXANDRIA": [29.92, 31.20], "CAIRO": [31.20, 30.06],
               "ACRE": [35.07, 32.92], "JAFFA": [34.75, 32.05], "FRÉJUS": [6.74, 43.43]},
    "routes": [
        {"color": "blue", "points": [[5.93, 43.12], [9.5, 39.8], [14.4, 36.1], [22.0, 33.6], [29.92, 31.20], [30.7, 30.7], [31.2, 30.1]],
         "legs": [["@The next year he sailed", "@to threaten Britain's route", 2], ["@to threaten Britain's route", "@With his soldiers came", 4],
                  ["@On land he won battles", "@including the Battle of", 6]],
         "width": 28, "head": 78},
        {"color": "blue", "points": [[31.2, 30.1], [32.4, 30.8], [34.0, 31.4], [34.75, 32.05], [35.0, 32.8]],
         "draw": ["@A campaign into Syria", "@failed before the walls"], "width": 26, "head": 74},
        {"color": "blue", "points": [[29.92, 31.25], [24.0, 33.4], [16.0, 37.6], [10.0, 40.2], [6.8, 43.35]],
         "draw": ["@left his army in Egypt", "@and slipped back to France+1.2"], "width": 28, "head": 78},
    ],
    "dots": [["TOULON", 0.3], ["MALTA", "@to threaten Britain's route"], ["ALEXANDRIA", "@With his soldiers came"], ["JAFFA", "@failed before the walls-0.6", 12],
             ["FRÉJUS", "@and slipped back to France+1.1"]],
    "stars": [["CAIRO", "@including the Battle of"]],
    "rings": [["ACRE", "@failed before the walls", "@and plague spread", "red"]],
    "labels": [
        {"place": "TOULON", "text": "TOULON · MAY 1798", "dy": -28, "at": 0.4},
        {"place": "MALTA", "dy": 36, "at": "@to threaten Britain's route+0.2"},
        {"place": "ALEXANDRIA", "text": "ALEXANDRIA", "dx": -22, "dy": -16, "align": "r", "at": "@With his soldiers came+0.2"},
        {"place": "CAIRO", "text": "PYRAMIDS · 21 JULY", "dx": 26, "dy": 34, "align": "l", "at": "@including the Battle of+0.2", "size": 24},
        {"place": "ACRE", "text": "ACRE", "dx": 26, "dy": -8, "align": "l", "at": "@failed before the walls+0.2", "size": 26},
        {"place": "FRÉJUS", "text": "FRÉJUS · OCT 1799", "dx": 22, "dy": 32, "align": "l", "at": "@and slipped back to France+1.3", "size": 22},
    ],
    "camera": [[0.0, 12.0, 39.5, 13.0], ["@to threaten Britain's route", 17.0, 36.5, 13.0], ["@With his soldiers came", 26.0, 32.5, 9.5],
               ["@including the Battle of", 29.5, 31.2, 8.6], ["@A campaign into Syria", 31.6, 31.4, 8.2], ["@and plague spread", 32.0, 31.6, 8.4],
               ["@left his army in Egypt", 19.0, 38.0, 14.5], ["@END", 14.0, 40.2, 15.5]],
    "kicker": ["THE EGYPTIAN EXPEDITION", 0.2],
    "dates": [[0.0, "MAY 1798"], ["@to threaten Britain's route", "JUNE 1798"], ["@With his soldiers came", "JULY 1798"],
              ["@A campaign into Syria", "1799"], ["@In August 1799", "AUGUST 1799"]],
    "legend": [["FRENCH EXPEDITION", "blue", 0.8]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 4: Ulm-Austerlitz = the APPROVED v2 map, anchored to the narration
MAPS["ch4_ulm_austerlitz"] = {
    "_base": "ghm4/data/maps/campaign_1805_ulm_austerlitz_16x9.json",
    "_about": "The client-approved map (v2, 2026-10-27), unchanged in every visual element; only its event times are "
              "anchored to the narration. Two shots: the march to Vienna, then (after the Trafalgar painting) Austerlitz.",
    "_retime": {   # v2 time -> anchor (piecewise linear between these points)
        0.0: 0.0,
        1.01: "@and marched it to the Rhine",
        3.62: "@Seven army corps swung",
        5.65: "@cut off and surrounded at Ulm",
        7.11: "@In November, the French entered",
        9.86: "@In November, the French entered+2.4",
        10.15: "@On land, the decisive moment",
        12.18: "@near the Moravian village",
        12.47: "@near the Moravian village+0.3",
        15.37: "@END-1.2",
        16.5: "@END",
    },
}

# ---------------------------------------------------------------- Chapter 5: Europe 1806-1811 (three shots)
MAPS["ch5_europe_1806_1811"] = {
    "_about": "Jena-Auerstedt (14 Oct 1806), Berlin (27 Oct 1806), Eylau (7-8 Feb 1807), Friedland (14 Jun 1807), Tilsit "
              "(7-9 Jul 1807) (Chandler S1); the Empire and its allied and dependent states shown with the approved "
              "1811 territory set (ghm2/data/napoleonic_regions.json, simplified, as in the Ep01 Short); Hamburg and Rome "
              "as the Empire's northern and southern cities (annexations 1809-1811, Broers S6).",
    "bounds": [-12.0, 40.0, 34.0, 62.0], "ref_lat": 50.0, "ppu": 120, "coast": COAST, "element_scale": 1.5, "star_scale": 0.62,
    "rivers": [RHINE, DANUBE, NIEMEN], "relief": [ALPS, CARPATHIANS],
    "region_labels": [["GREAT BRITAIN", -2.0, 53.0, 60, "land"], ["RUSSIAN EMPIRE", 31.0, 55.5, 62, "land"],
                      ["OTTOMAN EMPIRE", 25.0, 42.0, 56, "land"], ["ATLANTIC", -9.0, 47.0, 60, "sea"],
                      ["BALTIC SEA", 18.0, 56.4, 52, "sea"], ["MEDITERRANEAN", 6.0, 38.5, 56, "sea"]],
    "places": {"PARIS": [2.35, 48.86], "MAINZ": [8.27, 50.0], "JENA": [11.59, 50.93], "BERLIN": [13.40, 52.52],
               "WARSAW": [21.01, 52.23], "EYLAU": [20.60, 54.39], "FRIEDLAND": [21.01, 54.44], "TILSIT": [21.88, 55.08],
               "HAMBURG": [9.99, 53.55], "ROME": [12.50, 41.90], "MOSCOW": [37.62, 55.76],
               "RHINE_CONF": [10.4, 49.6], "WARSAW_D": [19.8, 51.6], "NAPLES": [15.6, 40.9], "WESTPHALIA": [9.6, 52.0],
               "SPAIN": [-3.7, 40.3], "HOLLAND": [5.6, 52.5]},
    "routes": [
        {"color": "blue", "points": [[8.27, 50.0], [10.4, 50.6], [11.59, 50.93], [13.40, 52.52], [17.0, 52.4], [21.01, 52.23], [20.8, 53.6], [21.01, 54.44], [21.88, 55.08]],
         "legs": [["@In 1806, Prussia went", "@was destroyed in a single", 2], ["@at Jena and Auerstedt", "@In 1807, after the frozen", 3],
                  ["@In 1807, after the frozen", "@slaughter of Eylau", 6], ["@slaughter of Eylau", "@and the victory of Friedland", 7]],
         "width": 28, "head": 78},
    ],
    "regions": [
        {"source": REGIONS, "key": "french_empire_1811", "color": "blue", "alpha": 0.45, "origin": [2.35, 48.86], "reveal": ["@He redrew the map", "@He redrew the map+1.6"]},
        {"source": REGIONS, "key": "french_allies_1811", "color": "blue", "alpha": 0.55, "hatch": True, "origin": [2.35, 48.86], "reveal": ["@He abolished the thousand", "@He abolished the thousand+1.6"]},
    ],
    "dots": [["MAINZ", 0.3, 13], ["BERLIN", "@at Jena and Auerstedt+0.3"], ["WARSAW", "@In 1807, after the frozen+0.4", 13], ["TILSIT", "@and the victory of Friedland+1.0"], ["EYLAU", "@slaughter of Eylau", 12],
             ["HAMBURG", "@France itself stretched from"], ["ROME", "@France itself stretched from+0.8"], ["PARIS", "@He redrew the map"]],
    "stars": [["JENA", "@at Jena and Auerstedt"], ["FRIEDLAND", "@and the victory of Friedland"]],
    "labels": [
        {"place": "JENA", "text": "JENA · 1806", "dx": -20, "dy": 30, "align": "r", "at": "@at Jena and Auerstedt+0.2"},
        {"place": "BERLIN", "dy": -28, "at": "@at Jena and Auerstedt+0.5", "size": 22},
        {"place": "WARSAW", "dy": 34, "at": "@In 1807, after the frozen+0.6", "size": 22},
        {"place": "EYLAU", "text": "EYLAU · FEB 1807", "dx": -22, "dy": -4, "align": "r", "at": "@slaughter of Eylau+0.2", "size": 22},
        {"place": "FRIEDLAND", "text": "FRIEDLAND · JUNE 1807", "dx": 30, "dy": 46, "align": "l", "at": "@and the victory of Friedland+0.2", "size": 22},
        {"place": "TILSIT", "text": "TILSIT", "dx": 22, "dy": -10, "align": "l", "at": "@and the victory of Friedland+1.2", "size": 22},
        {"place": "PARIS", "dy": -28, "at": "@He redrew the map+0.2"},
        {"place": "RHINE_CONF", "text": "CONFEDERATION OF THE RHINE", "at": "@created the Confederation", "preset": "map_label", "size": 20},
        {"place": "WARSAW_D", "text": "DUCHY OF WARSAW", "at": "@and the Duchy of Warsaw", "preset": "map_label", "size": 20},
        {"place": "HOLLAND", "text": "HOLLAND", "dy": -24, "at": "@thrones of Holland", "preset": "map_label", "size": 20},
        {"place": "NAPLES", "text": "NAPLES", "at": "@Naples, Westphalia", "preset": "map_label", "size": 20},
        {"place": "WESTPHALIA", "text": "WESTPHALIA", "dy": -6, "at": "@Westphalia and Spain", "preset": "map_label", "size": 20},
        {"place": "SPAIN", "text": "SPAIN", "at": "@and Spain", "preset": "map_label", "size": 20},
        {"place": "HAMBURG", "dx": 20, "dy": -16, "align": "l", "at": "@France itself stretched from+0.2", "size": 22},
        {"place": "ROME", "dx": -20, "dy": 8, "align": "r", "at": "@France itself stretched from+1.0", "size": 22},
        {"place": "MOSCOW", "dx": -14, "dy": -26, "align": "r", "at": "@Then Russia broke away+0.6"},
    ],
    "camera": [[0.0, 14.0, 52.2, 10.0], ["@In 1807, after the frozen", 17.0, 53.2, 9.6], ["@and the victory of Friedland", 19.0, 53.6, 9.4],
               ["@and the victory of Friedland+3.0", 19.0, 53.6, 9.4],
               ["@He redrew the map", 9.0, 48.5, 17.0], ["@and Spain+2.0", 7.0, 47.5, 19.0],
               ["@France itself stretched from-0.5", 8.0, 47.8, 17.0], ["@Then Russia broke away", 17.0, 51.3, 18.5], ["@END", 19.5, 51.8, 19.0]],
    "kicker": ["MASTER OF EUROPE", 0.2],
    "dates": [[0.0, "1806"], ["@In 1807, after the frozen", "1807"], ["@He redrew the map", "1806–1811"], ["@France itself stretched from", "1811"],
              ["@Then Russia broke away", "1812"]],
    "legend": [["FRENCH EMPIRE 1811", "blue", "@He redrew the map+0.8"], ["ALLIED & DEPENDENT STATES", "blue", "@He abolished the thousand+0.8"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 5: invasion of Russia
MAPS["ch5_invasion_1812"] = {
    "_about": "Invasion of Russia (Zamoyski S7, Lieven S8): Niemen crossing at Kovno 24 Jun 1812, Vilna 28 Jun, Vitebsk, "
              "Smolensk 16-18 Aug; Russian armies of Barclay and Bagration falling back east. The 1811 Empire as in the "
              "approved Ep01 map. Routes simplified.",
    "bounds": [-6.0, 44.0, 44.0, 64.0], "ref_lat": 53.0, "ppu": 120, "coast": COAST, "element_scale": 1.6,
    "rivers": [NIEMEN, DNIEPER, BEREZINA],
    "region_labels": [["RUSSIAN EMPIRE", 33.0, 57.6, 64, "land"], ["BALTIC SEA", 18.5, 57.2, 52, "sea"],
                      ["DUCHY OF WARSAW", 19.6, 51.9, 44, "land"], ["Dnieper", 31.2, 53.6, 44, "river"]],
    "places": {"KOVNO": [23.90, 54.90], "VILNA": [25.28, 54.69], "VITEBSK": [30.20, 55.19], "SMOLENSK": [32.05, 54.78],
               "MOSCOW": [37.62, 55.76], "WARSAW": [21.01, 52.23]},
    "regions": [{"source": REGIONS, "key": "french_allies_1811", "color": "blue", "alpha": 0.42, "hatch": True, "origin": [2.35, 48.86], "reveal": [0.0, 0.4]}],
    "routes": [
        {"color": "blue", "points": [[21.01, 52.23], [22.8, 54.0], [23.90, 54.90], [25.28, 54.69], [28.0, 55.1], [30.20, 55.19], [32.05, 54.78]],
         "legs": [["@Estimates for the whole", "@range from about", 2], ["@and around half of them", "@The Russians retreated", 3],
                  ["@The Russians retreated", "@and burning supplies as", 6]],
         "width": 30, "head": 84},
        {"color": "red", "points": [[26.4, 55.7], [28.6, 56.05], [30.8, 55.95], [33.6, 55.5]], "draw": ["@refusing battle", "@and burning supplies as+0.6"],
         "width": 24, "head": 68},
        {"color": "red", "points": [[25.0, 53.0], [27.6, 53.4], [30.3, 53.9], [32.4, 54.5]], "draw": ["@refusing battle+0.3", "@and burning supplies as+0.9"],
         "width": 24, "head": 68},
    ],
    "dots": [["WARSAW", 0.3, 13], ["KOVNO", "@range from about"], ["VILNA", "@The Russians retreated"], ["VITEBSK", "@refusing battle+1.0", 12],
             ["SMOLENSK", "@and burning supplies as"], ["MOSCOW", 0.5]],
    "labels": [
        {"place": "KOVNO", "text": "NIEMEN · 24 JUNE", "dx": -24, "dy": 40, "align": "r", "at": "@range from about+0.2", "size": 22},
        {"place": "VILNA", "dx": 6, "dy": -26, "at": "@The Russians retreated+0.2", "size": 22},
        {"place": "SMOLENSK", "text": "SMOLENSK · AUGUST", "dy": 44, "at": "@and burning supplies as+0.2", "size": 22},
        {"place": "MOSCOW", "dx": -14, "dy": -26, "align": "r", "at": 0.6},
    ],
    "camera": [[0.0, 26.0, 54.2, 11.5], ["@The Russians retreated", 28.5, 54.6, 11.0], ["@END", 30.0, 55.0, 11.0]],
    "kicker": ["THE INVASION OF RUSSIA", 0.2],
    "dates": [[0.0, "JUNE 1812"], ["@The Russians retreated", "JULY 1812"], ["@and burning supplies as", "AUGUST 1812"]],
    "legend": [["GRANDE ARMÉE", "blue", 0.8], ["RUSSIAN ARMIES", "red", "@refusing battle"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 6: the retreat
MAPS["ch6_retreat_1812"] = {
    "_about": "Retreat from Moscow (Zamoyski S7, Lieven S8): Moscow left 19 Oct 1812; after Maloyaroslavets (24 Oct) the "
              "army was forced back to the devastated Smolensk road via Mozhaisk; Smolensk 9 Nov; Krasnoi 15-18 Nov; "
              "Berezina crossing at Studianka 26-29 Nov, with Kutuzov following and Chichagov and Wittgenstein closing "
              "from south and north. Routes simplified.",
    "bounds": [16.0, 44.0, 47.0, 62.0], "ref_lat": 55.0, "ppu": 150, "coast": COAST, "element_scale": 1.3,
    "rivers": [DNIEPER, BEREZINA, NIEMEN],
    "region_labels": [["RUSSIAN EMPIRE", 34.5, 57.6, 62, "land"], ["Berezina", 27.9, 53.2, 44, "river"]],
    "places": {"MOSCOW": [37.62, 55.76], "MALOYAROSLAVETS": [36.46, 55.01], "SMOLENSK": [32.05, 54.78], "KRASNOI": [31.40, 54.56],
               "BEREZINA": [28.50, 54.33], "VILNA": [25.28, 54.69]},
    "routes": [
        {"color": "blue", "points": [[37.62, 55.76], [36.9, 55.3], [36.46, 55.01], [35.9, 55.45], [34.0, 55.25], [32.05, 54.78], [31.4, 54.56], [30.4, 54.5], [28.6, 54.33]],
         "legs": [["@It was forced back", "@along the same devastated", 2], ["@along the same devastated", "@Hunger, disease, exhaustion", 5],
                  ["@Marshal Ney commanded", "@and the hard frosts", 8]],
         "width": 30, "head": 84},
        {"color": "red", "points": [[36.3, 54.75], [34.5, 54.6], [32.4, 54.35], [31.0, 54.2]], "draw": ["@Hunger, disease, exhaustion", "@destroyed it piece by piece"],
         "width": 24, "head": 68},
        {"color": "red", "points": [[28.0, 52.4], [28.3, 53.3], [28.45, 54.1]], "draw": ["@and the hard frosts", "@finished what the march"], "width": 24, "head": 68},
        {"color": "red", "points": [[28.8, 56.0], [28.7, 55.2], [28.55, 54.6]], "draw": ["@and the hard frosts+0.4", "@finished what the march+0.4"], "width": 24, "head": 68},
    ],
    "dots": [["MOSCOW", 0.3], ["MALOYAROSLAVETS", "@along the same devastated-0.6", 12], ["SMOLENSK", "@Hunger, disease, exhaustion-0.4"],
             ["BEREZINA", "@and the hard frosts"]],
    "stars": [],
    "rings": [["BEREZINA", "@finished what the march", "@END", "red"]],
    "labels": [
        {"place": "MOSCOW", "text": "MOSCOW · 19 OCT", "dx": -16, "dy": -28, "align": "r", "at": 0.4},
        {"place": "MALOYAROSLAVETS", "dx": 18, "dy": 30, "align": "l", "at": "@along the same devastated-0.4", "preset": "map_label", "size": 20},
        {"place": "SMOLENSK", "text": "SMOLENSK · 9 NOV", "dy": -30, "at": "@Hunger, disease, exhaustion-0.2", "size": 22},
        {"place": "BEREZINA", "text": "BEREZINA · LATE NOV", "dx": -26, "dy": -18, "align": "r", "at": "@and the hard frosts+0.2", "size": 24},
    ],
    "camera": [[0.0, 35.0, 55.4, 9.0], ["@Hunger, disease, exhaustion", 33.0, 55.0, 9.4], ["@Marshal Ney commanded", 31.0, 54.7, 9.6], ["@END", 30.0, 54.6, 9.6]],
    "kicker": ["THE RETREAT FROM MOSCOW", 0.2],
    "dates": [[0.0, "OCTOBER 1812"], ["@Marshal Ney commanded", "NOVEMBER 1812"]],
    "legend": [["GRANDE ARMÉE", "blue", 0.8], ["RUSSIAN ARMIES", "red", "@Hunger, disease, exhaustion"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 6: 1813 and Leipzig
MAPS["ch6_leipzig_1813"] = {
    "_about": "1813 (Chandler S1): French victories at Lutzen (2 May) and Bautzen (20-21 May); Austria joined the "
              "coalition in August; the allied armies (Russia, Prussia, Austria, Sweden) converged on Leipzig, 16-19 Oct "
              "1813. Coalition arrows follow the approved Ep01 coalition map.",
    "bounds": [-2.0, 30.0, 42.0, 60.0], "ref_lat": 51.0, "ppu": 200, "coast": COAST, "element_scale": 1.0, "star_scale": 0.62,
    "rivers": [RHINE, DANUBE], "relief": [ALPS, CARPATHIANS],
    "region_labels": [["AUSTRIAN EMPIRE", 16.6, 48.9, 56, "land"], ["BALTIC SEA", 16.5, 55.4, 52, "sea"],
                      ["FRANCE", 3.5, 48.0, 56, "land"]],
    "places": {"PARIS": [2.35, 48.86], "LUTZEN": [12.14, 51.24], "BAUTZEN": [14.42, 51.18], "LEIPZIG": [12.37, 51.34],
               "BERLIN": [13.40, 52.52], "PRAGUE": [14.42, 50.08], "STRALSUND": [13.08, 54.31]},
    "routes": [
        {"color": "blue", "points": [[8.27, 50.0], [10.5, 50.9], [12.14, 51.24], [13.3, 51.15], [14.42, 51.18]],
         "legs": [["@He did raise one", "@and won more battles", 2], ["@and won more battles", "@in the spring of 1813", 4]],
         "width": 28, "head": 78},
        {"color": "red", "points": [[22.5, 52.6], [18.5, 52.0], [15.5, 51.7], [13.0, 51.45]], "draw": ["@But Prussia, and then", "@joined Russia, Britain"], "width": 28, "head": 78},
        {"color": "red", "points": [[13.3, 54.9], [13.2, 53.3], [12.6, 51.75]], "draw": ["@joined Russia, Britain", "@and Sweden against him"], "width": 24, "head": 68},
        {"color": "red", "points": [[16.5, 48.6], [14.6, 49.9], [12.85, 51.0]], "draw": ["@and then Austria", "@joined Russia, Britain+0.8"], "width": 24, "head": 68},
    ],
    "dots": [],
    "stars": [["LUTZEN", "@and won more battles+0.6"], ["BAUTZEN", "@in the spring of 1813"]],
    "rings": [["LEIPZIG", "@In October, at Leipzig", "@and the coalition defeated", "red"]],
    "labels": [
        {"place": "LUTZEN", "text": "LÜTZEN", "dx": -30, "dy": 14, "align": "r", "at": "@and won more battles+0.8", "size": 22},
        {"place": "BAUTZEN", "text": "BAUTZEN", "dx": 22, "dy": 30, "align": "l", "at": "@in the spring of 1813+0.2", "size": 22},
        {"place": "LEIPZIG", "text": "LEIPZIG · 16–19 OCT", "dy": -58, "at": "@In October, at Leipzig+0.3", "size": 26},
        {"place": "LEIPZIG", "text": "BATTLE OF THE NATIONS", "dy": -32, "at": "@in the Battle of the Nations", "preset": "map_label", "size": 20},
        {"place": "BERLIN", "text": "PRUSSIA & RUSSIA", "dx": 70, "dy": -20, "at": "@But Prussia, and then+0.6", "preset": "map_label", "size": 20},
        {"place": "PRAGUE", "text": "AUSTRIA", "dx": 60, "dy": 50, "at": "@and then Austria+0.4", "preset": "map_label", "size": 20},
        {"place": "STRALSUND", "text": "SWEDEN", "dx": 0, "dy": -30, "at": "@and Sweden against him", "preset": "map_label", "size": 20},
    ],
    "camera": [[0.0, 11.6, 51.0, 7.6], ["@But Prussia, and then", 13.6, 51.5, 8.2], ["@In October, at Leipzig", 13.2, 51.4, 6.4], ["@END", 13.1, 51.4, 6.2]],
    "kicker": ["THE SIXTH COALITION", 0.2],
    "dates": [[0.0, "1813"], ["@in the spring of 1813", "MAY 1813"], ["@But Prussia, and then", "AUGUST 1813"], ["@In October, at Leipzig", "OCTOBER 1813"]],
    "legend": [["FRENCH ARMY", "blue", 0.8], ["COALITION ARMIES", "red", "@But Prussia, and then"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 6: Elba and the return (two shots)
MAPS["ch6_elba_return"] = {
    "_about": "First abdication at Fontainebleau (6 Apr 1814); exile on Elba (arrived 4 May 1814); left Elba 26 Feb 1815, "
              "landed at Golfe-Juan 1 Mar; Route Napoleon via Grasse, Digne, Laffrey (7 Mar), Grenoble, Lyon (10 Mar), "
              "Paris 20 Mar (Roberts S2). Data and labels follow the approved Ep01 Elba map.",
    "bounds": [-6.0, 20.0, 38.0, 54.0], "ref_lat": 46.0, "ppu": 170, "coast": COAST, "element_scale": 1.5,
    "rivers": [RHINE], "relief": [ALPS, APENNINES],
    "region_labels": [["FRANCE", 0.6, 45.6, 62, "land"], ["MEDITERRANEAN", 6.0, 40.8, 52, "sea"], ["ITALY", 12.6, 43.3, 50, "land"]],
    "places": {"FONTAINEBLEAU": [2.70, 48.40], "PARIS": [2.35, 48.86], "ELBA": [10.32, 42.80], "GOLFE-JUAN": [7.08, 43.57],
               "GRENOBLE": [5.72, 45.19], "LYON": [4.83, 45.76]},
    "routes": [
        {"color": "blue", "points": [[2.7, 48.4], [3.9, 46.6], [4.81, 43.95], [6.77, 43.42], [8.6, 43.0], [10.1, 42.82]],
         "draw": ["@a small island off the coast", "@of an island realm"], "width": 28, "head": 80},
        {"color": "blue", "points": [[10.32, 42.8], [8.6, 43.35], [7.08, 43.57], [6.25, 44.6], [5.72, 45.19], [4.83, 45.76], [3.4, 47.6], [2.45, 48.75]],
         "legs": [["@He stayed less than", "@He stayed less than+1.6", 2], ["@Town after town", "@On the twentieth of March", 5],
                  ["@On the twentieth of March", "@he was back in the Tuileries", 7]],
         "width": 28, "head": 80},
    ],
    "rings": [["FONTAINEBLEAU", 0.4, 1.4, "red"]],
    "dots": [["FONTAINEBLEAU", 0.3, 13], ["ELBA", "@of an island realm"], ["GOLFE-JUAN", "@He stayed less than+1.5", 12],
             ["GRENOBLE", "@Town after town", 12], ["LYON", "@Town after town+1.2", 12], ["PARIS", "@he was back in the Tuileries"]],
    "labels": [
        {"place": "FONTAINEBLEAU", "text": "FONTAINEBLEAU", "dy": 60, "at": 0.45},
        {"place": "FONTAINEBLEAU", "text": "ABDICATION · 6 APRIL", "dy": 92, "at": 0.8, "preset": "map_label", "size": 20},
        {"place": "ELBA", "dy": -32, "at": "@of an island realm+0.1"},
        {"place": "GOLFE-JUAN", "text": "GOLFE-JUAN · 1 MARCH", "dx": -16, "dy": 30, "at": "@He stayed less than+1.6", "preset": "map_label", "align": "r", "size": 20},
        {"place": "GRENOBLE", "dx": 18, "dy": 6, "align": "l", "at": "@Town after town+0.2", "preset": "map_label", "size": 20},
        {"place": "LYON", "dx": -18, "dy": 6, "align": "r", "at": "@Town after town+1.4", "preset": "map_label", "size": 20},
        {"place": "PARIS", "text": "PARIS · 20 MARCH", "dx": -24, "dy": -4, "align": "r", "at": "@he was back in the Tuileries+0.2"},
    ],
    "camera": [[0.0, 4.0, 46.9, 9.0], ["@a small island off the coast", 4.8, 46.0, 10.5], ["@of an island realm", 6.3, 44.2, 11.5],
               ["@Town after town", 6.0, 44.6, 11.5], ["@END", 5.0, 45.6, 11.5]],
    "kicker": ["EXILE AND RETURN", 0.2],
    "dates": [[0.0, "APRIL 1814"], ["@He stayed less than", "MARCH 1815"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 7: the Belgian campaign, 15-18 June 1815
MAPS["ch7_belgium_1815"] = {
    "_about": "Waterloo campaign (Barbero S10, Hofschroer S11): the French crossed the Sambre at Charleroi on 15 Jun 1815; "
              "16 Jun Ligny (Napoleon beat Blucher) and Quatre Bras (Ney held by Wellington); 17 Jun the Prussians fell "
              "back north to Wavre and Wellington to the ridge of Mont-Saint-Jean south of Waterloo. Simplified to army "
              "level; same scale and element sizes as the chapter 1 map.",
    "bounds": [2.5, 6.5, 49.6, 51.6], "ref_lat": 50.7, "ppu": 920, "coast": COAST, "element_scale": 0.15, "star_scale": 0.62,
    "rivers": [DYLE, SAMBRE],
    "region_labels": [["FRANCE", 3.3, 49.85, 62, "land"], ["NORTH SEA", 2.4, 51.75, 60, "sea"]],
    "places": {"CHARLEROI": [4.44, 50.41], "LIGNY": [4.58, 50.51], "QUATRE BRAS": [4.46, 50.57], "WAVRE": [4.61, 50.717],
               "WATERLOO": [4.41, 50.68], "BRUSSELS": [4.35, 50.85]},
    "routes": [
        {"color": "blue", "points": [[4.2, 50.18], [4.44, 50.41]], "draw": ["@Napoleon decided to strike", "@into Belgium"], "width": 34, "head": 92},
        {"color": "blue", "points": [[4.44, 50.41], [4.52, 50.47], [4.565, 50.5]], "draw": ["@On the sixteenth of June", "@he beat the Prussians at Ligny"], "width": 30, "head": 84},
        {"color": "blue", "points": [[4.44, 50.41], [4.45, 50.49], [4.455, 50.555]], "draw": ["@while Marshal Ney", "@to a standstill at Quatre"], "width": 30, "head": 84},
        {"color": "red", "points": [[4.35, 50.85], [4.42, 50.7], [4.455, 50.585]], "draw": ["@while Marshal Ney+0.2", "@to a standstill at Quatre+0.2"], "width": 30, "head": 84},
        {"color": "red", "points": [[4.585, 50.53], [4.62, 50.62], [4.61, 50.705]], "draw": ["@They fell back to the north", "@toward Wavre"], "width": 30, "head": 84},
        {"color": "red", "points": [[4.46, 50.6], [4.43, 50.65], [4.415, 50.67]], "draw": ["@still within reach", "@still within reach+1.6"], "width": 30, "head": 84},
    ],
    "dots": [["CHARLEROI", "@into Belgium"], ["BRUSSELS", 0.3], ["WAVRE", "@toward Wavre", 13], ["WATERLOO", "@still within reach+1.5", 13]],
    "stars": [["LIGNY", "@he beat the Prussians at Ligny"], ["QUATRE BRAS", "@to a standstill at Quatre"]],
    "labels": [
        {"place": "BRUSSELS", "dy": -28, "at": 0.4},
        {"place": "CHARLEROI", "text": "CHARLEROI · 15 JUNE", "dx": 22, "dy": 22, "align": "l", "at": "@into Belgium+0.2", "size": 22},
        {"place": "LIGNY", "text": "LIGNY · 16 JUNE", "dx": 44, "dy": 14, "align": "l", "at": "@he beat the Prussians at Ligny+0.2", "size": 24},
        {"place": "QUATRE BRAS", "text": "QUATRE BRAS", "dx": -46, "dy": 4, "align": "r", "at": "@to a standstill at Quatre+0.2", "size": 24},
        {"place": "WAVRE", "text": "WAVRE · 17 JUNE", "dx": 20, "dy": -10, "align": "l", "at": "@toward Wavre+0.2", "size": 22},
        {"place": "WATERLOO", "text": "WATERLOO", "dx": -30, "dy": -14, "align": "r", "at": "@still within reach+1.7", "size": 26},
    ],
    "camera": [[0.0, 4.38, 50.5, 1.9], ["@On the sixteenth of June", 4.5, 50.56, 1.35], ["@They fell back to the north", 4.5, 50.62, 1.3],
               ["@END", 4.49, 50.63, 1.25]],
    "kicker": ["THE WATERLOO CAMPAIGN", 0.2],
    "dates": [[0.0, "JUNE 1815"], ["@into Belgium", "15 JUNE 1815"], ["@On the sixteenth of June", "16 JUNE 1815"],
              ["@They fell back to the north", "17 JUNE 1815"]],
    "legend": [["FRENCH ARMY", "blue", 0.8], ["ALLIED & PRUSSIAN ARMIES", "red", "@while Marshal Ney"]],
    "safe_labels": True,
}

# ---------------------------------------------------------------- Chapter 7: Saint Helena = the approved Ep01 map, anchored
MAPS["ch7_saint_helena"] = {
    "_base": "ghm4/data/maps/saint_helena_1815.json",
    "_about": "The approved Ep01 Saint Helena map, unchanged visually; event times anchored to the narration. HMS "
              "Northumberland sailed in August 1815 and reached Saint Helena on 15 October (Dwyer S13).",
    "_retime": {0.0: 0.0, 0.9: "@This time the British sent", 3.75: "@a volcanic island in the South", 4.2: "@almost two thousand kilometres", 5.19: "@END"},
}


# ---------------------------------------------------------------- Chapter 5 split: campaign 1806-07 (shot 1) and the Empire of 1811 (shots 2-3)
_E = MAPS.pop("ch5_europe_1806_1811")
_CAMPAIGN_LABELS = ("JENA", "BERLIN", "WARSAW", "EYLAU", "FRIEDLAND", "TILSIT")
MAPS["ch5_campaign_1806_1807"] = dict(
    _E, _about="Jena-Auerstedt (14 Oct 1806), Berlin (27 Oct 1806), Eylau (7-8 Feb 1807), Friedland (14 Jun 1807), Tilsit "
               "(7-9 Jul 1807) (Chandler S1). Routes simplified.",
    regions=[], legend=[],
    dots=[d for d in _E["dots"] if d[0] in ("MAINZ", "BERLIN", "WARSAW", "TILSIT", "EYLAU")],
    labels=[lb for lb in _E["labels"] if lb["place"] in _CAMPAIGN_LABELS],
    camera=_E["camera"][:3] + [["@END", 19.2, 53.7, 9.4]],
    dates=_E["dates"][:2])
MAPS["ch5_empire_1811"] = dict(
    _E, _about="The Empire and its allied and dependent states with the approved 1811 territory set "
               "(ghm2/data/napoleonic_regions.json, simplified, as in the Ep01 Short); kingdoms of Napoleon's brothers "
               "(Holland, Naples, Westphalia, Spain), the Confederation of the Rhine and the Duchy of Warsaw (Broers S6, "
               "Esdaile S9); Hamburg and Rome as the Empire's northern and southern cities (annexations 1809-1811).",
    routes=[], stars=[],
    dots=[d for d in _E["dots"] if d[0] in ("PARIS", "HAMBURG", "ROME")],
    labels=[dict(lb, text="RHINE CONFEDERATION", **({"place": "RHINE_CONF"})) if lb["place"] == "RHINE_CONF" else lb
            for lb in _E["labels"] if lb["place"] not in _CAMPAIGN_LABELS],
    camera=[[0.0, 9.0, 48.5, 17.0]] + _E["camera"][5:],
    dates=_E["dates"][2:], kicker=["THE FRENCH EMPIRE", 0.2])
MAPS["ch5_empire_1811"]["places"] = dict(_E["places"], RHINE_CONF=[12.0, 50.3])
