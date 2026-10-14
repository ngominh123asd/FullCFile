import numpy as np
import pytest

from app.services.ocr_text_refinement import crop_with_accents, refine_with_context, _agreed_edits


def line_for(text, confidence=98):
    words = [dict(text=token, confidence=confidence,
                  bbox=[10+i*80, 10, 75+i*80, 36])
             for i, token in enumerate(text.split())]
    return dict(text=text, words=words, confidence=confidence,
                word_confidences=[(w['text'], w['confidence']) for w in words])


class Predictor:
    def __init__(self, reading):
        self.reading = reading
        self.calls = []

    def predict(self, crop):
        self.calls.append(crop.size)
        return self.reading


def refine(line, full, local, cancelled=lambda:False):
    predictor = Predictor(local)
    refine_with_context(line, full, np.full((50,1000),255,np.uint8), predictor, cancelled)
    return predictor


def test_high_confidence_diacritic_error_requires_visual_agreement():
    line = line_for('Một bàn vẽ')
    refine(line, 'Một bản vẽ', 'Một bản vẽ')
    assert line['text'] == 'Một bản vẽ'
    assert line['ocr_corrections'][0]['before'] == 'bàn'
    assert line['words'][1]['bbox'] == [90,10,155,36]


def test_local_read_disagreement_preserves_source_accents():
    line = line_for('Mẫu bản vẽ')
    refine(line, 'Mẫu bàn vẽ', 'Mẫu bản vẽ')
    assert line['text'] == 'Mẫu bản vẽ'
    assert 'ocr_corrections' not in line


@pytest.mark.parametrize('text, reading', [
    ('Mã 0017-A', 'Mã 0018-A'),
    ('Số tiền 12,50', 'Số tiền 12,60'),
    ('Ngày 03/04/2028', 'Ngày 04/04/2028'),
])
def test_confident_identifiers_and_numbers_are_not_inferred(text, reading):
    line = line_for(text)
    predictor = refine(line, reading, reading)
    assert line['text'] == text
    assert not predictor.calls


@pytest.mark.parametrize('source, full, local, expected', [
    ('q8. Mục tiếp theo', '9. Mục tiếp theo', '9. Mục tiếp', '9. Mục tiếp theo'),
    ('Ghi chú #//);', 'Ghi chú a/b);', 'Ghi chú a/b);', 'Ghi chú a/b);'),
    ('Xem PHỤ LỤC ÏV', 'Xem PHỤ LỤC IV', 'PHỤ LỤC IV', 'Xem PHỤ LỤC IV'),
])
def test_weak_mixed_tokens_can_change_only_with_corroborating_pixels(source, full, local, expected):
    line = line_for(source, 25)
    refine(line, full, local)
    assert line['text'] == expected


def test_case_only_changes_do_not_rewrite_proper_names():
    line = line_for('Tại Nguyễn Trãi')
    predictor = refine(line, 'Tại nguyễn trãi', 'Tại nguyễn trãi')
    assert line['text'] == 'Tại Nguyễn Trãi'
    assert not predictor.calls


def test_cancellation_does_not_apply_partial_corrections():
    line = line_for('Một bàn vẽ')
    refine(line, 'Một bản vẽ', 'Một bản vẽ', cancelled=lambda:True)
    assert line['text'] == 'Một bàn vẽ'


def test_unaligned_tokens_cannot_be_assigned_to_another_word():
    line = line_for('Mã AB-CD và tên')
    refine(line, 'Mã A B C D và tên', 'Mã A B C D và tên')
    assert line['text'] == 'Mã AB-CD và tên'


def test_agreement_on_letters_is_independent_of_disagreement_on_trailing_punctuation():
    assert _agreed_edits('@|);', 'a/b);', 'a/b).') == 'a/b);'


def test_quoted_word_can_regain_an_accent_without_rewriting_quotes():
    line = line_for('Un “coté” différent', 92)
    refine(line, 'Un ?côté? différent', 'Un ?côté? différent')
    assert line['text'] == 'Un “côté” différent'


def test_accent_loss_on_confident_text_requires_an_isolated_word_read():
    line = line_for('Le café noir', 96)
    readings = iter(['Le cafe noir', 'café'])
    class Reader:
        def predict(self, crop):
            return next(readings)
    refine_with_context(line, 'Le cafe noir', np.full((50,1000),255,np.uint8), Reader(), lambda:False)
    assert line['text'] == 'Le café noir'


def test_crop_recovers_detached_accent_and_excludes_neighboring_line():
    image = np.full((100,150),255,np.uint8)
    image[40:61,40:80] = 0
    image[33:35,55:59] = 0
    image[22:28,40:80] = 0
    crop = crop_with_accents(image,(40,40,80,61),(30,85))
    assert np.count_nonzero(crop==0) == 21*40+2*4


def test_crop_keeps_existing_scale_if_detector_already_covers_all_ink():
    image = np.full((100,150),255,np.uint8)
    image[40:61,40:80] = 0
    crop = crop_with_accents(image,(40,40,80,61))
    assert np.array_equal(crop,image[36:66,36:85])


