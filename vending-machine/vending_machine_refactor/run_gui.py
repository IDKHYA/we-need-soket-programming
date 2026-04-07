from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = str(PROJECT_ROOT / "src")


def ensure_local_src_first() -> None:
    if SRC_PATH not in sys.path:
        sys.path.insert(0, SRC_PATH)


def ensure_installed() -> None:
    """의존 패키지가 없으면 editable install을 수행합니다."""
    ensure_local_src_first()
    try:
        import openpyxl  # noqa: F401
        import PySide6  # noqa: F401
        import httpx  # noqa: F401
    except ImportError:
        print("[설정] 필요한 패키지를 설치합니다. (pip install -e .)")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        print("   완료!")


def ensure_data_files() -> Path:
    """운영용 워크북을 우선 사용하고, 없으면 템플릿과 데모를 준비합니다."""
    data_dir = PROJECT_ROOT / "data"
    workbook_path = data_dir / "vending_machine.xlsx"
    template_path = data_dir / "vending_machine_template.xlsx"
    demo_path = data_dir / "vending_machine_gui_demo.xlsx"

    if workbook_path.exists():
        return workbook_path

    if not template_path.exists():
        print("[설정] 데이터 파일이 없어 템플릿 워크북을 생성합니다.")
        bootstrap = PROJECT_ROOT / "scripts" / "bootstrap_workbook.py"
        subprocess.run([sys.executable, str(bootstrap)], cwd=str(PROJECT_ROOT), check=True)
        print("   완료!")

    if workbook_path.exists():
        return workbook_path

    seed = PROJECT_ROOT / "scripts" / "seed_demo_analytics.py"
    if seed.exists() and not demo_path.exists():
        print("[설정] 데모 분석용 판매 데이터를 생성합니다.")
        subprocess.run([sys.executable, str(seed)], cwd=str(PROJECT_ROOT), check=True)
        print("   완료!")

    if workbook_path.exists():
        return workbook_path
    if template_path.exists():
        return template_path
    return demo_path


def main() -> int:
    print("=" * 52)
    print("  자판기 실행중...")
    print("=" * 52)

    ensure_local_src_first()
    ensure_installed()

    workbook = ensure_data_files()
    print(f"[실행] 워크북: {workbook.name}")
    print()

    from vending_machine.presentation.pyside_gui import run

    return run(workbook)


if __name__ == "__main__":
    raise SystemExit(main())