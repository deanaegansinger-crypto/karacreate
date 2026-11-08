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

## Installing with the setup program (easiest)

Download **KaraokeMaker-Setup.exe** from this repository's
[Releases page](../../releases/latest) and run it. Nothing else is needed, so
it's also the file to share with friends, for example by Dropbox or
WhatsApp. **KaraokeMaker-Setup.zip** is the same file zipped, for apps that
won't send an .exe.

- **No administrator needed.** It installs for the person running it, and
  puts Karaoke Maker in the Start menu and on the desktop.
- **Python 3.13 comes with it**, for PCs that don't have it.
- **Then it downloads the AI tools and models**: about 5 GB, which takes
  15-30 minutes. A black window shows the progress: leave it open until it
  says "All set". You need about 8 GB of free disk space.
- **"Windows protected your PC"** shows because the setup program isn't
  signed: click **More info**, then **Run anyway**.
- **If the download fails** (say the internet drops), run **Repair Karaoke
  Maker** from the Start menu.

A new setup program is built automatically each time the code on `main`
changes. Running a newer one over an installed Karaoke Maker updates it,
and only downloads what's new.

## Setting up from the files (the other way)

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
then drag them into Karaoke Maker. Either format works, so there's no need
to convert MP4s first.

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
Mustang Sally.mp4
Mustang Sally_no_vocals_split_by_lalalai.mp3
Mustang Sally_vocals_split_by_lalalai.mp3
```

Then drag any of them into Karaoke Maker, or all three: each song is
only done once. Files are matched by name. lalal.ai shortens long names
("...Cover by B._vocals_split_by_lalalai.mp3"), which is fine.

- **Both lalal.ai files are enough on their own.** The original song is
  then only used to check that the lengths match.
- With only the no-vocals file, the original song must be there too.
  Karaoke Maker removes the vocals from it itself to time the lyrics.

Split the same song file you have in the folder, or one exactly the same length. If the
lalal.ai file was trimmed at the start, the lyrics will be out of time,
and Karaoke Maker warns you if the lengths differ.

If you add lalal.ai files after already making a song with Karaoke Maker's
own vocal removal, just add the song again: it picks up the new files.

## Making a karaoke track

1. Open **Karaoke Maker** from your desktop. `Install.bat` puts the shortcut
   there; if it's missing, double-click `Create Desktop Shortcut.bat`.
2. Drag songs into the window: the song, its lalal.ai files, or all of
   them, for as many songs as you like. Or use **Add from Downloads...**,
   which opens your Downloads folder, or **Add songs...**, which opens
   wherever you last picked songs from.
3. Press **Start**. With lalal.ai files, a 4-minute song takes roughly 3-8
   minutes on a laptop without a graphics card. Without them, Karaoke Maker
   removes the vocals too, which adds another 3-6 minutes. Messages show in
   the box at the bottom.
4. When a song's lyrics are ready, a window opens to check them:
   - check the **Title** and **Artist**: the files are named after them
   - fix any wrong words (**Play the song** opens it in your player)
   - press **Make karaoke files**. **Later** keeps your changes for another
     time: double-click the song to come back to it.
5. When the song says **Done**, **Open folder** shows the files. They're
   saved next to the song unless you pick a folder under **Save files to**:
   **Choose...** an existing folder, **New folder...** to make one (inside
   the current save folder), or **Next to songs** to go back. The choice is
   remembered. The files are:
   - `Artist - Title.mp3` and `Artist - Title.cdg`: the karaoke track for
     EZtiger or any karaoke player. The CDG is the lyric screen; on its own,
     Windows can't play it.
   - `Artist - Title.mp4`: the same as a video, which plays anywhere. Untick
     **Also make an MP4 video** if you don't need it.

If the name is already your song's own name, `(Karaoke)` is added so it's
never overwritten. To fix the lyrics later, add the song again,
double-click it and press **Make karaoke files**: the slow steps aren't
repeated.

`Make Karaoke.bat` still works too. Drag files onto it and the lyrics open in
Notepad instead. The MP3, CDG and MP4 are made after you save and close
Notepad.

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
python -m karaoke_maker.gui                                    # the window
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
| `--no-mp4` | skip the MP4 video |
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
