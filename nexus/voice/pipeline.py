"""语音管线——Whisper听+Piper说，纯本地"""
import os, logging
logger = logging.getLogger("nexus.voice")

class VoicePipeline:
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.join(os.path.dirname(__file__), "..", "..", "..", ".nexus", "models")
        self.whisper = None
        self.piper = None

    def load_whisper(self):
        import whisper
        model_path = os.path.join(self.models_dir, "whisper")
        if os.path.exists(os.path.join(model_path, "model.safetensors")):
            self.whisper = whisper.load_model("small", download_root=model_path)
        else:
            self.whisper = whisper.load_model("small")
        logger.info("Whisper small loaded")

    def load_piper(self):
        piper_path = os.path.join(self.models_dir, "speech", "zh_CN-huayan-medium.onnx")
        if os.path.exists(piper_path):
            self.piper = piper_path
            logger.info("Piper TTS (huayan) ready")

    def listen(self, audio_path: str) -> str:
        if not self.whisper: self.load_whisper()
        result = self.whisper.transcribe(audio_path, language="zh")
        return result["text"].strip()

    def status(self) -> dict:
        return {"whisper": self.whisper is not None, "piper": self.piper is not None}
