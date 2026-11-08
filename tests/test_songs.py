from karaoke_maker.songs import find_song, split_name


def make(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"")
    return [folder / n for n in names]


LALAL = ["Mustang Sally (Lyrics).mp4",
         "Mustang Sally (Lyrics)_no_vocals_split_by_lalalai.mp3",
         "Mustang Sally (Lyrics)_vocals_split_by_lalalai.mp3"]


def test_split_names():
    assert split_name("Song_no_vocals_split_by_lalalai").kind == "backing"
    assert split_name("Song_vocals_split_by_lalalai").kind == "vocals"
    assert split_name("Song_vocals_split_by_lalalai").by_lalal
    assert split_name("Song - Instrumental").base == "Song"
    assert split_name("Song (Vocals)").kind == "vocals"
    assert split_name("Song") is None
    assert split_name("Vocals") is None


def test_any_of_the_three_files_finds_the_same_song(tmp_path):
    song, backing, vocals = make(tmp_path, *LALAL)
    for dragged in (song, backing, vocals):
        s = find_song(dragged)
        assert (s.original, s.backing, s.vocals) == (song, backing, vocals)
        assert s.name == "Mustang Sally (Lyrics)"


def test_lalal_shortened_long_names(tmp_path):
    full = "Delilah – Tom Jones Dark Soul Blues Rock Cover by Bluesman Jack"
    song, backing, vocals = make(tmp_path, f"{full}.mp4",
                                 "Delilah – Tom Jones Dark Soul Blues Rock Cover by B._no_vocals_split_by_lalalai.mp3",
                                 "Delilah – Tom Jones Dark Soul Blues Rock Cover by B._vocals_split_by_lalalai.mp3")
    for dragged in (song, backing, vocals):
        s = find_song(dragged)
        assert (s.original, s.backing, s.vocals) == (song, backing, vocals)


def test_both_lalal_files_without_the_original(tmp_path):
    backing, vocals = make(tmp_path, LALAL[1], LALAL[2])
    s = find_song(backing)
    assert (s.original, s.backing, s.vocals) == (None, backing, vocals)
    assert s.name == "Mustang Sally (Lyrics)"
    assert s.work == tmp_path / "Mustang Sally (Lyrics) (karaoke work)"


def test_other_names_for_split_files(tmp_path):
    song, backing, vocals = make(tmp_path, "Song.mp3", "Song - Instrumental.wav", "Song (Vocals).flac")
    s = find_song(song)
    assert (s.backing, s.vocals) == (backing, vocals)


def test_different_songs_dont_mix(tmp_path):
    song, *_ = make(tmp_path, "Song.mp4", "Song Two_vocals.mp3", "Song2_no_vocals.mp3")
    s = find_song(song)
    assert (s.backing, s.vocals) == (None, None)


def test_a_title_ending_in_vocals_is_still_a_song(tmp_path):
    [song] = make(tmp_path, "The Backing Vocals.mp3")
    s = find_song(song)
    assert (s.original, s.backing, s.vocals) == (song, None, None)


def test_finished_karaoke_tracks_are_left_alone(tmp_path):
    song, backing, vocals, mp3, _ = make(tmp_path, *LALAL, "Mustang Sally.mp3", "Mustang Sally.cdg")
    assert find_song(mp3) is None
    assert find_song(song).backing == backing
