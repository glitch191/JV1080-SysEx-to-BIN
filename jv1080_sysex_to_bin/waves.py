"""JV-1080 waveforms and their XV-5080 equivalents (the plug-in uses the XV-5080 wave list).

JV wave names: JV-1080 owner's manual, "Waveform List" (p. 122-123), checked against the names
stored in the JV-1080 program ROM. XV numbers: matched by name against the XV-5080 waveform list;
21 waves renamed on the XV were matched with the factory patches (e.g. "ST.Strings-R" is
"JV Strings R"). On 502 factory tones the table agrees 478 times; the other 24 are tones Roland
deliberately re-voiced (stereo pianos, other strings) when making the XV presets.

Expansion boards (SR-JV80 series) are not part of the plug-in. ``EXPANSION_SUBSTITUTES`` gives,
per board, the closest internal XV wave for each of its waves (a judgement call by family: saw,
square, pulse, strings, choir...), used only when the user allows approximate conversions.
"""

INT_A_NAMES = (
    "Ac Piano1 A", "Ac Piano1 B", "Ac Piano1 C", "Ac Piano2 pA", "Ac Piano2 pB", "Ac Piano2 pC",
    "Ac Piano2 fA", "Ac Piano2 fB", "Ac Piano2 fC", "Piano Thump", "Piano Up TH", "MKS-20 P3 A",
    "MKS-20 P3 B", "MKS-20 P3 C", "SA Rhodes 1A", "SA Rhodes 1B", "SA Rhodes 1C", "SA Rhodes 2A",
    "SA Rhodes 2B", "SA Rhodes 2C", "E.Piano 1A", "E.Piano 1B", "E.Piano 1C", "E.Piano 2A",
    "E.Piano 2B", "E.Piano 2C", "E.Piano 3A", "E.Piano 3B", "E.Piano 3C", "MK-80 EP A", "MK-80 EP B",
    "MK-80 EP C", "D-50 EP A", "D-50 EP B", "D-50 EP C", "Celesta", "Music Box", "Clav 1A", "Clav 1B",
    "Clav 1C", "Organ 1", "Jazz Organ 1", "Jazz Organ 2", "Organ 2", "Organ 3", "Organ 4", "Rock Organ",
    "Dist. Organ", "Rot.Org Slw", "Rot.Org Fst", "Pipe Organ", "Nylon Gtr A", "Nylon Gtr B",
    "Nylon Gtr C", "6-Str Gtr A", "6-Str Gtr B", "6-Str Gtr C", "Gtr Harm A", "Gtr Harm B",
    "Gtr Harm C", "Comp Gtr A", "Comp Gtr B", "Comp Gtr C", "Comp Gtr A+", "Mute Gtr 1", "Mute Gtr 2A",
    "Mute Gtr 2B", "Mute Gtr 2C", "Pop Strat A", "Pop Strat B", "Pop Strat C", "Jazz Gtr A",
    "Jazz Gtr B", "Jazz Gtr C", "JC Strat A", "JC Strat B", "JC Strat C", "JC Strat A+", "JC Strat B+",
    "JC Strat C+", "Clean Gtr A", "Clean Gtr B", "Clean Gtr C", "Stratus A", "Stratus B", "Stratus C",
    "OD Gtr A", "OD Gtr B", "OD Gtr C", "OD Gtr A+", "Heavy Gtr A", "Heavy Gtr B", "Heavy Gtr C",
    "Heavy Gtr A+", "Heavy Gtr B+", "Heavy Gtr C+", "PowerChord A", "PowerChord B", "PowerChord C",
    "EG Harm", "Gt.FretNoise", "Syn Gtr A", "Syn Gtr B", "Syn Gtr C", "Harp 1A", "Harp 1B", "Harp 1C",
    "Banjo A", "Banjo B", "Banjo C", "Sitar A", "Sitar B", "Sitar C", "Dulcimer A", "Dulcimer B",
    "Dulcimer C", "Shamisen A", "Shamisen B", "Shamisen C", "Koto A", "Koto B", "Koto C", "Pick Bass A",
    "Pick Bass B", "Pick Bass C", "Fingerd Bs A", "Fingerd Bs B", "Fingerd Bs C", "E.Bass",
    "Fretless A", "Fretless B", "Fretless C", "UprightBs 1", "UprightBs 2A", "UprightBs 2B",
    "UprightBs 2C", "Slap Bass 1", "Slap & Pop", "Slap Bass 2", "Slap Bass 3", "Jz.Bs Thumb",
    "Jz.Bs Slap 1", "Jz.Bs Slap 2", "Jz.Bs Slap 3", "Jz.Bs Pop", "Syn Bass A", "Syn Bass C",
    "Mini Bs 1A", "Mini Bs 1B", "Mini Bs 1C", "Mini Bs 2", "Mini Bs 2+", "MC-202 Bs A", "MC-202 Bs B",
    "MC-202 Bs C", "Flute 1A", "Flute 1B", "Flute 1C", "Blow Pipe", "Bottle", "Shakuhachi",
    "Clarinet A", "Clarinet B", "Clarinet C", "Oboe mf A", "Oboe mf B", "Oboe mf C", "Sop.Sax mf A",
    "Sop.Sax mf B", "Sop.Sax mf C", "Alto Sax 1A", "Alto Sax 1B", "Alto Sax 1C", "Tenor Sax A",
    "Tenor Sax B", "Tenor Sax C", "Bari.Sax f A", "Bari.Sax f B", "Bari.Sax f C", "Harmonica A",
    "Harmonica B", "Harmonica C", "Chanter", "Tpt Sect. A", "Tpt Sect. B", "Tpt Sect. C", "Trumpet 1A",
    "Trumpet 1B", "Trumpet 1C", "Trumpet 2A", "Trumpet 2B", "Trumpet 2C", "HarmonMute1A",
    "HarmonMute1B", "HarmonMute1C", "Trombone 1", "French 1A", "French 1C", "F.Horns A", "F.Horns B",
    "F.Horns C", "Violin A", "Violin B", "Violin C", "Cello A", "Cello B", "Cello C", "ST.Strings-R",
    "ST.Strings-L", "MonoStringsA", "MonoStringsC", "Pizz", "JP Strings1A", "JP Strings1B",
    "JP Strings1C", "JP Strings2A", "JP Strings2B", "JP Strings2C", "Soft Pad A", "Soft Pad B",
    "Soft Pad C", "Fantasynth A", "Fantasynth B", "Fantasynth C", "D-50 HeavenA", "D-50 HeavenB",
    "D-50 HeavenC", "Fine Wine", "D-50 Brass A", "D-50 Brass B", "D-50 Brass C", "D-50 BrassA+",
    "DualSquare A", "DualSquare C", "DualSquareA+", "Pop Voice", "Syn Vox 1", "Syn Vox 2",
    "Voice Aahs A", "Voice Aahs B", "Voice Aahs C", "Voice Oohs1A", "Voice Oohs1B", "Voice Oohs1C",
    "Voice Oohs2A", "Voice Oohs2B", "Voice Oohs2C", "Voice Breath", "Male Ooh A", "Male Ooh B",
    "Male Ooh C", "Org Vox A", "Org Vox B", "Org Vox C", "Vox Noise",
)

