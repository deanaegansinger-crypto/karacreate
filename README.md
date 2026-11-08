# Karaoke Maker

Turns a song with vocals (such as a lyric video you've saved as MP4 or MP3)
into an **MP3+CDG karaoke track** that any karaoke player can play:

- the **MP3** is the song with the vocals taken out
- the **CDG** is the lyric screen: big lyrics on black, each word changing
  colour as it's sung

For private use with songs you own or have permission to use.

## How it works

1. **The split files.** You split the song with lalal.ai into a no-vocals
   track (the karaoke audio) and a vocals track (see below). If they're
   missing, [Demucs](https://github.com/facebookresearch/demucs) splits the
   song instead, which is slower.
2. **Finding the words.** [WhisperX](https://github.com/m-bain/whisperX)
   listens to the vocals on their own and writes down each word and when
   it's sung.
3. **Checking the lyrics.** Speech recognition mishears some sung words, so
   the words open in Notepad as `lyrics.txt`, one line per screen line.
   Correct them against the video and save. Words you fix or add get their
   timing from the words around them.
4. **Making the files.** The MP3 and CDG are saved next to your song as
   `Artist - Title.mp3` and `Artist - Title.cdg`.

## Setting up (once)

1. You need **Python 3.13**. Newer versions (3.14, 3.15) are missing parts
   the AI tools need. If you don't have 3.13, `Install.bat` offers to
   install it for you. It sits alongside any other Python, so there's no need
   to remove a newer one.
2. If you downloaded a zip, extract it first: right-click it, choose
   **Extract All...**, and pick a folder to keep it in. Running it from inside
   the zip doesn't work, because Windows deletes that copy afterwards.
3. Double-click **`Install.bat`** in the extracted folder. It downloads the AI tools
   and the word-recognition models (about 5 GB in all). If you have an
   NVIDIA graphics card it installs the faster graphics-card version.

## Where the songs come from

Karaoke Maker works on files you already have. It doesn't download anything.
Save songs with your downloader as usual, for example RealTimes in
RealPlayer, as MP4 or MP3. Split them with lalal.ai into the same folder,
then drag the song onto `Make Karaoke.bat`. Either
format works, so there's no need to convert MP4s first.

## Splitting songs with lalal.ai

Split each song with lalal.ai first. Karaoke Maker uses those files and
skips its own vocal removal, which is faster and uses less memory:

- the **no vocals** file becomes the karaoke MP3. An MP3 is used exactly as
  it is, with no re-encoding.
- the **vocals** file is what the word timings come from. Clean vocals give
  the best timing.

Put lalal.ai's files in the same folder as the song (the version with the
singing), keeping the names lalal.ai gives them, for example:

```
Mustang Sally.mp4                              <- drag this one
Mustang Sally_no_vocals_split_by_lalalai.mp3
Mustang Sally_vocals_split_by_lalalai.mp3
```

They're found by name: the song's name followed by "no vocals" /
"instrumental", or "vocals". If you only have the no-vocals file, Karaoke
Maker still removes the vocals itself to time the lyrics. Dragging all
three files onto `Make Karaoke.bat` is fine: the split files are spotted
and skipped.

Split the same file you drag in, or one exactly the same length. If the
lalal.ai file was trimmed at the start, the lyrics will be out of time,
and Karaoke Maker warns you if the lengths differ.

If you add lalal.ai files after already making a song with Karaoke Maker's
own vocal removal, just drag the song on again: it picks up the new files.

## Making a karaoke track

1. Drag one or more songs (MP4 or MP3) onto **`Make Karaoke.bat`**.
2. Wait while it finds the words. With lalal.ai files, a 4-minute song takes
   roughly 3-8 minutes on a laptop without a graphics card. Without them,
   Karaoke Maker removes the vocals too, which adds another 3-6 minutes.
   With an NVIDIA graphics card it takes about a minute. Close other
   programs first if your PC has 8 GB of memory: it needs about 3-4 GB.
3. Notepad opens with the lyrics. Fix any wrong words and check the
   title and artist at the top. Then save and close Notepad.
4. The MP3 and CDG appear next to the song, named `Artist - Title`. If
   that's already your song's own name, `(Karaoke)` is added so it's never
   overwritten. If you need to fix the lyrics
   again, edit `lyrics.txt` in the song's `(karaoke work)` folder and drag
   the song onto `Make Karaoke.bat` again. The slow steps are skipped the
   second time.

Tips for `lyrics.txt`:

- Each line is a line on the karaoke screen. Long lines wrap onto two.
- Blank lines and lines starting with `#` are ignored.
- Paste in the full correct lyrics if the recognised ones are poor. The
  timing still comes from the singing.

## From the command line

Run these from this folder (`.venv\Scripts\python` on Windows):

```
python -m karaoke_maker prepare "Song.mp4"          # steps 1-2, writes lyrics.txt
python -m karaoke_maker build "Song (karaoke work)"   # step 4
python -m karaoke_maker make "Song.mp4" --lyrics lyrics.txt   # all in one go
python -m karaoke_maker preview "Artist - Title.cdg" --at 42  # picture of the screen
```

Useful options:

| Option | What it does |
|---|---|
| `--backing FILE` / `--vocals FILE` | use split files with any names (see lalal.ai above) |
| `--text-size small/large/huge` | 8, 5 or 4 lines on screen (default large) |
| `--sung-color "#ffcc00"` | the colour words turn when sung (default blue) |
| `--unsung-color "#ffffff"` | the colour of words still to sing (default white) |
| `--no-title-screen` | skip the title and artist at the start |
| `--lrc` | also save an `.lrc` timed-lyrics file |
| `--whisper-model large-v3` | slightly better word recognition: slower, needs 16 GB of memory without a graphics card |
| `--whisper-model small` | fastest, least accurate word recognition |
| `--demucs-model htdemucs_ft` | cleaner vocal removal, 4x slower |
| `--language en` | skip language detection |

## What to expect

- Vocal removal is very good but not perfect. You may hear faint traces of
  backing vocals or reverb, especially from compressed YouTube audio.
- Long instrumental breaks clear the screen. The next lines come back 5
  seconds before the singing starts again.

## Tests

The tests cover the lyric timing, the CDG writer and the lyric screen. They
need no AI models:

```
pip install -r requirements-dev.txt
python -m pytest
```
