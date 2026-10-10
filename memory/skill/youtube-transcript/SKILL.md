# YouTube transcript

Turns a YouTube link into a clean transcript, so the ingest operation has
something verbatim to file.

## When it applies

An ingest URL that is a YouTube link means: get the transcript with this skill
FIRST, then run the normal INGEST OPERATION on it. Nothing else about the
ingest changes — the transcript IS the verbatim source, so it lands in `raw/`,
and the research page with its provenance block and concepts lands in
`research/`, like every other ingest.

## Commands

```bash
# 1. transcript only, printed to stdout (the normal case)
youtube-transcript.sh "https://youtu.be/VIDEOID"

# 2. write it straight into the inbox as a raw candidate
youtube-transcript.sh "https://youtu.be/VIDEOID" --slug 2026-10-08-talk-title > ~/wiki/raw/2026-10-08-talk-title.md
```

## Traps this skill handles

- **yt-dlp needs a JavaScript runtime.** Without one it silently fetches nothing
  for many videos. The script checks for `node` and points yt-dlp at it.
- **Auto-captions repeat themselves** in overlapping fragments. The script
  de-duplicates and reflows them so the text reads as prose: no timestamps, no
  repeated lines.
- **No captions at all.** The script says so and exits non-zero. The agent must
  NEVER summarise a video it could not read.
- Official captions are preferred; auto-generated ones are the fallback, and the
  header records which one you got.

## The header it writes

```
# <video title>
Source: <url> · By: <channel or unknown> · Published: <date or unknown>
Read: YYYY-MM-DD · Type: video
Third-party material. These are the author's claims, not our facts.
```

That is the research tier's provenance block, so the page can be filed without
retyping it.