INT_B_NAMES = (
    "Kalimba", "Marimba Wave", "Log Drum", "Vibes", "Bottle Hit", "Glockenspiel", "Tubular",
    "Steel Drums", "Fanta Bell A", "Fanta Bell B", "Fanta Bell C", "FantaBell A+", "Org Bell", "Agogo",
    "DIGI Bell 1", "DIGI Bell 1+", "DIGI Chime", "Wave Scan", "Wire String", "2.2 Bellwave",
    "2.2 Vibwave", "Spark VOX", "MMM VOX", "Lead Wave", "Synth Reed", "Synth Saw 1", "Synth Saw 2",
    "Syn Saw 2inv", "Synth Saw 3", "JP-8 Saw A", "JP-8 Saw B", "JP-8 Saw C", "P5 Saw A", "P5 Saw B",
    "P5 Saw C", "D-50 Saw A", "D-50 Saw B", "D-50 Saw C", "Synth Square", "JP-8 SquareA",
    "JP-8 SquareB", "JP-8 SquareC", "Synth Pulse1", "Synth Pulse2", "Triangle", "Sine", "Org Click",
    "White Noise", "Pink Noise", "Metal Wind", "Wind Agogo", "Feedbackwave", "Spectrum", "BreathNoise",
    "Rattles", "Ice Rain", "Tin Wave", "Anklungs", "Wind Chimes", "Orch. Hit", "Tekno Hit", "Back Hit",
    "Philly Hit", "Scratch 1", "Scratch 2", "Scratch 3", "Natural SN1", "Natural SN2", "Piccolo SN",
    "Ballad SN", "SN Roll", "808 SN", "Brush Slap", "Brush Swish", "Brush Roll", "Dry Stick",
    "Side Stick", "Lite Kick", "Hybrid Kick1", "Hybrid Kick2", "Old Kick", "Verb Kick", "Round Kick",
    "808 Kick", "Verb Tom Hi", "Verb Tom Lo", "Dry Tom Hi", "Dry Tom Lo", "Cl HiHat 1", "Cl HiHat 2",
    "Op HiHat", "Pedal HiHat", "606 HiHat Cl", "606 HiHat Op", "808 Claps", "Hand Claps",
    "Finger Snaps", "Ride 1", "Ride 2", "Ride Bell 1", "Crash 1", "China Cym", "Cowbell 1",
    "Wood Block", "Claves", "Bongo Hi", "Bongo Lo", "Cga Open Hi", "Cga Open Lo", "Cga Mute Hi",
    "Cga Mute Lo", "Cga Slap", "Timbale", "Cabasa Up", "Cabasa Down", "Cabasa Cut", "Maracas",
    "Long Guiro", "Tambourine", "Open Triangl", "Cuica", "Vibraslap", "Timpani", "Applause",
    "REV Orch.Hit", "REV TeknoHit", "REV Back Hit", "REV PhillHit", "REV Steel DR", "REV Tin Wave",
    "REV NatrlSN1", "REV NatrlSN2", "REV PiccloSN", "REV BalladSN", "REV Side Stk", "REV SN  Roll",
    "REV Brush 1", "REV Brush 2", "REV Brush 3", "REV LiteKick", "REV HybridK1", "REV HybridK2",
    "REV Old Kick", "REV Timpani", "REV VerbTomH", "REV VerbTomL", "REV DryTom H", "REV DryTom M",
    "REV ClHiHat1", "REV ClHiHat2", "REV Op HiHat", "REV Pedal HH", "REV 606HH Cl", "REV 606HH Op",
    "REV Ride", "REV Cup", "REV Crash 1", "REV China", "REV DrySick", "REV RealCLP", "REV FingSnap",
    "REV Cowbell", "REV WoodBlck", "REV Clve", "REV Conga", "REV Tamb", "REV Maracas", "REV Guiro",
    "REV Cuica", "REV Metro", "Loop 1", "Loop 2", "Loop 3", "Loop 4", "Loop 5", "Loop 6", "Loop 7",
    "R8 Click", "Metronome 1", "Metronome 2", "MC500 Beep 1", "MC500 Beep 2", "Low Saw", "Low Saw inv",
    "Low P5 Saw", "Low Pulse 1", "Low Pulse 2", "Low Square", "Low Sine", "Low Triangle",
    "Low White NZ", "Low Pink NZ", "DC",
)

