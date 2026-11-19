from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from pathlib import Path
from typing import Any

import win32con
import win32gui
import win32process
from mss import mss
from PIL import Image, ImageDraw, ImageFont
from pywinauto import Desktop

ROOT = Path(__file__).resolve().parents[1]
SCREEN_DIR = ROOT / "data" / "screenshots"
SCREEN_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT = SCREEN_DIR / "latest.jpg"


def ensure_dpi_aware() -> None:
    """Keep Win32 window rects, mss captures and SendInput coordinates in physical pixels."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


ensure_dpi_aware()

# Win32 SendInput structures (64-bit safe)
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

ALLOWED_KEYS: dict[str, int] = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "tab": 0x09,
    "end": 0x23,
    "backspace": 0x08,
    "left": 0x25,
    "arrowleft": 0x25,
    "up": 0x26,
    "arrowup": 0x26,
    "right": 0x27,
    "arrowright": 0x27,
    "down": 0x28,
    "arrowdown": 0x28,
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): ord(str(d)) for d in range(10)},
    **{f"f{n}": 0x70 + n - 1 for n in range(1, 11)},
}
EXTENDED_VKS = {0x23, 0x25, 0x26, 0x27, 0x28}


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wt.DWORD),
        ("union", _INPUT_UNION),
    ]


def _send_inputs(items: list[_INPUT]) -> None:
    if not items:
        return
    arr = (_INPUT * len(items))(*items)
    sent = ctypes.windll.user32.SendInput(len(items), arr, ctypes.sizeof(_INPUT))
    if sent != len(items):
        raise OSError(f"SendInput only delivered {sent}/{len(items)} events.")


def _to_abs_coords(x: int, y: int) -> tuple[int, int]:
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    vw = max(1, user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
    vh = max(1, user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
    nx = int(max(0, min(65535, round(((x - vx) * 65535) / max(1, vw - 1)))))
    ny = int(max(0, min(65535, round(((y - vy) * 65535) / max(1, vh - 1)))))
    return nx, ny


def _mouse_event(flags: int, x: int | None = None, y: int | None = None, data: int = 0) -> _INPUT:
    dx, dy = (0, 0) if x is None or y is None else _to_abs_coords(x, y)
    return _INPUT(
        type=INPUT_MOUSE,
        union=_INPUT_UNION(
            mi=_MOUSEINPUT(dx=dx, dy=dy, mouseData=wt.DWORD(data & 0xFFFFFFFF), dwFlags=flags, time=0, dwExtraInfo=0)
        ),
    )


def _desktop() -> Desktop:
    return Desktop(backend="uia", allow_magic_lookup=False)


def _rect(control: Any) -> dict[str, int] | None:
    try:
        r = control.rectangle()
        return {"left": int(r.left), "top": int(r.top), "right": int(r.right), "bottom": int(r.bottom)}
    except Exception:
        return None


def _win32_rect(handle: int) -> dict[str, int]:
    hwnd = int(handle)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if not win32gui.IsIconic(hwnd):
        try:
            rc = wt.RECT()
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                wt.HWND(hwnd), 9, ctypes.byref(rc), ctypes.sizeof(rc)
            )
            if hr == 0 and rc.right > rc.left and rc.bottom > rc.top:
                left, top, right, bottom = rc.left, rc.top, rc.right, rc.bottom
        except Exception:
            pass
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": max(0, int(right - left)),
        "height": max(0, int(bottom - top)),
    }


def _process_name(pid: int) -> str:
    try:
        import win32api

        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        try:
            exe = win32process.GetModuleFileNameEx(hproc, 0)
            return Path(exe).name
        finally:
            win32api.CloseHandle(hproc)
    except Exception:
        return ""


def is_f12_pressed() -> bool:
    """Return True if global F12 emergency stop key is currently pressed."""
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x7B) & 0x8000)
    except Exception:
        return False


def window_info(handle: int) -> dict[str, Any]:
    """Return live Win32 metadata for a specific window handle."""
    hwnd = int(handle)
    if not win32gui.IsWindow(hwnd):
        return {"found": False, "handle": hwnd}
    try:
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        rect = _win32_rect(hwnd)
        return {
            "found": True,
            "handle": hwnd,
            "title": title[:240],
            "process_id": int(pid),
            "process_name": _process_name(int(pid)),
            "class_name": (win32gui.GetClassName(hwnd) or "")[:120],
            "visible": bool(win32gui.IsWindowVisible(hwnd)),
            "minimized": bool(win32gui.IsIconic(hwnd)),
            "rect": rect,
        }
    except Exception as exc:
        return {"found": False, "handle": hwnd, "error": str(exc)[:300]}


def _is_process_elevated_blocked(pid: int) -> bool:
    """Return True when target process runs at higher integrity or blocks token/input access."""
    try:
        import win32api
        import win32security

        try:
            self_elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            self_elevated = False

        try:
            hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        except Exception:
            return True
        try:
            try:
                htok = win32security.OpenProcessToken(hproc, win32con.TOKEN_QUERY)
            except Exception:
                return True
            try:
                elev = win32security.GetTokenInformation(htok, win32security.TokenElevation)
                if bool(elev) and not self_elevated:
                    return True
            except Exception:
                pass
            finally:
                win32api.CloseHandle(htok)
            return False
        finally:
            win32api.CloseHandle(hproc)
    except Exception:
        return False


def focus_window(handle: int) -> dict[str, Any]:
    """Restore if minimized and bring target window to foreground safely."""
    hwnd = int(handle)
    info = window_info(hwnd)
    if not info.get("found") or not info.get("visible"):
        raise ValueError("Cửa sổ mục tiêu không còn tồn tại hoặc không hiển thị.")
    if info.get("minimized"):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.15)
    if ctypes.windll.user32.GetForegroundWindow() == hwnd:
        return window_info(hwnd)

    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass

    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass

    if ctypes.windll.user32.GetForegroundWindow() != hwnd:
        fg = ctypes.windll.user32.GetForegroundWindow()
        cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(fg, None) if fg else 0
        target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
        attached_fg = False
        attached_tg = False
        try:
            if fg_tid and fg_tid != cur_tid:
                attached_fg = bool(ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, True))
            if target_tid and target_tid not in (cur_tid, fg_tid):
                attached_tg = bool(ctypes.windll.user32.AttachThreadInput(cur_tid, target_tid, True))
            try:
                win32gui.BringWindowToTop(hwnd)
            except Exception:
                pass
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        finally:
            if attached_tg:
                ctypes.windll.user32.AttachThreadInput(cur_tid, target_tid, False)
            if attached_fg:
                ctypes.windll.user32.AttachThreadInput(cur_tid, fg_tid, False)

    if ctypes.windll.user32.GetForegroundWindow() != hwnd:
        try:
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass

    time.sleep(0.14)
    if ctypes.windll.user32.GetForegroundWindow() != hwnd:
        pid = int(info.get("process_id", 0) or 0)
        if pid and _is_process_elevated_blocked(pid):
            raise PermissionError(
                "Game đang chạy ở quyền Administrator (hoặc được bảo vệ UIPI), Windows chặn AI Office thao tác. Hãy chạy game ở quyền thường hoặc tự click vào game."
            )
        raise PermissionError("Không thể chuyển focus tới cửa sổ game; hãy click vào cửa sổ game rồi thử lại.")
    return window_info(hwnd)


_SHELL_WINDOW_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
_SHELL_WINDOW_TITLES = {"Program Manager", "Windows Input Experience", "Microsoft Text Input Application"}


def _is_window_cloaked(hwnd: int) -> bool:
    """Return True if Windows DWM cloaks the window (hidden virtual desktop / suspended UWP)."""
    try:
        cloaked = ctypes.c_int(0)
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wt.HWND(int(hwnd)), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return hr == 0 and bool(cloaked.value)
    except Exception:
        return False


def list_windows() -> list[dict[str, Any]]:
    """List visible, non-cloaked top-level user windows with handles, PIDs, titles and bounds."""
    result: list[dict[str, Any]] = []

    def enum_cb(hwnd: int, _: Any) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd) or _is_window_cloaked(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title or title in _SHELL_WINDOW_TITLES:
                return True
            class_name = (win32gui.GetClassName(hwnd) or "")[:120]
            if class_name in _SHELL_WINDOW_CLASSES:
                return True
            rect = _win32_rect(hwnd)
            if rect["width"] < 80 or rect["height"] < 60:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            result.append({
                "title": title[:240],
                "process_id": int(pid),
                "process_name": _process_name(int(pid)),
                "handle": int(hwnd),
                "rect": rect,
                "class_name": class_name,
                "minimized": bool(win32gui.IsIconic(hwnd)),
                "elevated": bool(_is_process_elevated_blocked(int(pid))),
            })
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        for win in _desktop().windows(visible_only=True):
            try:
                title = (win.window_text() or "").strip()
                if not title or title in _SHELL_WINDOW_TITLES:
                    continue
                pid = int(win.process_id())
                result.append({
                    "title": title[:240],
                    "process_id": pid,
                    "handle": int(win.handle),
                    "rect": _rect(win),
                    "class_name": win.class_name()[:120],
                    "minimized": False,
                    "elevated": bool(_is_process_elevated_blocked(pid)),
                })
            except Exception:
                continue
    return result[:80]


def active_window() -> dict[str, Any]:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return {"found": False}
    info = window_info(int(hwnd))
    if not info.get("found"):
        return {"found": False}
    return info


def inspect_active(max_items: int = 100, window_handle: int | None = None) -> dict[str, Any]:
    info = window_info(window_handle) if window_handle is not None else active_window()
    if not info.get("found"):
        return {"window": info, "controls": []}
    win = _desktop().window(handle=info["handle"])
    controls = []
    try:
        descendants = win.descendants()
    except Exception:
        descendants = []
    for item in descendants[:max_items]:
        try:
            element = item.element_info
            controls.append({
                "name": (element.name or "")[:160],
                "control_type": (element.control_type or "")[:60],
                "automation_id": (element.automation_id or "")[:120],
                "enabled": bool(item.is_enabled()),
                "visible": bool(item.is_visible()),
                "rect": _rect(item),
            })
        except Exception:
            continue
    return {"window": info, "controls": controls, "count": len(controls)}


def _add_grid_overlay(image: Image.Image) -> Image.Image:
    """Draw a high-contrast 0..1000 coordinate grid along all 4 edges with subtle crosshairs."""
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    w, h = annotated.size
    font_size = max(10, min(13, round(w / 72)))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    pill_h = font_size + 3
    for step in range(100, 1000, 100):
        px = round(w * step / 1000)
        py = round(h * step / 1000)
        draw.line([(px, 0), (px, h)], fill=(0, 225, 255), width=1)
        draw.line([(0, py), (w, py)], fill=(0, 225, 255), width=1)
        label = str(step)
        for yy in (1, max(1, h - pill_h - 1)):
            x0 = max(2, min(w - 30, px - 14))
            draw.rectangle([x0, yy, x0 + 28, yy + pill_h], fill=(10, 14, 24))
            draw.text((x0 + 2, yy + 1), label, fill=(255, 235, 80), font=font)
        for xx in (3, max(3, w - 36)):
            y0 = max(2, min(h - pill_h - 2, py - pill_h // 2))
            draw.rectangle([xx, y0, xx + 32, y0 + pill_h], fill=(10, 14, 24))
            draw.text((xx + 3, y0 + 1), label, fill=(255, 235, 80), font=font)
    for gx in (200, 400, 500, 600, 800):
        cx = round(w * gx / 1000)
        for gy in (200, 400, 500, 600, 800):
            cy = round(h * gy / 1000)
            draw.line([(cx - 6, cy), (cx + 6, cy)], fill=(255, 215, 70), width=2)
            draw.line([(cx, cy - 6), (cx, cy + 6)], fill=(255, 215, 70), width=2)
    return annotated


def capture_screen(max_width: int = 1280, quality: int = 68) -> dict[str, Any]:
    with mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
    original = image.size
    if image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    image.save(SCREENSHOT, "JPEG", quality=quality, optimize=True)
    return {
        "path": str(SCREENSHOT),
        "width": image.width,
        "height": image.height,
        "original_width": original[0],
        "original_height": original[1],
        "bytes": SCREENSHOT.stat().st_size,
        "captured_at": time.time(),
    }


def capture_window(
    handle: int | None = None,
    *,
    max_width: int = 1024,
    quality: int = 72,
    draw_grid: bool = False,
    filename: str = "window.jpg",
) -> dict[str, Any]:
    """Capture a cropped screenshot of the given window handle (or primary monitor if None)."""
    if handle is None:
        return capture_screen(max_width=max_width, quality=quality)
    info = window_info(handle)
    if not info.get("found") or not info.get("visible") or info.get("minimized"):
        raise ValueError("Cửa sổ mục tiêu không hiển thị để chụp.")
    rect = info["rect"]
    if rect["width"] < 20 or rect["height"] < 20:
        raise ValueError("Kích thước cửa sổ mục tiêu quá nhỏ.")
    with mss() as sct:
        virt = sct.monitors[0]
        left = max(int(virt["left"]), int(rect["left"]))
        top = max(int(virt["top"]), int(rect["top"]))
        right = min(int(virt["left"]) + int(virt["width"]), int(rect["right"]))
        bottom = min(int(virt["top"]) + int(virt["height"]), int(rect["bottom"]))
        width = max(1, right - left)
        height = max(1, bottom - top)
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
        image = Image.frombytes("RGB", shot.size, shot.rgb)
    original = image.size
    clean_img = image
    if clean_img.width > 1440:
        clean_h = max(1, round(clean_img.height * 1440 / clean_img.width))
        clean_img = clean_img.resize((1440, clean_h), Image.Resampling.LANCZOS)
    clean_path = SCREEN_DIR / filename
    clean_img.save(clean_path, "JPEG", quality=max(quality, 82), optimize=True)
    ai_img = clean_img
    if ai_img.width > max_width:
        scaled_h = max(1, round(ai_img.height * max_width / ai_img.width))
        ai_img = ai_img.resize((max_width, scaled_h), Image.Resampling.LANCZOS)
    ai_path = clean_path
    if draw_grid:
        ai_path = SCREEN_DIR / ("grid_" + filename)
        _add_grid_overlay(ai_img).save(ai_path, "JPEG", quality=quality, optimize=True)
    return {
        "path": str(clean_path),
        "ai_path": str(ai_path),
        "width": ai_img.width,
        "height": ai_img.height,
        "original_width": original[0],
        "original_height": original[1],
        "rect": {"left": left, "top": top, "right": right, "bottom": bottom, "width": width, "height": height},
        "bytes": clean_path.stat().st_size,
        "captured_at": time.time(),
    }


def _active_control(name: str, control_type: str, automation_id: str = "", window_handle: int | None = None):
    if window_handle is None:
        info = active_window()
        if not info.get("found"):
            raise ValueError("Không tìm thấy cửa sổ đang hoạt động.")
        window_handle = int(info["handle"])
    win = _desktop().window(handle=int(window_handle))
    if not win.exists(timeout=0.5) or not win.is_visible():
        raise ValueError("Cửa sổ mục tiêu không còn tồn tại hoặc không hiển thị.")
    matches = []
    for item in win.descendants():
        try:
            el = item.element_info
            if (el.name or "") == name and (el.control_type or "") == control_type:
                if not automation_id or (el.automation_id or "") == automation_id:
                    matches.append(item)
        except Exception:
            continue
    if len(matches) != 1:
        raise ValueError(f"Cần khớp đúng 1 control; tìm thấy {len(matches)}.")
    return matches[0]


def perform_action(
    action: str,
    *,
    confirm: bool,
    name: str = "",
    control_type: str = "",
    automation_id: str = "",
    text: str = "",
    direction: str = "down",
    amount: int = 3,
    window_handle: int | None = None,
) -> dict[str, Any]:
    if confirm is not True:
        raise PermissionError("Thao tác yêu cầu confirm=true từ người dùng.")
    if action == "click":
        if not name or not control_type:
            raise ValueError("Click cần name và control_type lấy từ cây UIA.")
        target = _active_control(name, control_type, automation_id, window_handle)
        if not target.is_visible() or not target.is_enabled():
            raise ValueError("Control không hiển thị hoặc đang bị vô hiệu hóa.")
        target.set_focus()
        target.click_input()
        return {"ok": True, "action": "click", "target": name, "control_type": control_type}
    if action == "type":
        if not name or control_type not in {"Edit", "ComboBox"}:
            raise ValueError("Nhập liệu chỉ được phép vào Edit/ComboBox được chỉ định rõ.")
        if len(text) > 500:
            raise ValueError("Văn bản vượt quá 500 ký tự.")
        target = _active_control(name, control_type, automation_id, window_handle)
        if not target.is_visible() or not target.is_enabled():
            raise ValueError("Ô nhập không hiển thị hoặc đang bị vô hiệu hóa.")
        target.set_focus()
        target.set_edit_text(text)
        return {"ok": True, "action": "type", "target": name, "characters": len(text)}
    if action == "scroll":
        if direction not in {"up", "down"}:
            raise ValueError("direction chỉ nhận up hoặc down.")
        if amount < 1 or amount > 8:
            raise ValueError("amount phải từ 1 đến 8.")
        if window_handle is None:
            info = active_window()
            if not info.get("found"):
                raise ValueError("Không tìm thấy cửa sổ đang hoạt động.")
            window_handle = int(info["handle"])
        win = _desktop().window(handle=int(window_handle))
        if not win.exists(timeout=0.5) or not win.is_visible():
            raise ValueError("Cửa sổ mục tiêu không còn tồn tại hoặc không hiển thị.")
        win.set_focus()
        win.wheel_mouse_input(wheel_dist=(amount if direction == "up" else -amount))
        return {"ok": True, "action": "scroll", "direction": direction, "amount": amount}
    raise ValueError("Action không được hỗ trợ. Chỉ có click/type/scroll.")


def _map_norm_to_window(rect: dict[str, int], x_norm: int, y_norm: int) -> tuple[int, int]:
    """Map 0..1000 normalized coordinates strictly inside target window bounds."""
    margin_x = min(6, max(1, rect["width"] // 40))
    margin_y = min(6, max(1, rect["height"] // 40))
    nx = max(0, min(1000, int(x_norm)))
    ny = max(0, min(1000, int(y_norm)))
    px = rect["left"] + round(rect["width"] * nx / 1000)
    py = rect["top"] + round(rect["height"] * ny / 1000)
    px = max(rect["left"] + margin_x, min(rect["right"] - margin_x, px))
    py = max(rect["top"] + margin_y, min(rect["bottom"] - margin_y, py))
    return px, py


def _press_vk(vk: int, duration_ms: int = 75) -> None:
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    base_flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0)
    _send_inputs([_INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(wVk=0, wScan=scan, dwFlags=base_flags, time=0, dwExtraInfo=0)))])
    time.sleep(max(0.03, min(duration_ms / 1000.0, 0.5)))
    _send_inputs([_INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(wVk=0, wScan=scan, dwFlags=base_flags | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))])


def perform_scoped_input(
    handle: int,
    action: str,
    *,
    expected_pid: int,
    x: int = 500,
    y: int = 500,
    x2: int = 500,
    y2: int = 500,
    key: str = "",
    duration_ms: int = 80,
    direction: str = "down",
    amount: int = 3,
    text: str = "",
) -> dict[str, Any]:
    """Execute one mouse/key input strictly clamped inside the locked target window."""
    info = window_info(handle)
    if not info.get("found") or not info.get("visible") or info.get("minimized"):
        raise ValueError("Cửa sổ game không còn tồn tại hoặc đang bị thu nhỏ.")
    if int(info["process_id"]) != int(expected_pid):
        raise ValueError("PID cửa sổ mục tiêu đã thay đổi.")
    rect = info["rect"]
    if rect["width"] < 40 or rect["height"] < 40:
        raise ValueError("Kích thước cửa sổ mục tiêu không hợp lệ.")

    focus_window(handle)
    fg = active_window()
    if not fg.get("found") or int(fg.get("handle", -1)) != int(handle):
        raise PermissionError("Không thể focus đúng cửa sổ game mục tiêu.")
    if _is_process_elevated_blocked(expected_pid):
        raise PermissionError(
            "Cửa sổ game đang chạy quyền Administrator hoặc có lớp bảo vệ chặn quyền tiến trình (UIPI). AI Office không thể gửi chuột/phím thật vào cửa sổ này."
        )

    if action == "wait":
        time.sleep(max(0.1, min(duration_ms / 1000.0, 1.5)))
        return {"ok": True, "action": "wait"}

    if action in {"click_xy", "double_click_xy", "right_click_xy"}:
        px, py = _map_norm_to_window(rect, x, y)
        try:
            ctypes.windll.user32.SetCursorPos(px, py)
        except Exception:
            pass
        _send_inputs([_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE, px, py)])
        time.sleep(0.045)
        try:
            cur_x, cur_y = win32gui.GetCursorPos()
            if abs(cur_x - px) > 16 or abs(cur_y - py) > 16:
                raise PermissionError(f"Con trỏ chuột không di chuyển tới ({px},{py}) (thực tế tại {cur_x},{cur_y}); cửa sổ game có thể đang chặn chuột.")
        except PermissionError:
            raise
        except Exception:
            pass
        down_flag = MOUSEEVENTF_RIGHTDOWN if action == "right_click_xy" else MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP if action == "right_click_xy" else MOUSEEVENTF_LEFTUP
        clicks = 2 if action == "double_click_xy" else 1
        for i in range(clicks):
            _send_inputs([_mouse_event(down_flag)])
            time.sleep(0.055)
            _send_inputs([_mouse_event(up_flag)])
            if i + 1 < clicks:
                time.sleep(0.06)
        return {"ok": True, "action": action, "x": x, "y": y, "screen_x": px, "screen_y": py}

    if action == "drag_xy":
        sx, sy = _map_norm_to_window(rect, x, y)
        ex, ey = _map_norm_to_window(rect, x2, y2)
        try:
            ctypes.windll.user32.SetCursorPos(sx, sy)
        except Exception:
            pass
        _send_inputs([_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE, sx, sy)])
        time.sleep(0.04)
        try:
            cur_x, cur_y = win32gui.GetCursorPos()
            if abs(cur_x - sx) > 16 or abs(cur_y - sy) > 16:
                raise PermissionError(f"Con trỏ chuột không di chuyển tới điểm bắt đầu ({sx},{sy}); cửa sổ game có thể đang chặn chuột.")
        except PermissionError:
            raise
        except Exception:
            pass
        _send_inputs([_mouse_event(MOUSEEVENTF_LEFTDOWN)])
        time.sleep(0.035)
        steps = 8
        for step in range(1, steps + 1):
            mx = round(sx + (ex - sx) * step / steps)
            my = round(sy + (ey - sy) * step / steps)
            try:
                ctypes.windll.user32.SetCursorPos(mx, my)
            except Exception:
                pass
            _send_inputs([_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE, mx, my)])
            time.sleep(0.015)
        _send_inputs([_mouse_event(MOUSEEVENTF_LEFTUP)])
        return {"ok": True, "action": "drag_xy", "x": x, "y": y, "x2": x2, "y2": y2}

    if action == "key_press":
        clean_key = key.strip().lower()
        vk = ALLOWED_KEYS.get(clean_key)
        if vk is None:
            raise ValueError(f"Phím không được hỗ trợ hoặc không an toàn: {key!r}")
        _press_vk(vk, duration_ms=duration_ms)
        return {"ok": True, "action": "key_press", "key": clean_key, "duration_ms": duration_ms}

    if action == "scroll":
        if direction not in {"up", "down"}:
            raise ValueError("direction chỉ nhận up hoặc down.")
        amt = max(1, min(int(amount), 8))
        px, py = _map_norm_to_window(rect, x, y)
        _send_inputs([_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE, px, py)])
        time.sleep(0.03)
        delta = 120 * amt if direction == "up" else -120 * amt
        _send_inputs([_mouse_event(MOUSEEVENTF_WHEEL, data=delta)])
        return {"ok": True, "action": "scroll", "direction": direction, "amount": amt, "x": x, "y": y}

    if action == "type_text":
        if not text or len(text) > 120:
            raise ValueError("Văn bản nhập phải từ 1 đến 120 ký tự.")
        events: list[_INPUT] = []
        for ch in text:
            code = ord(ch)
            events.append(_INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))))
            events.append(_INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))))
        _send_inputs(events)
        return {"ok": True, "action": "type_text", "characters": len(text)}

    raise ValueError(f"Action không hỗ trợ: {action}")
