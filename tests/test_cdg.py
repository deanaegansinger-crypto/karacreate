import numpy as np

from karaoke_maker.cdg import HEIGHT, PACKET_SIZE, WIDTH, CdgDecoder, CdgWriter, load_palette


def test_palette_round_trips():
    colors = [(0, 0, 0), (255, 255, 255), (51, 153, 255), (255, 204, 0)]
    dec = CdgDecoder(b"".join(load_palette(colors)))
    dec.seek(1)
    assert dec.palette[:4] == colors


def test_writer_draws_what_it_is_asked_to_at_the_right_time():
    w = CdgWriter(palette=[(0, 0, 0), (255, 255, 255), (0, 0, 255)])
    pic = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    pic[30:40, 50:90] = 1
    pic[100:110, 7:11] = 2
    w.show(1.0, pic)
    data = w.finish(3.0)
    assert len(data) == 900 * PACKET_SIZE

    dec = CdgDecoder(data)
    dec.seek(0.99)
    assert not dec.pixels.any()
    dec.seek(1.2)
    assert np.array_equal(dec.pixels, pic)


def test_writer_only_sends_changed_tiles():
    w = CdgWriter(palette=[(0, 0, 0), (255, 255, 255)])
    pic = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    pic[12:24, 6:12] = 1  # exactly one tile
    assert w.show(0.5, pic) == 1
    assert w.show(0.6, pic) == 0