# XV-5080 wave numbers (1-1083) for INT-A / INT-B waves 1-255 / 1-193 (index = JV wave - 1).
INT_A_XV = (
    19, 20, 21, 13, 14, 15, 16, 17, 18, 22, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 49, 50, 51, 52, 53,
    54, 55, 56, 57, 58, 59, 60, 64, 65, 66, 67, 68, 70, 71, 72, 89, 87, 88, 90, 91, 92, 99, 118, 119,
    120, 121, 125, 126, 127, 129, 130, 131, 147, 148, 149, 158, 159, 160, 161, 162, 163, 164, 165, 167,
    168, 169, 150, 151, 152, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 185, 186, 187,
    188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 208, 209,
    210, 211, 212, 213, 220, 221, 222, 223, 224, 225, 226, 227, 228, 232, 233, 234, 235, 236, 237, 238,
    242, 243, 244, 248, 249, 250, 251, 255, 256, 257, 258, 259, 260, 261, 262, 263, 266, 267, 272, 273,
    274, 275, 276, 277, 278, 279, 281, 282, 283, 291, 293, 295, 298, 299, 300, 301, 302, 303, 319, 320,
    321, 325, 326, 327, 334, 335, 336, 340, 341, 342, 348, 349, 350, 347, 363, 364, 365, 376, 377, 378,
    379, 380, 381, 382, 383, 384, 385, 392, 393, 394, 395, 396, 397, 398, 399, 403, 404, 405, 421, 420,
    422, 423, 410, 424, 425, 426, 427, 428, 429, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442,
    443, 444, 445, 551, 552, 553, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 575, 464,
    465, 466, 467, 468, 469, 573,
)

