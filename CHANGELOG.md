# Changelog

## 0.2.0 (2026-10-13)

- Waves of all 19 SR-JV80 expansion boards are now replaced with the closest internal waves
  (option, on by default), not only SR-JV80-04. Phrase loops become the plug-in's internal drum
  loops, whatever their tempo; such patches stay marked approximate.

## 0.1.0 (2026-10-13)

First version.

- Converts JV-1080 patch dumps (`.syx`, `.mid`; JV-1080, JV-2080, JV-1010, XP series) into
  128-patch banks for the Roland Cloud JV-1080 plug-in (`.bin`, loaded with BANK > LOAD).
- Accepts files, folders and `.zip` / `.7z` archives (unpacked automatically); several at once.
- Scan first, then confirm: the list shows every patch with its bank, effect and conversion notes,
  and whether its bank is **New** or will **Replace** an existing one.
- Patch, tones, waves, controllers, chorus, reverb and the 40 EFX types are converted; factory
  patches converted from SysEx sound like the plug-in's own presets.
- SR-JV80-04 Vintage Synth waves are replaced with the closest internal waves (option), other
  expansion and PCM card waves are muted; every approximation is listed.
