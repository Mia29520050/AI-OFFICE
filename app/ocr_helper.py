from __future__ import annotations

import atexit
import base64
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

_PS_WORKER_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($op, $type) {
    $m = $asTaskGeneric.MakeGenericMethod($type)
    $t = $m.Invoke($null, @($op))
    $t.Wait()
    return $t.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) {
    $en = [Windows.Globalization.Language]::new("en-US")
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($en)
}
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
while (($line = [Console]::In.ReadLine()) -ne $null) {
    $line = $line.Trim()
    if (-not $line) { continue }
    if ($line -eq '__EXIT__') { break }
    $t0 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    try {
        if (-not $engine) { throw "OCR engine unavailable" }
        $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($line)) ([Windows.Storage.StorageFile])
        $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocr = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
        $bw = [double]$bmp.PixelWidth; $bh = [double]$bmp.PixelHeight
        $angDeg = if ($null -ne $ocr.TextAngle) { [double]$ocr.TextAngle } else { 0.0 }
        $rad = $angDeg * [Math]::PI / 180.0
        $cosA = [Math]::Cos($rad); $sinA = [Math]::Sin($rad)
        $cx0 = $bw / 2.0; $cy0 = $bh / 2.0
        $items = @()
        foreach ($ol in $ocr.Lines) {
            $minX = 1e9; $minY = 1e9; $maxX = 0.0; $maxY = 0.0
            foreach ($wd in $ol.Words) {
                $r = $wd.BoundingRect
                if ($r.X -lt $minX) { $minX = $r.X }
                if ($r.Y -lt $minY) { $minY = $r.Y }
                if (($r.X + $r.Width) -gt $maxX) { $maxX = $r.X + $r.Width }
                if (($r.Y + $r.Height) -gt $maxY) { $maxY = $r.Y + $r.Height }
            }
            if ($maxX -gt $minX -and $bw -gt 0 -and $bh -gt 0) {
                $px = (($minX + $maxX) / 2.0) - $cx0
                $py = (($minY + $maxY) / 2.0) - $cy0
                $rx = ($px * $cosA - $py * $sinA) + $cx0
                $ry = ($px * $sinA + $py * $cosA) + $cy0
                $items += [PSCustomObject]@{
                    text = $ol.Text
                    x = [int][Math]::Round($rx * 1000.0 / $bw)
                    y = [int][Math]::Round($ry * 1000.0 / $bh)
                }
            }
        }
        $stream.Dispose(); $bmp.Dispose()
        $dt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - $t0
        Write-Output (@{ok=$true; ms=$dt; items=$items} | ConvertTo-Json -Compress)
    } catch {
        Write-Output (@{ok=$false; error=$_.Exception.Message; items=@()} | ConvertTo-Json -Compress)
    }
}
"""

_ENCODED_PS = base64.b64encode(_PS_WORKER_SCRIPT.encode("utf-16le")).decode("ascii")


class WindowsOcrWorker:
    """Persistent Windows.Media.Ocr worker returning normalized (0..1000) text boxes in ~30-60ms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None

    def _ensure_started(self) -> subprocess.Popen[str]:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-EncodedCommand", _ENCODED_PS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=flags,
        )
        return self._proc

    def close(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is not None and proc.poll() is None:
            try:
                if proc.stdin:
                    proc.stdin.write("__EXIT__\n")
                    proc.stdin.flush()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def recognize(self, image_path: str | Path, *, max_items: int = 28) -> dict[str, Any]:
        """Extract normalized (0..1000) text lines and centers from an image file."""
        resolved = Path(image_path).resolve()
        if not resolved.is_file():
            return {"ok": False, "ms": 0, "items": []}
        with self._lock:
            for attempt in range(2):
                try:
                    proc = self._ensure_started()
                    if not proc.stdin or not proc.stdout:
                        raise RuntimeError("OCR pipe unavailable")
                    proc.stdin.write(str(resolved) + "\n")
                    proc.stdin.flush()
                    raw = proc.stdout.readline().strip()
                    if not raw:
                        raise RuntimeError("Empty OCR output")
                    data = json.loads(raw)
                    items = [
                        {
                            "text": str(it.get("text", "")).strip()[:60],
                            "x": max(0, min(1000, int(it.get("x", 0)))),
                            "y": max(0, min(1000, int(it.get("y", 0)))),
                        }
                        for it in (data.get("items") or [])
                        if str(it.get("text", "")).strip()
                    ][:max_items]
                    return {"ok": bool(data.get("ok")), "ms": int(data.get("ms", 0)), "items": items}
                except Exception:
                    if self._proc is not None:
                        try:
                            self._proc.kill()
                        except Exception:
                            pass
                        self._proc = None
                    if attempt == 1:
                        return {"ok": False, "ms": 0, "items": []}
        return {"ok": False, "ms": 0, "items": []}


OCR_WORKER = WindowsOcrWorker()
atexit.register(OCR_WORKER.close)


def _classify_box_color(im: Any, x0_n: int, y0_n: int, x1_n: int, y1_n: int) -> str:
    """Classify a UI button region by hue/luminance: 'CAM', 'TÍM', 'ĐEN' (active dark), 'XÁM' (disabled gray), or ''."""
    w, h = im.size
    left = max(0, min(w - 1, int(w * x0_n / 1000)))
    top = max(0, min(h - 1, int(h * y0_n / 1000)))
    right = max(left + 1, min(w, int(w * x1_n / 1000)))
    bottom = max(top + 1, min(h, int(h * y1_n / 1000)))
    crop = im.crop((left, top, right, bottom)).convert("RGB")
    pixels = list(crop.get_flattened_data()) if hasattr(crop, "get_flattened_data") else list(crop.getdata())
    n = max(1, len(pixels))
    orange = sum(1 for r, g, b in pixels if r >= 170 and g >= 70 and b <= 115 and (r - b) >= 70)
    purple = sum(1 for r, g, b in pixels if b >= 120 and r >= 85 and ((r + b) / 2 - g) >= 28 and (b - r) >= -20)
    gray = sum(1 for r, g, b in pixels if (max(r, g, b) - min(r, g, b)) <= 26 and 85 <= (r + g + b) / 3 <= 220)
    dark = sum(1 for r, g, b in pixels if (max(r, g, b) - min(r, g, b)) <= 26 and (r + g + b) / 3 < 75)
    if orange * 100.0 / n >= 20.0:
        return "CAM"
    if purple * 100.0 / n >= 20.0:
        return "TÍM"
    if gray * 100.0 / n >= 45.0:
        return "XÁM"
    if dark * 100.0 / n >= 45.0:
        return "ĐEN"
    return ""


_ACTION_BUTTON_WORDS = (
    "confirm",
    "enter",
    "select",
    "assign",
    "extract",
    "details",
    "skip",
    "next",
    "continue",
    "end turn",
    "promotions",
    "delegate",
)


def annotate_button_colors(image_path: str | Path, ocr_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Attach CAM/TÍM (active) vs XÁM (disabled/unselected) state tags to detected buttons & bottom-right corner."""
    try:
        from PIL import Image
        im = Image.open(image_path)
    except Exception:
        return ocr_items, ""
    annotated: list[dict[str, Any]] = []
    for it in ocr_items:
        copy_it = dict(it)
        low = str(it.get("text", "")).lower()
        if any(tok in low for tok in _ACTION_BUTTON_WORDS):
            st = _classify_box_color(im, int(it["x"]) - 55, int(it["y"]) - 28, int(it["x"]) + 55, int(it["y"]) + 28)
            if st:
                copy_it["state"] = st
        annotated.append(copy_it)
    corner_state = _classify_box_color(im, 805, 885, 975, 960)
    return annotated, corner_state


def extract_ocr_labels(image_path: str | Path, *, max_items: int = 28) -> dict[str, Any]:
    return OCR_WORKER.recognize(image_path, max_items=max_items)