INT_B_XV = (
    473, 484, 481, 487, 488, 489, 490, 491, 493, 494, 495, 496, 497, 498, 500, 501, 509, 517, 518, 506,
    507, 522, 526, 527, 528, 529, 530, 531, 532, 535, 536, 537, 538, 539, 540, 544, 545, 546, 547, 548,
    549, 550, 558, 559, 562, 564, 602, 576, 577, 565, 566, 567, 568, 574, 578, 579, 580, 581, 582, 583,
    584, 585, 586, 587, 588, 589, 668, 669, 663, 670, 667, 708, 702, 703, 712, 713, 715, 732, 734, 735,
    733, 736, 737, 742, 771, 772, 773, 774, 787, 788, 797, 803, 809, 810, 813, 816, 817, 825, 826, 827,
    836, 838, 839, 840, 841, 842, 843, 844, 845, 846, 847, 848, 849, 850, 851, 852, 853, 854, 855, 857,
    858, 859, 860, 863, 888, 889, 890, 891, 892, 893, 908, 909, 903, 910, 954, 907, 942, 943, 944, 972,
    974, 975, 973, 1080, 1004, 1005, 1006, 1007, 1020, 1021, 1030, 1036, 1041, 1042, 1056, 1058, 1067,
    1069, 953, 1048, 1047, 1070, 1071, 1072, 1073, 1077, 1075, 1076, 1079, 1083, 865, 866, 867, 868,
    869, 870, 871, 872, 873, 874, 875, 876, 877, 878, 879, 880, 881, 882, 883, 884, 885, 886, 887,
)

EXPANSION_NAMES = {
    4: "SR-JV80-04 Vintage Synth",
}

