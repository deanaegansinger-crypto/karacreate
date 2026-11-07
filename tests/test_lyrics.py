from karaoke_maker.cli import guess_title_artist
from karaoke_maker.lyrics import Word, draft_lines, normalise, time_lyrics


def words(*items):
    return [Word(t, s, e) for t, s, e in items]


def test_normalise_ignores_case_and_punctuation():
    assert normalise("Don't,") == normalise("dont")
    assert normalise("Café") == "cafe"


def test_matching_words_take_recognised_times():
    rec = words(("hello", 1.0, 1.4), ("world", 1.5, 2.0))
    [line] = time_lyrics(["Hello, world!"], rec)
    assert [(w.text, w.start, w.end) for w in line.words] == [("Hello,", 1.0, 1.4), ("world!", 1.5, 2.0)]


def test_misheard_word_gets_the_misheard_time():
    rec = words(("i", 1.0, 1.2), ("can't", 1.2, 1.5), ("bee", 1.5, 2.0), ("there", 2.0, 2.4))
    [line] = time_lyrics(["I can't be there"], rec)
    assert line.words[2].text == "be"
    assert (line.words[2].start, line.words[2].end) == (1.5, 2.0)


def test_missing_words_share_the_time_between_neighbours():
    rec = words(("one", 1.0, 1.5), ("four", 3.0, 3.5))
    [line] = time_lyrics(["one two three four"], rec)
    two, three = line.words[1], line.words[2]
    assert 1.5 <= two.start < two.end <= three.start < three.end <= 3.0


def test_lines_keep_their_breaks_and_times_never_go_backwards():
    rec = words(("a", 0.0, 0.5), ("b", 0.4, 0.6), ("c", 0.6, 0.7), ("d", 5.0, 6.0))
    lines = time_lyrics(["a b", "", "c d"], rec)
    assert [l.text for l in lines] == ["a b", "c d"]
    flat = [w for l in lines for w in l.words]
    for prev, cur in zip(flat, flat[1:]):
        assert cur.start >= prev.end
        assert cur.end > cur.start


def test_skipped_line_after_a_break_sits_before_the_next_singing():
    rec = words(("verse", 1.0, 2.0), ("chorus", 60.0, 61.0))
    lines = time_lyrics(["verse", "missing words here", "chorus"], rec)
    missing = lines[1]
    assert missing.start > 50  # not stretched across the instrumental


def test_draft_lines_split_on_pauses():
    rec = words(("a", 0, 0.5), ("b", 0.5, 1.0), ("c", 3.0, 3.5))
    assert draft_lines(rec) == ["a b", "c"]


def test_title_and_artist_from_youtube_names():
    assert guess_title_artist("Adele - Hello (Official Lyric Video)") == ("Hello", "Adele")
    assert guess_title_artist("Queen - Bohemian Rhapsody [Lyrics] [HD]") == ("Bohemian Rhapsody", "Queen")
    assert guess_title_artist("Some Song lyrics") == ("Some Song", "")


def test_finds_files_split_by_another_program(tmp_path):
    from karaoke_maker.cli import find_stems

    song = tmp_path / "Mustang Sally (Lyrics).mp4"
    for name in [song.name, "Mustang Sally (Lyrics)_no_vocals_split_by_lalalai.mp3",
                 "Mustang Sally (Lyrics)_vocals_split_by_lalalai.mp3", "Other Song_vocals.mp3", "notes.txt"]:
        (tmp_path / name).write_bytes(b"")
    backing, vocals = find_stems(song)
    assert backing.name == "Mustang Sally (Lyrics)_no_vocals_split_by_lalalai.mp3"
    assert vocals.name == "Mustang Sally (Lyrics)_vocals_split_by_lalalai.mp3"


def test_other_names_for_split_files(tmp_path):
    from karaoke_maker.cli import find_stems

    song = tmp_path / "Song.mp3"
    for name in ["Song.mp3", "Song - Instrumental.wav", "Song (Vocals).flac"]:
        (tmp_path / name).write_bytes(b"")
    backing, vocals = find_stems(song)
    assert (backing.name, vocals.name) == ("Song - Instrumental.wav", "Song (Vocals).flac")


def test_nothing_found_when_there_are_no_split_files(tmp_path):
    from karaoke_maker.cli import find_stems

    song = tmp_path / "Song.mp4"
    for name in ["Song.mp4", "Song.mp3", "Song Two_vocals.mp3"]:
        (tmp_path / name).write_bytes(b"")
    assert find_stems(song) == (None, None)


def test_split_files_know_which_song_they_belong_to(tmp_path):
    from karaoke_maker.cli import split_from

    names = ["Song.mp4", "Song_no_vocals_split_by_lalalai.mp3", "Song_vocals_split_by_lalalai.mp3"]
    for name in names:
        (tmp_path / name).write_bytes(b"")
    assert split_from(tmp_path / names[0]) is None
    assert split_from(tmp_path / names[1]).name == "Song.mp4"
    assert split_from(tmp_path / names[2]).name == "Song.mp4"


def test_own_karaoke_output_is_not_taken_for_a_split_file(tmp_path):
    from karaoke_maker.cli import find_stems

    for name in ["Song.mp3", "Song (Karaoke).mp3"]:
        (tmp_path / name).write_bytes(b"")
    assert find_stems(tmp_path / "Song.mp3") == (None, None)
