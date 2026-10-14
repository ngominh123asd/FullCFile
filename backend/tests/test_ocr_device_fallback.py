import pytest
from PIL import Image
from app.services import ocr_service


def test_cuda_runtime_failure_retries_same_image_on_cpu_and_reuses_fallback(monkeypatch):
    model = ocr_service.VietOcrOnnxPredictor.__new__(ocr_service.VietOcrOnnxPredictor)
    class Session:
        def get_providers(self):
            return ['CUDAExecutionProvider','CPUExecutionProvider']
    model.sess_enc = Session()
    calls=[]
    def fail(*args):
        calls.append('gpu')
        raise RuntimeError('device allocation failed')
    model._predict_impl = fail
    seen=[]
    class CPU:
        def predict(self, image, rapid_rec, max_steps, max_chunk_width):
            seen.append((image,max_steps,max_chunk_width))
            return '007 - Original'
    cpu = CPU()
    monkeypatch.setattr(ocr_service, '_get_vietocr_onnx_predictor', lambda use_gpu: None if use_gpu else cpu)
    image=Image.new('L',(80,30),255)
    assert model.predict(image,max_steps=100,max_chunk_width=320) == '007 - Original'
    assert model.predict(image,max_steps=100,max_chunk_width=320) == '007 - Original'
    assert calls == ['gpu']
    assert seen == [(image,100,320)]*2


def test_cpu_errors_are_not_hidden_by_recursive_fallback(monkeypatch):
    model = ocr_service.VietOcrOnnxPredictor.__new__(ocr_service.VietOcrOnnxPredictor)
    class Session:
        def get_providers(self):
            return ['CPUExecutionProvider']
    model.sess_enc = Session()
    def fail(*args):
        raise RuntimeError('invalid input')
    model._predict_impl = fail
    with pytest.raises(RuntimeError,match='invalid input'):
        model.predict(Image.new('L',(80,30),255))