EXPANSION_WAVE_NAMES = {
    4: (
        "JP-8 Saw A", "JP-8 Saw C", "Sys700 Saw", "JX-10 Saw", "D-50 Saw 1", "D-50 Saw 2", "SH-5 Saw",
        "SH-2 Saw", "SH-101 Saw", "SH-1000 Saw", "GR-300 Saw 1", "GR-300 Saw 2", "JU-2 Saw",
        "MG Saw 1A", "MG Saw 1C", "MG Saw 2", "OB Saw 1A", "OB Saw 1C", "OB Saw 2", "P5 Saw 1A",
        "P5 Saw 1C", "2600 Saw", "AP Saw", "OSC Saw", "OSC Reso Saw", "KG700 Saw", "KG800 Saw 1",
        "KG800 Saw 2", "KG MS Saw", "CS Saw 1A", "CS Saw 1", "CS Saw 2", "JP-8 SquareA", "JP-8 SquareC",
        "JX-10 Square", "SH-5 Square", "SH-2 Square", "MG Square A", "MG Square C", "OB Square A",
        "OB Square C", "P5 Square A", "P5 Square C", "2600 Square", "OSC Square", "KG800 Square",
        "KG MS Square", "CS Square", "JP-8 Pulse 1", "JP-8 Pulse 2", "JP-8 Pulse 3", "JP-8 Pulse 4",
        "JP-8 Pulse 5", "SH-1000 Puls", "MG Pulse 1A", "MG Pulse 1C", "MG Pulse 2A", "MG Pulse 2C",
        "OB Pulse 1", "OB Pulse 2", "OB Pulse 3", "2600 Pulse 1", "2600 Pulse 2", "EM Pulse",
        "CS Pulse 1", "CS Pulse 2", "JU-2 Sub OSC", "MG Ramp", "MG Triangle", "2600Triangle",
        "2600 Sine", "JP-8 PWM A", "JP-8 PWM B", "JP-8 PWM C", "MG Dt.Saw A", "MG Dt.Saw B",
        "MG Dt.Saw C", "P5 Dt.Saw A", "P5 Dt.Saw B", "P5 Dt.Saw C", "MG Dt.Squ A", "MG Dt.Squ B",
        "MG Dt.Squ C", "JP-8 Str A", "JP-8 Str B", "JP-8 Str C", "OB Str 1A", "OB Str 1B", "OB Str 1C",
        "OB Str 2A", "OB Str 2B", "OB Str 2C", "AP Str Ens A", "AP Str Ens B", "AP Str Ens C",
        "OBXP Str A", "OBXP Str B", "OBXP Str C", "OBXP Str Lp", "MG Oct A", "MG Oct B", "MG Oct C",
        "MG Dt.Oct A", "MG Dt.Oct B", "MG Dt.Oct C", "OBXP Brass A", "OBXP Brass B", "OBXP Brass C",
        "OBXP BrassLp", "FM Brass", "Waspy", "Waspy Lp", "OB Lead", "OB Lead Lp", "JP-6 SqLead",
        "JP-6 SqLd Lp", "Blown 1", "Blown 2", "PG Sweep 1A", "PG Sweep 1C", "PG Sweep 2A",
        "PG Sweep 2C", "D-50 HeavenA", "D-50 HeavenB", "D-50 HeavenC", "JX-8P Vox", "JX-8P Vox Lp",
        "VP-330ChoirA", "VP-330ChoirB", "VP-330ChoirC", "P5 Unisync", "P5 UnisyncLp", "P5 Dipthong",
        "P5 DipthngLp", "FM Lead", "KG800 Lead", "MG Lead", "MG Lead Lp", "JP-8 Lead", "Digiwave 1",
        "Digiwave 2", "Digiwave 3", "Frog wave", "SRG FM", "Shimmer wave", "VS Organ A", "VS Organ C",
        "Juno Organ", "Juno OrganLp", "FM Punch", "Mondigital", "MondigitalLp", "JP-8 Clavi A",
        "JP-8 Clavi C", "JP-8 ClaviLp", "Juno Clavi", "P5 X-mod", "Steam Drum", "Kalimba Atk",
        "Additive", "MG Blip", "MG Blip Lp", "MG Thump", "MG Thump Lp", "MG Attack", "MG Attack Lp",
        "VS Bell 1", "VS Bell 2", "JP-6 Bell", "MKS-80 Xmod1", "MKS-80 Xmod2", "MKS-80 Xmod3",
        "MKS-80 Xmod4", "MKS-80 Xmod5", "OB Bass", "OB Bass Lp A", "OB Bass Lp B", "OB Bass Lp C",
        "MG BsPedal", "MG BsPdl LpA", "MG BsPdl LpC", "MG Fat Bs", "MG Sharp Bs1", "MG Big Bs",
        "MG ClassicBs", "MG Sharp Bs2", "TB-303 Bass", "JP-4 Bass 1", "JP-4 Bass 2", "SH-101 Bs 1",
        "SH-101 Bs 2", "SH-101 Bs 3", "SH-101 Bs 4", "SH-101 Bs 5", "Sys700 Bs 1", "Sys700 Bs 2",
        "FM Super Bs", "KG Poly Bs", "KG Poly BsLp", "Power B slwA", "Power B slwB", "Power B slwC",
        "Power B fstA", "Power B fstB", "Power B fstC", "Tron Choir A", "Tron Choir B", "Tron Choir C",
        "Tron Flute A", "Tron Flute B", "Tron Flute C", "Tron Str A", "Tron Str B", "Tron Str C",
        "MG White Nz", "MG Pink Nz", "SH-5 Pink Nz", "JP-8 X-mod 1", "JP-8 X-mod 2", "P5 Noise 1",
        "P5 Noise 2", "ZZZ loop", "Atmosphere", "FX1A-L(RSS)", "FX1B-L(RSS)", "FX1C-L(RSS)",
        "FX1A-R(RSS)", "FX1B-R(RSS)", "FX1C-R(RSS)", "FX2A-L(RSS)", "FX2B-L(RSS)", "FX2C-L(RSS)",
        "FX2A-R(RSS)", "FX2B-R(RSS)", "FX2C-R(RSS)", "FX3A-L(RSS)", "FX3B-L(RSS)", "FX3C-L(RSS)",
        "FX3A-R(RSS)", "FX3B-R(RSS)", "FX3C-R(RSS)", "REV Waspy", "REV P5 X-mod", "REV SteamDrm",
        "REV Kalimba", "REV Additive", "REV Blip", "REV Thump", "REV Attack", "REV FX1L RSS",
        "REV FX1R RSS", "REV FX2L RSS", "REV FX2R RSS", "REV FX3L RSS", "REV FX3R RSS",
    ),
}