def test_word_crop_recovers_tone_above_false_gutter_without_neighbor_fragments():
    from app.services.ocr_text_refinement import word_crop
    image=np.full((100,150),255,np.uint8)
    image[40:61,40:80]=0
    image[33:35,55:59]=0  # Detached tone above the detector's body box.
    image[22:34,72:78]=0  # Descender from the preceding line, cut by search top.
    word=dict(text='cote',bbox=[40,40,80,61],recognition_limits=(37,85))
    crop=word_crop(image,word,{})
    assert np.count_nonzero(crop==0)==21*40+2*4
    assert word['local_ink_recovered']
    assert np.count_nonzero(image==0)==21*40+2*4+12*6


def test_word_crop_does_not_import_a_neighbor_letter_as_a_tone():
    from app.services.ocr_text_refinement import word_crop
    image=np.full((100,150),255,np.uint8)
    image[40:61,40:80]=0
    image[20:36,55:69]=0
    word=dict(text='cote',bbox=[40,40,80,61],recognition_limits=(37,85))
    crop=word_crop(image,word,{})
    assert np.count_nonzero(crop==0)==21*40
    assert not word.get('local_ink_recovered')


def test_third_visual_read_resolves_disagreement_without_fixed_word_replacements():
    line = line_for('Dòng Sao mới', 93)
    readings = iter(['Dòng Sáo mới', 'Sáo'])
    class Reader:
        def predict(self, crop):
            return next(readings)
    refine_with_context(line, 'Dòng Sào mới', np.full((50,1000),255,np.uint8), Reader(), lambda:False)
    assert line['text'] == 'Dòng Sáo mới'


@pytest.mark.parametrize('symbol,wrong', [('+','%'),('—','?'),('✓','v'),('%','+')])
def test_language_model_does_not_replace_standalone_symbols(symbol,wrong):
    line = line_for(symbol+' Read this',25)
    refine(line,wrong+' Read this',wrong+' Read this')
    assert line['text'] == symbol+' Read this'


def test_low_confidence_letters_can_change_without_losing_typographic_quotes():
    line = line_for('Un “cote” différent',30)
    refine(line,'Un ?côté? différent','Un ?côté? différent')
    assert line['text'] == 'Un “côté” différent'


def test_repeated_neural_accent_bias_needs_independent_confirmation():
    line = line_for('Một bản vẽ',89)
    refine_with_context(line,'Một bàn vẽ',np.full((50,1000),255,np.uint8),
                        Predictor('Một bàn vẽ'),lambda:False,
                        verify_word=lambda crop:dict(text='bản',confidence=92))
    assert line['text'] == 'Một bản vẽ'


def test_alternate_accent_evidence_requires_both_views_and_never_changes_numbers():
    from app.services.ocr_text_refinement import alternate_accent_support
    crop=np.tile(np.arange(256,dtype=np.uint8),(40,1))
    def agrees(view):return dict(text='bản',confidence=65)
    assert alternate_accent_support(crop,'bàn','bản',agrees)
    reads=iter([dict(text='bản',confidence=90),dict(text='bàn',confidence=95)])
    assert not alternate_accent_support(crop,'bàn','bản',lambda view:next(reads))
    assert not alternate_accent_support(crop,'A13','Á13',agrees)
    assert not alternate_accent_support(crop,'bàn','bán',agrees)
    assert not alternate_accent_support(crop,'cáp','cặp',agrees)


def test_spacing_pass_cannot_smuggle_in_different_accents():
    from app.services.ocr_native import _merge_visual_words
    assert _merge_visual_words(dict(text='le ca fé',confidence=60), 'le cafè',spacing_only=True) == 'le café'
    assert _merge_visual_words(dict(text='cafétoujours',confidence=60), 'cafè toujours',spacing_only=True) == 'café toujours'


def test_joined_word_uses_a_stronger_visual_read_and_updates_word_geometry():
    from app.services.ocr_text_refinement import refine_spacing
    line = line_for('Un ca fe',60)
    image = np.full((60,500),255,np.uint8)
    reading = lambda crop:[dict(text='café',confidence=94,bbox=[4,4,crop.shape[1]-4,crop.shape[0]-4])]
    refine_spacing(line,'Un cafe',image,reading,lambda:False)
    assert line['text'] == 'Un café'
    assert [w['text'] for w in line['words']] == ['Un','café']
    assert line['words'][1]['bbox'][0] == 90


def test_join_is_rejected_if_local_pixels_do_not_agree_on_letters():
    from app.services.ocr_text_refinement import refine_spacing
    line = line_for('Un ca fe',60)
    reading = lambda crop:[dict(text='cake',confidence=99,bbox=[0,0,40,20])]
    refine_spacing(line,'Un cafe',np.full((60,500),255,np.uint8),reading,lambda:False)
    assert line['text'] == 'Un ca fe'
