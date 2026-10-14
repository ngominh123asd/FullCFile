from copy import deepcopy
import numpy as np

from app.services.ocr_structured_text import refine_addresses


class Reader:
    def __init__(self, value):
        self.value = value

    def predict(self, crop):
        return self.value


def line(text, confidence=35):
    return dict(text='Mail: '+text, bbox=[0,10,290,40], words=[
        dict(text='Mail:', confidence=97, bbox=[0,10,40,40]),
        dict(text=text, confidence=confidence, bbox=[50,10,290,40])])


def test_address_changes_need_visual_agreement_for_every_character():
    source = line('Ieam(dsample.org')
    original = deepcopy(source)
    image = np.full((70,320),255,np.uint8)
    ascii_read = lambda c: ('team@sample.org', .99)
    # The English reader disagrees on the first glyph; the second independent
    # reader confirms it. Neither syntax nor a known-domain list fills it in.
    english = lambda c: [dict(text='feam@sample.org',confidence=70)]
    refine_addresses([source],image,ascii_read,english,Reader('wrong address'),lambda:False)
    assert source == original
    refine_addresses([source],image,ascii_read,english,Reader('team(A sample.org'),lambda:False)
    assert source['text'] == 'Mail: team@sample.org'
    assert source['words'][0] == original['words'][0]
    assert source['words'][1]['bbox'] == original['words'][1]['bbox']


def test_valid_syntax_alone_cannot_repair_address_or_change_strong_reading():
    image = np.full((70,320),255,np.uint8)
    for text, confidence in [('user@sample.org',98),('bad(sample.org',30)]:
        source = line(text,confidence); original=deepcopy(source)
        refine_addresses([source],image,lambda c:('user@example.net',.99),
                         lambda c:[dict(text='user@example.net',confidence=40)],
                         Reader('user@example.net'),lambda:False)
        assert source == original


def test_numeric_values_and_cancellation_do_not_trigger_address_repair():
    image=np.full((70,320),255,np.uint8)
    def unexpected(crop):
        raise AssertionError('This region must not be read')
    for text,cancelled in [('123.456',False),('weak(example.org',True)]:
        source=line(text);original=deepcopy(source)
        refine_addresses([source],image,unexpected,unexpected,None,lambda:cancelled)
        assert source == original