EXPANSION_SUBSTITUTES = {
    4: (
        535, 537, 529, 530, 544, 546, 529, 529, 529, 530, 532, 532, 535, 534, 534, 534, 541, 543, 541,
        538, 540, 529, 530, 529, 561, 529, 530, 530, 529, 533, 533, 533, 548, 550, 547, 547, 547, 551,
        552, 548, 550, 548, 550, 547, 547, 547, 547, 547, 554, 555, 556, 557, 560, 558, 558, 558, 559,
        559, 558, 559, 559, 558, 559, 558, 558, 559, 547, 534, 562, 562, 564, 430, 430, 430, 534, 534,
        534, 541, 542, 543, 551, 551, 552, 424, 425, 426, 427, 428, 429, 427, 428, 429, 422, 422, 423,
        424, 425, 426, 425, 534, 534, 534, 534, 534, 534, 442, 443, 444, 443, 445, 527, 527, 527, 527,
        548, 548, 528, 528, 561, 561, 561, 561, 438, 439, 440, 448, 448, 459, 460, 461, 561, 561, 449,
        449, 527, 527, 527, 527, 527, 508, 508, 511, 519, 512, 505, 89, 89, 90, 90, 524, 508, 508, 79,
        81, 82, 82, 561, 580, 475, 503, 602, 602, 604, 604, 601, 601, 503, 500, 506, 561, 561, 561, 561,
        561, 266, 266, 266, 267, 272, 272, 274, 275, 276, 275, 272, 276, 277, 268, 268, 277, 277, 278,
        278, 279, 269, 270, 280, 268, 268, 269, 270, 271, 269, 270, 271, 459, 460, 461, 281, 282, 283,
        420, 421, 423, 576, 577, 577, 561, 561, 576, 577, 471, 432, 432, 433, 434, 432, 433, 434, 438,
        439, 440, 438, 439, 440, 435, 436, 437, 435, 436, 437, 527, 561, 893, 475, 503, 602, 604, 601,
        432, 432, 438, 438, 435, 435,
    ),
}

# JV-1080 wave group parameter: 0 = internal (ID 1 = INT-A, 2 = INT-B), 1 = PCM card (SN-U110),
# 2 = expansion board (ID = SR-JV80 board number).
GROUP_INT, GROUP_PCM, GROUP_EXP = 0, 1, 2


class WaveResult(tuple):
    """(xv_wave or 0 when the tone must be silenced, approximate, warning text or "")."""

    __slots__ = ()

    def __new__(cls, xv: int, approximate: bool = False, warning: str = ""):
        return super().__new__(cls, (xv, approximate, warning))


def convert_wave(group: int, group_id: int, number: int, substitute: bool) -> WaveResult:
    """XV wave for a JV tone wave (``number`` is 0-based, as stored in the sysex data)."""
    if group == GROUP_INT and group_id in (1, 2):
        table = INT_A_XV if group_id == 1 else INT_B_XV
        if 0 <= number < len(table):
            return WaveResult(table[number])
        return WaveResult(0, False, f"unknown internal wave {number + 1}")
    if group == GROUP_EXP:
        board = EXPANSION_NAMES.get(group_id, f"SR-JV80-{group_id:02d}")
        subs = EXPANSION_SUBSTITUTES.get(group_id)
        if not substitute:
            return WaveResult(0, False, f"{board} wave muted")
        if subs is None or not 0 <= number < len(subs):
            return WaveResult(0, False, f"{board} wave muted (no substitute known)")
        return WaveResult(subs[number], True, f"{board} wave replaced")
    if group == GROUP_PCM:
        return WaveResult(0, False, "PCM card wave muted")
    return WaveResult(0, False, f"unknown wave group {group}")
