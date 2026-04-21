"""
Workers para operações pesadas sem bloquear a UI.
"""
import sys
import json
import os
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config import (
    WHISPER_LANGUAGE, GROQ_API_KEY, GROQ_WHISPER_MODEL,
    TRANSCRIPTIONS_DIR, WHISPER_PROMPT,
)
from core.transcriber import TranscriptionSegment, Transcriber
from core.meeting_controller import MeetingController

_PYTHON          = str(Path(sys.executable).parent / "python.exe")
_TRANSCRIBE_GROQ = str(Path(__file__).parent.parent / "core" / "transcribe_groq.py")


class TxtProcessingWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, controller: MeetingController):
        super().__init__()
        self._controller = controller

    def run(self):
        try:
            self.progress.emit("Gerando resumo...", 20)
            self._controller.summarize_current()
            self.progress.emit("Exportando documento...", 80)
            path = self._controller.export_current()
            self.progress.emit("Documento salvo!", 100)
            self.finished.emit(str(path))
        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")


class ProcessingWorker(QThread):
    progress = pyqtSignal(str, int)   # (mensagem, percentual 0-100)
    finished = pyqtSignal(str)        # caminho do .md gerado
    error = pyqtSignal(str)

    def __init__(self, controller: MeetingController):
        super().__init__()
        self._controller = controller

    def run(self):
        try:
            meeting = self._controller.current_meeting()
            if not meeting or not meeting.audio_path:
                self.error.emit("Nenhum áudio disponível para transcrever.")
                return

            # ----------------------------------------------------------
            # 1. Transcrição via Groq API (subprocesso)
            # ----------------------------------------------------------
            self.progress.emit("Transcrevendo áudio...", 10)

            audio_path = str(meeting.audio_path)
            clean_env = os.environ.copy()
            clean_env["PYTHONPATH"] = ""
            clean_env["PYTHONIOENCODING"] = "utf-8"
            clean_env["PYTHONUTF8"] = "1"

            cmd = [_PYTHON, _TRANSCRIBE_GROQ, audio_path,
                   GROQ_WHISPER_MODEL, WHISPER_LANGUAGE, GROQ_API_KEY, WHISPER_PROMPT]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=clean_env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            stderr_lines = []

            def _read_stderr():
                for raw_line in proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    stderr_lines.append(line)
                    if line.startswith("PROGRESS:"):
                        try:
                            pct = int(line.split(":")[1])
                            scaled = 10 + int(pct * 0.5)
                            self.progress.emit(f"Transcrevendo... {pct}%", scaled)
                        except ValueError:
                            pass

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            stdout_bytes = proc.stdout.read()
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr_thread.join()
            proc.wait()

            if proc.returncode != 0:
                err_detail = "\n".join(stderr_lines[-5:])
                self.error.emit(f"Falha na transcrição (código {proc.returncode}):\n{err_detail}")
                return

            # ----------------------------------------------------------
            # 2. Parseia resultado JSON
            # ----------------------------------------------------------
            try:
                raw_segments = json.loads(stdout)
            except json.JSONDecodeError:
                self.error.emit(f"Resultado inválido do transcritor:\n{stdout[:300]}")
                return

            if isinstance(raw_segments, dict) and "error" in raw_segments:
                self.error.emit(raw_segments["error"])
                return

            segments = [
                TranscriptionSegment(
                    start=s["start"],
                    end=s["end"],
                    text=s["text"],
                )
                for s in raw_segments
            ]

            # ----------------------------------------------------------
            # 3. Salva transcrição no meeting atual via controller
            # ----------------------------------------------------------
            transcriber = Transcriber()
            transcript_text = transcriber.segments_to_text(segments)

            meeting.transcript_text = transcript_text
            meeting.whisper_model = GROQ_WHISPER_MODEL

            from core.meeting_controller import _safe_name
            safe = _safe_name(meeting.title)
            date_str = meeting.started_at.strftime("%Y-%m-%d_%H-%M")
            txt_path = TRANSCRIPTIONS_DIR / f"{date_str}_{safe}.txt"
            txt_path.write_text(transcript_text, encoding="utf-8")
            meeting.transcript_path = txt_path
            meeting.status = "summarizing"

            self.progress.emit(f"Transcrição concluída ({len(segments)} segmentos). Gerando resumo...", 65)

            # ----------------------------------------------------------
            # 4. Sumarização via Claude
            # ----------------------------------------------------------
            self._controller.summarize_current()
            self.progress.emit("Resumo gerado. Exportando documento...", 90)

            # ----------------------------------------------------------
            # 5. Exportação
            # ----------------------------------------------------------
            path = self._controller.export_current()
            self.progress.emit("Documento salvo!", 100)
            self.finished.emit(str(path))

        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")
