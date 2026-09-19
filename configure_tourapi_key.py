"""API 키를 마스킹 입력 창 또는 실제 터미널에서 로컬 파일로 저장한다."""
import argparse
import getpass
import os
from pathlib import Path
import sys
import tempfile
import warnings


TARGET = Path(__file__).resolve().parent / ".secrets" / "tourapi.key"
PET_TARGET = TARGET.with_name("pet_tourapi.key")


def save_key(value, target=TARGET, replace=False):
    key = value.strip()
    if not key or any(char.isspace() for char in key):
        raise ValueError("키는 공백 없이 한 줄로 입력하세요. 저장하지 않았습니다.")
    target.parent.mkdir(exist_ok=True)
    # A cleared file (including a BOM or whitespace) is ready for new input.
    if not replace:
        if target.exists():
            with target.open("r+", encoding="utf-8-sig") as handle:
                if handle.read().strip():
                    raise FileExistsError("기존 키가 있습니다. 입력 창에서 새 키를 저장하세요.")
                handle.seek(0)
                handle.write(key + "\n")
                handle.truncate()
        else:
            with target.open("x", encoding="utf-8") as handle:
                handle.write(key + "\n")
        return
    # Finish writing before replacing the old file, so write errors keep it intact.
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".tourapi-", delete=False) as handle:
            staged = Path(handle.name)
            handle.write(key + "\n")
        os.replace(staged, target)
    finally:
        if staged is not None and staged.exists():
            staged.unlink()


def run_gui(target=TARGET):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    location = f".secrets/{target.name}"
    root.title("반려동물 TourAPI 인증키 입력" if target == PET_TARGET else "TourAPI 인증키 입력")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=24)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text="복사한 인증키를 붙여넣으세요", font=("맑은 고딕", 14, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
    ttk.Label(frame, text="입력은 ●로 표시되고, 아래에 글자 수가 나옵니다.\n"
              "붙여넣기 버튼이나 Ctrl+V는 이전 입력 전체를 교체합니다.").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
    value = tk.StringVar(root)
    status = tk.StringVar(root, "입력 대기 · 0자")
    entry = ttk.Entry(frame, textvariable=value, show="●", width=58, font=("맑은 고딕", 11))
    entry.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ttk.Label(frame, textvariable=status, wraplength=500).grid(
        row=3, column=0, columnspan=3, sticky="w", pady=(0, 16))

    def changed(*_):
        count = len(value.get().strip())
        status.set(f"입력됨 · {count}자 · 아래 저장 버튼을 누르세요." if count else "입력 대기 · 0자")
        save_button.configure(state="normal" if count else "disabled")

    def paste(event=None):
        try:
            copied = root.clipboard_get()
        except tk.TclError:
            status.set("클립보드에 텍스트가 없습니다. 인증키를 복사한 뒤 다시 누르세요.")
        else:
            value.set(copied.strip())
            entry.icursor(tk.END)
            entry.focus_set()
        return "break"

    def save():
        try:
            save_key(value.get(), target=target, replace=True)
        except ValueError as error:
            status.set(str(error))
        except OSError:
            status.set("파일을 저장하지 못했습니다. 파일 사용 여부와 폴더 권한을 확인하세요.")
        else:
            value.set("")
            status.set(f"저장 완료 · {location}\n이 창을 닫아도 됩니다. API 연결 확인은 아직 하지 않았습니다.")

    ttk.Button(frame, text="복사한 키 붙여넣기", command=paste).grid(row=4, column=0, sticky="w")
    ttk.Button(frame, text="입력 지우기", command=lambda: value.set("")).grid(row=4, column=1, padx=8)
    save_button = ttk.Button(frame, text="새 키 저장", command=save, state="disabled")
    save_button.grid(row=4, column=2, sticky="e")
    ttk.Label(frame, text=f"저장 위치: {location}\n"
              "‘새 키 저장’을 누르면 기존 파일을 교체합니다.").grid(
        row=5, column=0, columnspan=3, sticky="w", pady=(16, 0))
    value.trace_add("write", changed)
    entry.bind("<<Paste>>", paste)
    root.bind("<Escape>", lambda event: root.destroy())
    root.after(100, entry.focus_force)
    root.mainloop()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="입력 글자 수를 보여주는 마스킹 입력 창 열기")
    parser.add_argument("--service", choices=("visitors", "pet"), default="visitors",
                        help="키 저장 대상: visitors(기존 방문자 API), pet(반려동물 API)")
    args = parser.parse_args()
    target = PET_TARGET if args.service == "pet" else TARGET
    if args.gui:
        return run_gui(target)
    if not sys.stdin.isatty():
        print("사용자 PC의 대화형 PowerShell 터미널에서 실행하세요.")
        return 2
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            key = getpass.getpass("공공데이터포털 인증키 붙여넣기 (화면에 표시되지 않음): ").strip()
        except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
            print("\n키 입력을 완료하지 못했습니다. 저장하지 않았습니다.")
            return 2
    try:
        save_key(key, target=target)
    except (ValueError, FileExistsError) as error:
        print(error)
        return 2
    except OSError:
        print("파일을 저장하지 못했습니다. 파일 사용 여부와 폴더 권한을 확인하세요.")
        return 2
    print(f"키를 .secrets/{target.name}에 저장했습니다. 이 파일은 Git 추적에서 제외됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
