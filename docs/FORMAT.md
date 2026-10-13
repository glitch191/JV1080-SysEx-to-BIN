# JV-1080 plug-in bank format (.bin) and the JV-1080 SysEx conversion

What this tool relies on, measured on the Roland Cloud JV-1080 plug-in (version 1.13). The code is
the reference: `jv1080_sysex_to_bin/patch.py` (record), `effects.py` (effects), `waves.py`
(waveforms), `sysex.py` (input).

## Sources

- Plug-in factory banks `PR-A.bin` ... `PR-E.bin` (640 records).
- Factory patches as JV SysEx: the Preset D bank (`2080_PTC.MID`, 126 of 128 patches named as in
  `PR-D.bin`) and about 35 more from various dumps, matched by name: 161 factory patches in both
  formats. Conversions below were fitted on them; values that do not fit are presets Roland
  re-voiced by hand (other octave, other wave, other effect level...).
- JV-1080 owner's manual (waveform list p. 122-123, EFX parameters p. 114-121, MIDI implementation
  p. 132-155) and XV-5080 owner's manual (parameter address map, wave list).
- The plug-in's own manual: MFX type list and parameters.

## File

```
"KoaBankFile00003" "PG-JV1080"      25 bytes
128 records of 23,255 bytes         patch or rhythm set
```

The plug-in only loads complete banks (2,976,665 bytes).

## Record (patch)

| Offset | Content |
|---|---|
| 0x0000 | Name, 12 ASCII characters. The rest of the header is constant. |
| 0x0054 | Patch Common, XV-5080 layout 00-4E, plus one zero byte |
| 0x00A4 | MFX: type, 16 header bytes (dry, chorus, reverb sends, output, 4 x control source + sens, 4 control assigns), 32 parameters |
| 0x0135 | Chorus: type, level, output assign, output select, 20 parameters |
| 0x0189 | Reverb: type, level, output assign, 20 parameters |
| 0x01DC | TMT: structures and boosters, velocity control, 4 x (switch, key range, key fades, velocity range, velocity fades) |
| 0x0205 | Tone 1, XV-5080 layout 00-88 then 17 constant bytes; tones 2-4 every 0x9A |
| 0x046D | Rhythm set data; "------------" in a patch, kept from the template |
| 0x48C3 | Per-type effect memory (below) |

Parameters stored as 4 nibbles hold the value + 32768 (`08 00 00 00` = 0).

### Per-type effect memory

From 0x48C3: for each of the 78 MFX types, a 4-byte header then that type's parameters (the
sizes are in `effects.MFX_SIZES`). Only the active type's header is set: it holds the control
assigns. The plug-in plays the parameters stored here for the active type, so a conversion writes
them both here and in the SysEx-style area at 0x00B5. The chorus and reverb have the same kind of
memory: chorus type 1 at 22,979 (9 parameters), reverb type 1 at 23,099 (4 parameters).

The other types keep whatever the template record holds, as factory patches do.

## Conversion

### Waves

The plug-in uses the XV-5080 wave list (1,083 waves). JV-1080 waves INT-A 1-255 and INT-B 1-193
are matched by name (21 renamed ones by the factory patches). Expansion-board waves have no
equivalent; `waves.EXPANSION_SUBSTITUTES` picks, for each wave of the 19 SR-JV80 boards, the closest
internal wave by family (phrase loops become the internal Loop 1-7, whatever their tempo).

### Value rules (JV -> XV)

- Centred values: coarse tune +16, fine tune +14, pitch envelope depth +52, LFO / controller
  depths +1, TVF depth +1, curves +1.
- Keyfollow and bias tables: 64 + percentage / 10 (pitch / cutoff keyfollow -100..+200 %, the
  others -100..+100 %).
- Velocity sensitivity: 64 + (value - 50) x 0.64 up to +100 %, then a steeper measured curve.
- Time velocity sensitivity: 64 + percentage x 63 / 100.
- LFO waveform order differs (`patch.LFO_WAVES`); LFO and tone delay synchronised to the clock
  become note values (`patch._SYNC_NOTES`).
- Output: a tone sent to the JV's EFX goes to the MFX with its chorus and reverb sends; a tone sent
  to MIX goes to output A with the "non MFX" sends. The unused pair is set to 127.
- Controllers: the JV has 3 controllers x 4 destinations per tone; the XV has 4 matrix controls
  (source + 4 destinations) shared by the tones, with per-tone switches. Entries are allocated
  tone by tone in order (switched-off tones included); an equal entry is shared, a mirrored one
  is shared with the REVERSE switch unless the tone already uses it; a full control gets a twin;
  entries beyond 4 controls are dropped. Controller 1 is CC01; controllers 2 and 3 follow the
  patch control sources, system controllers 1 and 2 becoming aftertouch and CC02.

### Effects

Chorus and reverb copy the JV parameters (chorus rate converted to 0.05 Hz steps). The 40 JV EFX
types map onto the plug-in's 78 MFX types (`effects.EFX`); rates become 0.05 Hz steps
(`rate_hz20`), delay times milliseconds (`delay_ms`, `tap_time`), each as a triplet (Hz/ms or
note, value, note). The JV's parallel CHORUS/DELAY, FLANGER/DELAY and CHORUS/FLANGER become the
serial types.
