"""Custom exceptions for the pipeline."""


class AutoworkerError(Exception):
    """Base exception."""


class InputError(AutoworkerError):
    """Invalid input (URL, parameters)."""


class TranscriptError(AutoworkerError):
    """Failed to extract transcript."""


class LLMError(AutoworkerError):
    """LLM API call failed."""


class TTSError(AutoworkerError):
    """TTS generation failed."""


class VideoAssemblyError(AutoworkerError):
    """Video assembly/encoding failed."""


class StageError(AutoworkerError):
    """A pipeline stage failed."""

    def __init__(self, stage_name: str, message: str):
        self.stage_name = stage_name
        super().__init__(f"[{stage_name}] {message}")
