from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QPoint, QRectF, Qt, QSize
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vending_machine.app.report_service import SalesReportService
from vending_machine.app.service import VendingMachineService
from vending_machine.infra.excel_repository import ExcelMachineRepository


DENOMS = [10, 50, 100, 500, 1000]
THEME = {
    "navy": "#0A2B68",
    "navy_dark": "#071C48",
    "blue": "#318CFF",
    "blue_soft": "#DCEBFF",
    "silver": "#D5D8DE",
    "silver_dark": "#A1A9B5",
    "bg": "#A9D6FF",
    "panel": "#F7F8FB",
    "ok": "#0FB980",
    "warn": "#F59E0B",
    "danger": "#E74C3C",
    "ink": "#16223A",
}


def format_won(value: int) -> str:
    return f"{value:,}원"


def qdate_to_date(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class ImageResolver:
    def __init__(self, workbook_path: Path):
        self.workbook_path = workbook_path.resolve()
        self.base_candidates = [
            self.workbook_path.parent,
            self.workbook_path.parent.parent,
            Path.cwd(),
        ]

    def resolve(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        for base in self.base_candidates:
            path = (base / candidate).resolve()
            if path.exists():
                return path
        return None


class BackendController:
    def __init__(self, workbook_path: Path):
        self.workbook_path = workbook_path
        self.repo = ExcelMachineRepository(workbook_path)
        self.report_service = SalesReportService(self.repo)

    def load(self):
        state = self.repo.load_state()
        session = self.repo.load_session()
        return state, session

    def service(self) -> VendingMachineService:
        state, session = self.load()
        return VendingMachineService(state, session)

    def insert_cash(self, denomination: int):
        svc = self.service()
        result = svc.insert_cash(denomination)
        self.repo.commit(svc.state, svc.session, result.cash_events)
        return result

    def purchase(self, product_id: str):
        svc = self.service()
        result = svc.purchase(product_id)
        events = [*result.sale_events, *result.cash_events, *result.stock_events]
        self.repo.commit(svc.state, svc.session, events)
        return result

    def refund(self):
        svc = self.service()
        result = svc.refund()
        self.repo.commit(svc.state, svc.session, result.cash_events)
        return result

    def authenticate_admin(self, password: str) -> bool:
        svc = self.service()
        return svc.authenticate_admin(password)

    def refill_product(self, product_id: str):
        svc = self.service()
        events = svc.refill_product_to_max(product_id)
        self.repo.commit(svc.state, svc.session, events)

    def adjust_product_stock(self, product_id: str, delta: int):
        svc = self.service()
        events = svc.adjust_product_stock(product_id, delta)
        self.repo.commit(svc.state, svc.session, events)

    def refill_cash_to_minimum(self):
        svc = self.service()
        events = svc.refill_cash_to_minimum()
        self.repo.commit(svc.state, svc.session, events)

    def collect_cash(self, keep_minimum: bool = True):
        svc = self.service()
        events = svc.collect_cash(keep_minimum=keep_minimum)
        self.repo.commit(svc.state, svc.session, events)

    def update_product(self, product_id: str, **kwargs):
        svc = self.service()
        events = svc.update_product(product_id, **kwargs)
        self.repo.commit(svc.state, svc.session, events)


class StatCard(QFrame):
    def __init__(self, title: str, accent: str = THEME["navy"], inverted: bool = False):
        super().__init__()
        self.title_label = QLabel(title)
        self.value_label = QLabel("-")
        self.caption_label = QLabel("")
        bg = accent if inverted else "white"
        fg = "white" if inverted else THEME["ink"]
        sub = "rgba(255,255,255,0.72)" if inverted else "#64748B"
        self.setStyleSheet(
            f"QFrame{{background:{bg}; border-radius:22px;}} QLabel{{color:{fg};}}"
            f"QLabel#caption{{color:{sub};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.title_label.setStyleSheet("font-size:12px; font-weight:700;")
        self.value_label.setStyleSheet("font-size:30px; font-weight:900;")
        self.caption_label.setObjectName("caption")
        self.caption_label.setStyleSheet("font-size:12px; font-weight:600;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str, caption: str = ""):
        self.value_label.setText(value)
        self.caption_label.setText(caption)


class ProductCard(QFrame):
    def __init__(self, product, image_resolver: ImageResolver, on_buy, parent=None):
        super().__init__(parent)
        self.product_id = product.product_id
        self.on_buy = on_buy
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label = QLabel(product.name)
        self.price_label = QLabel(format_won(product.price))
        self.stock_label = QLabel()
        self.indicator = QLabel()
        self.buy_btn = QPushButton("선택")
        self.image_resolver = image_resolver

        self.setObjectName("productCard")
        self.setStyleSheet(
            "QFrame#productCard{background:transparent;}"
            "QLabel{color:#0F172A;}"
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #56A8FF, stop:1 #1D67E4);"
            "border:2px solid #0A2B68; border-radius:14px; color:white; font-weight:900; padding:8px 0;}"
            "QPushButton:disabled{background:#CBD5E1; border-color:#94A3B8; color:#64748B;}"
        )
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-size:17px; font-weight:900;")
        self.price_label.setStyleSheet("font-size:16px; font-weight:800; color:#1E3A8A;")
        self.stock_label.setStyleSheet("font-size:12px; font-weight:700; color:#64748B;")
        self.indicator.setFixedSize(32, 12)
        self.buy_btn.clicked.connect(lambda: self.on_buy(self.product_id))

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        glass = QFrame()
        glass.setFixedHeight(190)
        glass.setStyleSheet(
            "QFrame{border-radius:22px; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgba(255,255,255,0.92), stop:0.58 rgba(234,240,247,0.68), stop:1 rgba(179,190,207,0.72));"
            "border:2px solid rgba(255,255,255,0.6);}"
        )
        glass_layout = QVBoxLayout(glass)
        glass_layout.setContentsMargins(10, 10, 10, 10)
        glass_layout.addWidget(self.image_label, 1)
        layout.addWidget(glass)
        layout.addWidget(self.name_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.stock_label)
        ind_wrap = QHBoxLayout()
        ind_wrap.addStretch(1)
        ind_wrap.addWidget(self.indicator)
        ind_wrap.addStretch(1)
        layout.addLayout(ind_wrap)
        layout.addWidget(self.buy_btn)
        self.update_from_product(product, balance=0)

    def update_from_product(self, product, balance: int):
        self.name_label.setText(product.name)
        self.price_label.setText(format_won(product.price))
        self.stock_label.setText(f"재고 {product.stock}/{product.max_stock}")
        affordable = balance >= product.price
        available = product.active and product.stock > 0
        self.buy_btn.setEnabled(available and affordable)
        indicator_color = THEME["ok"] if available else THEME["danger"]
        self.indicator.setStyleSheet(f"background:{indicator_color}; border:1px solid white; border-radius:6px;")
        pix_path = self.image_resolver.resolve(product.image_path)
        if pix_path and pix_path.exists():
            pix = QPixmap(str(pix_path)).scaled(118, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(pix)
        else:
            self.image_label.setText(product.name)
            self.image_label.setStyleSheet("font-weight:900; color:#334155;")


class DisplayPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.amount_label = QLabel(format_won(0))
        self.status_label = QLabel("음료를 선택하거나 금액을 투입해 주세요")
        self.pickup_label = QLabel("방금 뽑은 음료가 이곳에 표시됩니다")
        self.setFixedWidth(320)
        self.setStyleSheet(
            "QFrame{border-radius:28px; background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E4E7EC, stop:0.2 #C7CCD5, stop:0.5 #F5F6F8, stop:1 #C7CCD5);}"
            "QPushButton{border:none;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.display = QFrame()
        self.display.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2D2D2D, stop:1 #161616); border-radius:20px; border:2px solid #4B5563;}"
            "QLabel{color:white;}"
        )
        dlay = QVBoxLayout(self.display)
        dlay.setContentsMargins(16, 12, 16, 12)
        title = QLabel("금액 표시")
        title.setStyleSheet("font-size:12px; font-weight:700; color:#D4D4D8;")
        self.amount_label.setStyleSheet("font-size:34px; font-weight:900; color:white;")
        self.amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size:12px; font-weight:700; color:#86EFAC;")
        dlay.addWidget(title)
        dlay.addWidget(self.amount_label)
        dlay.addWidget(self.status_label)
        layout.addWidget(self.display)

        label_row = QHBoxLayout()
        label_row.setSpacing(12)
        for text in ("동전 투입구", "지폐 투입구"):
            box = QLabel(text)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setFixedHeight(58)
            box.setStyleSheet("background:rgba(255,255,255,0.82); border-radius:16px; font-weight:800; color:#475569;")
            label_row.addWidget(box)
        layout.addLayout(label_row)

        insert_group = QFrame()
        insert_group.setStyleSheet("QFrame{background:rgba(255,255,255,0.82); border-radius:22px;}")
        iglay = QVBoxLayout(insert_group)
        iglay.setContentsMargins(16, 16, 16, 16)
        title_wrap = QHBoxLayout()
        t1 = QLabel("투입 패널")
        t2 = QLabel("빈칸 위치 전용 머니 존")
        t1.setStyleSheet("font-size:12px; font-weight:800; color:#64748B;")
        t2.setStyleSheet("font-size:19px; font-weight:900; color:#0F172A;")
        left = QVBoxLayout()
        left.addWidget(t1)
        left.addWidget(t2)
        title_wrap.addLayout(left)
        title_wrap.addStretch(1)
        iglay.addLayout(title_wrap)
        self.money_grid = QGridLayout()
        self.money_grid.setSpacing(10)
        iglay.addLayout(self.money_grid)
        self.refund_btn = QPushButton("금액 반환")
        self.refund_btn.setFixedHeight(48)
        self.refund_btn.setStyleSheet("QPushButton{background:#111827; color:white; border-radius:16px; font-weight:900; font-size:15px;} QPushButton:hover{background:#1F2937;}")
        iglay.addWidget(self.refund_btn)
        layout.addWidget(insert_group)

        pickup_box = QFrame()
        pickup_box.setStyleSheet("QFrame{background:rgba(255,255,255,0.78); border-radius:22px;}")
        pkl = QVBoxLayout(pickup_box)
        pkl.setContentsMargins(16, 16, 16, 16)
        pkl.addWidget(QLabel("음료 나오는 곳"))
        stage = QLabel()
        stage.setMinimumHeight(180)
        stage.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #64748B, stop:0.22 #1F2937, stop:0.58 #A8B0BC, stop:1 #111827);"
            "border-radius:20px; color:white; font-weight:900; font-size:14px; padding:18px;"
        )
        stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stage.setWordWrap(True)
        self.pickup_label = stage
        pkl.addWidget(stage)
        pick = QLabel("PICK UP")
        pick.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick.setStyleSheet("font-size:34px; font-weight:900; color:#0A2B68;")
        pkl.addWidget(pick)
        layout.addWidget(pickup_box, 1)

        self.admin_btn = QPushButton("관리자 모드")
        self.admin_btn.setFixedHeight(46)
        self.admin_btn.setStyleSheet("QPushButton{background:white; color:#0F172A; border-radius:16px; font-weight:900; font-size:15px; border:1px solid #CBD5E1;} QPushButton:hover{background:#F8FAFC;}")
        layout.addWidget(self.admin_btn)

    def set_balance(self, balance: int):
        self.amount_label.setText(format_won(balance))

    def set_status(self, message: str, ok: bool = True):
        color = "#86EFAC" if ok else "#FCA5A5"
        self.status_label.setStyleSheet(f"font-size:12px; font-weight:700; color:{color};")
        self.status_label.setText(message)

    def set_pickup(self, message: str):
        self.pickup_label.setText(message)


class ProductEditDialog(QDialog):
    def __init__(self, product, image_resolver: ImageResolver, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"상품 편집 · {product.name}")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.product_id = product.product_id
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(product.name)
        self.price_spin = QSpinBox()
        self.price_spin.setRange(10, 100000)
        self.price_spin.setSingleStep(10)
        self.price_spin.setValue(product.price)
        self.max_stock_spin = QSpinBox()
        self.max_stock_spin.setRange(1, 999)
        self.max_stock_spin.setValue(product.max_stock)
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(1, 99)
        self.slot_spin.setValue(product.slot_no or 1)
        self.active_check = QCheckBox("판매 가능")
        self.active_check.setChecked(product.active)
        self.image_edit = QLineEdit(product.image_path or "")
        form.addRow("상품명", self.name_edit)
        form.addRow("가격", self.price_spin)
        form.addRow("최대 재고", self.max_stock_spin)
        form.addRow("슬롯 번호", self.slot_spin)
        form.addRow("이미지 경로", self.image_edit)
        form.addRow("상태", self.active_check)
        layout.addLayout(form)
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setFixedHeight(180)
        preview.setStyleSheet("background:#F8FAFC; border:1px solid #E2E8F0; border-radius:18px;")
        pix_path = image_resolver.resolve(product.image_path)
        if pix_path and pix_path.exists():
            preview.setPixmap(QPixmap(str(pix_path)).scaled(130, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(preview)
        btn_row = QHBoxLayout()
        save_btn = QPushButton("저장")
        cancel_btn = QPushButton("취소")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def payload(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "price": self.price_spin.value(),
            "max_stock": self.max_stock_spin.value(),
            "slot_no": self.slot_spin.value(),
            "active": self.active_check.isChecked(),
            "image_path": self.image_edit.text().strip(),
        }


class AdminLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 인증")
        self.setModal(True)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("관리자 비밀번호를 입력하세요"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("비밀번호")
        self.password_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.password_edit)
        help_label = QLabel("기본 비밀번호: admin!12345")
        help_label.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(help_label)
        row = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        ok_btn = QPushButton("인증")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        layout.addLayout(row)

    @property
    def password(self) -> str:
        return self.password_edit.text()


class ProductManageItem(QFrame):
    def __init__(self, product, edit_cb, refill_cb, minus_cb, plus_cb, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame{background:white; border-radius:20px;} QPushButton{border-radius:14px; padding:8px 10px; font-weight:800;}")
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        left = QVBoxLayout()
        name = QLabel(product.name)
        name.setStyleSheet("font-size:18px; font-weight:900; color:#0F172A;")
        meta = QLabel(f"{product.product_id} · {format_won(product.price)} · 슬롯 {product.slot_no}")
        meta.setStyleSheet("color:#64748B; font-weight:700;")
        left.addWidget(name)
        left.addWidget(meta)
        top.addLayout(left)
        top.addStretch(1)
        edit_btn = QPushButton("편집")
        edit_btn.setStyleSheet("background:#EEF2FF; color:#1D4ED8;")
        edit_btn.clicked.connect(lambda: edit_cb(product))
        refill_btn = QPushButton("최대 보충")
        refill_btn.setStyleSheet("background:#0F172A; color:white;")
        refill_btn.clicked.connect(lambda: refill_cb(product.product_id))
        top.addWidget(edit_btn)
        top.addWidget(refill_btn)
        layout.addLayout(top)
        progress = QProgressBar()
        progress.setRange(0, product.max_stock)
        progress.setValue(product.stock)
        progress.setFormat(f"재고 {product.stock}/{product.max_stock}")
        progress.setTextVisible(True)
        progress.setStyleSheet(
            "QProgressBar{height:14px; border-radius:7px; background:#E2E8F0; text-align:center; font-weight:700;}"
            "QProgressBar::chunk{border-radius:7px; background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2563EB, stop:1 #0EA5E9);}"
        )
        layout.addWidget(progress)
        row = QHBoxLayout()
        minus = QPushButton("-1")
        minus.setStyleSheet("background:#E2E8F0; color:#0F172A;")
        minus.clicked.connect(lambda: minus_cb(product.product_id))
        plus = QPushButton("+1")
        plus.setStyleSheet("background:#1E40AF; color:white;")
        plus.clicked.connect(lambda: plus_cb(product.product_id))
        row.addStretch(1)
        row.addWidget(minus)
        row.addWidget(plus)
        layout.addLayout(row)


class AdminDashboardDialog(QDialog):
    def __init__(self, controller: BackendController, image_resolver: ImageResolver, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.image_resolver = image_resolver
        self.setWindowTitle("자판기 운영 센터")
        self.resize(1280, 860)
        self.setStyleSheet(
            "QDialog{background:#F3F6FB;} QTabWidget::pane{border:0;} QTabBar::tab{padding:10px 18px; border-radius:16px; background:white; margin-right:8px; font-weight:800;} QTabBar::tab:selected{background:#0F172A; color:white;}"
        )
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("ADMIN DASHBOARD")
        title.setStyleSheet("font-size:12px; font-weight:800; color:#2563EB;")
        subtitle = QLabel("자판기 운영 센터")
        subtitle.setStyleSheet("font-size:32px; font-weight:900; color:#0F172A;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.range_combo = QComboBox()
        self.range_combo.addItems(["오늘", "최근 7일", "최근 30일", "전체", "사용자 지정"])
        self.range_combo.currentTextChanged.connect(self.on_range_changed)
        self.start_date = QDateEdit(calendarPopup=True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date = QDateEdit(calendarPopup=True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.apply_btn = QPushButton("적용")
        self.apply_btn.clicked.connect(self.refresh_all)
        header.addWidget(self.range_combo)
        header.addWidget(self.start_date)
        header.addWidget(self.end_date)
        header.addWidget(self.apply_btn)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.report_tab = QWidget()
        self.product_tab = QWidget()
        self.cash_tab = QWidget()
        self.tabs.addTab(self.report_tab, "통계")
        self.tabs.addTab(self.product_tab, "상품 관리")
        self.tabs.addTab(self.cash_tab, "현금 관리")

        self._build_report_tab()
        self._build_product_tab()
        self._build_cash_tab()
        self.on_range_changed(self.range_combo.currentText())
        self.refresh_all()

    def selected_range(self) -> tuple[date | None, date | None]:
        label = self.range_combo.currentText()
        today = date.today()
        if label == "오늘":
            return today, today
        if label == "최근 7일":
            return today - timedelta(days=6), today
        if label == "최근 30일":
            return today - timedelta(days=29), today
        if label == "전체":
            return None, None
        return qdate_to_date(self.start_date.date()), qdate_to_date(self.end_date.date())

    def on_range_changed(self, label: str):
        today = date.today()
        enabled = label == "사용자 지정"
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        if label == "오늘":
            start = end = today
        elif label == "최근 7일":
            start, end = today - timedelta(days=6), today
        elif label == "최근 30일":
            start, end = today - timedelta(days=29), today
        elif label == "전체":
            start, end = today - timedelta(days=29), today
        else:
            return
        self.start_date.setDate(QDate(start.year, start.month, start.day))
        self.end_date.setDate(QDate(end.year, end.month, end.day))

    def refresh_all(self):
        self._refresh_report_tab()
        self._refresh_product_tab()
        self._refresh_cash_tab()

    def _build_report_tab(self):
        layout = QVBoxLayout(self.report_tab)
        self.summary_cards = [
            StatCard("순매출", THEME["navy"], inverted=True),
            StatCard("판매 건수"),
            StatCard("평균 객단가"),
            StatCard("베스트셀러"),
        ]
        cards = QHBoxLayout()
        for card in self.summary_cards:
            cards.addWidget(card)
        layout.addLayout(cards)

        chart_grid = QGridLayout()
        chart_grid.setSpacing(14)
        self.daily_chart = self._empty_chart_view()
        self.product_chart = self._empty_chart_view()
        self.cash_chart = self._empty_chart_view()
        self.trend_chart = self._empty_chart_view()
        chart_grid.addWidget(self._chart_box("일별 순매출", self.daily_chart), 0, 0)
        chart_grid.addWidget(self._chart_box("상품 판매 비중", self.product_chart), 0, 1)
        chart_grid.addWidget(self._chart_box("현금 흐름", self.cash_chart), 1, 0)
        chart_grid.addWidget(self._chart_box("누적 판매 추이", self.trend_chart), 1, 1)
        layout.addLayout(chart_grid)

        bottom = QHBoxLayout()
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["시간", "상품", "결제", "거스름돈"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.recent_table.setAlternatingRowColors(True)
        self.low_stock_list = QListWidget()
        bottom.addWidget(self._chart_box("최근 판매 내역", self.recent_table), 2)
        bottom.addWidget(self._chart_box("저재고 알림", self.low_stock_list), 1)
        layout.addLayout(bottom)

    def _build_product_tab(self):
        layout = QVBoxLayout(self.product_tab)
        note = QLabel("상품명, 가격, 최대 재고, 표시 슬롯과 이미지를 편집할 수 있습니다.")
        note.setStyleSheet("color:#64748B; font-size:13px; font-weight:700;")
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.product_list_layout = QVBoxLayout(container)
        self.product_list_layout.setSpacing(12)
        self.product_list_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def _build_cash_tab(self):
        layout = QVBoxLayout(self.cash_tab)
        top = QHBoxLayout()
        self.cash_total_card = StatCard("보유 현금", THEME["navy"], inverted=True)
        self.coin_mix_card = StatCard("권종 구성")
        top.addWidget(self.cash_total_card)
        top.addWidget(self.coin_mix_card)
        layout.addLayout(top)
        self.cash_pie_chart = self._empty_chart_view()
        layout.addWidget(self._chart_box("현금 권종 비중", self.cash_pie_chart), 1)
        btn_row = QHBoxLayout()
        refill_btn = QPushButton("최소 잔돈 기준으로 보충")
        refill_btn.clicked.connect(self._handle_refill_cash)
        collect_btn = QPushButton("최소 잔돈만 남기고 수거")
        collect_btn.clicked.connect(self._handle_collect_cash)
        for btn in (refill_btn, collect_btn):
            btn.setMinimumHeight(46)
            btn.setStyleSheet("QPushButton{background:#0F172A; color:white; border-radius:16px; font-weight:900; padding:0 16px;} QPushButton:hover{background:#1F2937;}")
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)
        self.cash_table = QTableWidget(0, 4)
        self.cash_table.setHorizontalHeaderLabels(["권종", "현재 수량", "최소 유지", "최대 적재"])
        self.cash_table.horizontalHeader().setStretchLastSection(True)
        self.cash_table.verticalHeader().setVisible(False)
        self.cash_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cash_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._chart_box("잔돈 재고", self.cash_table), 1)

    def _chart_box(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet("QGroupBox{font-size:15px; font-weight:900; color:#0F172A; background:white; border-radius:22px; margin-top:10px; padding-top:14px;} QGroupBox::title{subcontrol-origin:margin; left:18px; padding:0 6px;}")
        layout = QVBoxLayout(box)
        layout.addWidget(widget)
        return box

    def _empty_chart_view(self) -> QChartView:
        chart = QChart()
        chart.legend().setVisible(True)
        chart.setBackgroundVisible(False)
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(280)
        view.setStyleSheet("background:transparent;")
        return view

    def _refresh_report_tab(self):
        start, end = self.selected_range()
        report = self.controller.report_service
        summary = report.summary(start, end)
        card_values = [
            (format_won(summary["net_sales"]), f"거스름돈 제외 · {summary['sales_count']}건"),
            (f"{summary['sales_count']}건", f"총 판매 수량 {summary['units_sold']}개"),
            (format_won(summary["avg_ticket"]), "순매출 기준 평균 결제"),
            (summary["best_seller"], "선택 기간 최다 판매"),
        ]
        for card, (value, caption) in zip(self.summary_cards, card_values):
            card.set_value(value, caption)

        self._set_daily_sales_chart(report.daily_sales(start, end))
        self._set_product_sales_chart(report.product_sales(start, end))
        self._set_cash_flow_chart(report.cash_flow(start, end))
        self._set_trend_chart(report.sales_events(start, end))
        self._set_recent_sales_table(report.sales_events(start, end)[-12:])
        self._set_low_stock_list(report.low_stock_products(threshold=2))

    def _refresh_product_tab(self):
        while self.product_list_layout.count():
            item = self.product_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        state, _ = self.controller.load()
        for product in sorted(state.products.values(), key=lambda p: (p.slot_no or 0, p.product_id)):
            widget = ProductManageItem(
                product,
                edit_cb=self._open_product_edit,
                refill_cb=self._handle_refill_product,
                minus_cb=lambda pid, delta=-1: self._handle_adjust_stock(pid, delta),
                plus_cb=lambda pid, delta=1: self._handle_adjust_stock(pid, delta),
            )
            self.product_list_layout.addWidget(widget)
        self.product_list_layout.addStretch(1)

    def _refresh_cash_tab(self):
        state, _ = self.controller.load()
        cash = state.cash_inventory
        total = cash.total_amount()
        mix = ", ".join(f"{denom}원 {qty}개" for denom, qty in sorted(cash.counts.items()))
        self.cash_total_card.set_value(format_won(total), "현재 자판기 내부 보유액")
        self.coin_mix_card.set_value(f"{len(cash.counts)}종", mix)
        self._set_cash_mix_chart(cash.counts)
        self.cash_table.setRowCount(0)
        for row_idx, denom in enumerate(sorted(cash.counts)):
            self.cash_table.insertRow(row_idx)
            values = [format_won(denom), str(cash.counts[denom]), str(cash.min_keep.get(denom, 0)), str(cash.max_capacity.get(denom, 0))]
            for col_idx, value in enumerate(values):
                self.cash_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _set_daily_sales_chart(self, rows):
        chart = QChart()
        chart.setTitle("일별 순매출")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        if not rows:
            chart.setTitle("일별 순매출 · 데이터 없음")
            self.daily_chart.setChart(chart)
            return
        bar_set = QBarSet("순매출")
        categories = []
        max_value = 0
        for row in rows:
            categories.append(row.date[5:])
            bar_set << row.net_sales
            max_value = max(max_value, row.net_sales)
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, max(max_value * 1.2, 1000))
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        chart.legend().setVisible(False)
        self.daily_chart.setChart(chart)

    def _set_product_sales_chart(self, rows):
        chart = QChart()
        chart.setTitle("상품 판매 비중")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        series = QPieSeries()
        if not rows:
            chart.setTitle("상품 판매 비중 · 데이터 없음")
            self.product_chart.setChart(chart)
            return
        for row in rows:
            slice_ = series.append(row.product_name, row.net_sales)
            slice_.setLabelVisible(True)
        series.setHoleSize(0.38)
        chart.addSeries(series)
        self.product_chart.setChart(chart)

    def _set_cash_flow_chart(self, rows):
        chart = QChart()
        chart.setTitle("현금 흐름")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        if not rows:
            chart.setTitle("현금 흐름 · 데이터 없음")
            self.cash_chart.setChart(chart)
            return
        bar_set = QBarSet("금액")
        categories = []
        max_value = 0
        for row in rows:
            categories.append(row.event_type)
            bar_set << row.total_amount
            max_value = max(max_value, row.total_amount)
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, max(max_value * 1.2, 1000))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        chart.legend().setVisible(False)
        self.cash_chart.setChart(chart)

    def _set_trend_chart(self, events):
        chart = QChart()
        chart.setTitle("누적 판매 추이")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        if not events:
            chart.setTitle("누적 판매 추이 · 데이터 없음")
            self.trend_chart.setChart(chart)
            return
        cumulative = 0
        by_day = []
        grouped = {}
        for event in events:
            key = event["sold_at_dt"].strftime("%m-%d")
            grouped[key] = grouped.get(key, 0) + int(event.get("unit_price", 0))
        bar_set = QBarSet("누적 매출")
        cats = []
        max_val = 0
        for key in grouped:
            cumulative += grouped[key]
            cats.append(key)
            bar_set << cumulative
            max_val = max(max_val, cumulative)
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(cats)
        axis_y = QValueAxis()
        axis_y.setRange(0, max(max_val * 1.2, 1000))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        chart.legend().setVisible(False)
        self.trend_chart.setChart(chart)

    def _set_recent_sales_table(self, events):
        self.recent_table.setRowCount(0)
        for row_idx, event in enumerate(reversed(events)):
            self.recent_table.insertRow(row_idx)
            values = [
                event["sold_at_dt"].strftime("%m-%d %H:%M"),
                str(event.get("product_name", "")),
                format_won(int(event.get("paid_amount", 0))),
                format_won(int(event.get("change_amount", 0))),
            ]
            for col_idx, value in enumerate(values):
                self.recent_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _set_low_stock_list(self, rows):
        self.low_stock_list.clear()
        if not rows:
            item = QListWidgetItem("모든 상품 재고가 안정적입니다")
            self.low_stock_list.addItem(item)
            return
        for row in rows:
            self.low_stock_list.addItem(f"{row['name']} · 재고 {row['stock']}/{row['max_stock']} · 보충 권장")

    def _set_cash_mix_chart(self, counts: dict[int, int]):
        chart = QChart()
        chart.setTitle("현금 권종 비중")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        series = QPieSeries()
        for denom, qty in sorted(counts.items()):
            if qty > 0:
                slice_ = series.append(f"{denom}원", denom * qty)
                slice_.setLabelVisible(True)
        if series.count() == 0:
            chart.setTitle("현금 권종 비중 · 데이터 없음")
        else:
            series.setHoleSize(0.36)
            chart.addSeries(series)
        self.cash_pie_chart.setChart(chart)

    def _handle_refill_product(self, product_id: str):
        self.controller.refill_product(product_id)
        self.refresh_all()

    def _handle_adjust_stock(self, product_id: str, delta: int):
        self.controller.adjust_product_stock(product_id, delta)
        self.refresh_all()

    def _open_product_edit(self, product):
        dialog = ProductEditDialog(product, self.image_resolver, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.controller.update_product(product.product_id, **dialog.payload())
                self.refresh_all()
            except Exception as exc:
                QMessageBox.warning(self, "저장 실패", str(exc))

    def _handle_refill_cash(self):
        self.controller.refill_cash_to_minimum()
        self.refresh_all()

    def _handle_collect_cash(self):
        self.controller.collect_cash(keep_minimum=True)
        self.refresh_all()


class VendingMachineWindow(QMainWindow):
    def __init__(self, workbook_path: Path):
        super().__init__()
        self.controller = BackendController(workbook_path)
        self.image_resolver = ImageResolver(workbook_path)
        self.setWindowTitle("자동판매기 · PySide6")
        self.resize(1560, 980)
        self.setStyleSheet("QMainWindow{background:#A7D5FF;} QWidget{font-family:'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR';}")
        self._build_ui()
        self.refresh_view()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        machine_wrap = QFrame()
        machine_wrap.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FDFEFF, stop:1 #E5E9F2); border-radius:40px;}"
        )
        shadow = QGraphicsDropShadowEffect(blurRadius=42, xOffset=0, yOffset=18)
        shadow.setColor(QColor(15, 23, 42, 80))
        machine_wrap.setGraphicsEffect(shadow)
        machine_wrap.setMinimumWidth(1160)
        machine_layout = QVBoxLayout(machine_wrap)
        machine_layout.setContentsMargins(24, 24, 24, 24)
        machine_layout.setSpacing(18)
        header = QFrame()
        header.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #081F53, stop:0.5 #0B347E, stop:1 #081F53); border-radius:28px;} QLabel{color:white;}"
        )
        hlay = QVBoxLayout(header)
        hlay.setContentsMargins(26, 18, 26, 18)
        title = QLabel("자동판매기")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:42px; font-weight:900;")
        sub = QLabel("Premium Smart Vending Interface · PySide6")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size:14px; font-weight:700; color:#DBEAFE;")
        hlay.addWidget(title)
        hlay.addWidget(sub)
        machine_layout.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        left = QFrame()
        left.setStyleSheet("QFrame{background:rgba(255,255,255,0.7); border-radius:30px;}")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(16)
        showcase = QFrame()
        showcase.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0E3A87, stop:1 #082766); border-radius:28px;}")
        sc_layout = QVBoxLayout(showcase)
        sc_layout.setContentsMargins(16, 16, 16, 16)
        self.slot_grid = QGridLayout()
        self.slot_grid.setSpacing(14)
        sc_layout.addLayout(self.slot_grid)
        left_layout.addWidget(showcase)
        pickup_box = QFrame()
        pickup_box.setStyleSheet("QFrame{background:rgba(255,255,255,0.84); border-radius:24px;}")
        pk = QVBoxLayout(pickup_box)
        pk.setContentsMargins(18, 18, 18, 18)
        head = QLabel("음료 나오는 곳")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setStyleSheet("font-size:22px; font-weight:900; color:#0F172A;")
        pk.addWidget(head)
        self.pickup_stage = QLabel("방금 뽑은 음료가 아래에 표시됩니다")
        self.pickup_stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pickup_stage.setWordWrap(True)
        self.pickup_stage.setMinimumHeight(180)
        self.pickup_stage.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #596579, stop:0.18 #1E293B, stop:0.56 #B5BEC9, stop:1 #111827); border-radius:24px; color:white; font-size:18px; font-weight:800;"
        )
        pk.addWidget(self.pickup_stage)
        pick_label = QLabel("PICK UP")
        pick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick_label.setStyleSheet("font-size:38px; font-weight:900; color:#0A2B68;")
        pk.addWidget(pick_label)
        left_layout.addWidget(pickup_box)
        body.addWidget(left, 1)

        self.display_panel = DisplayPanel()
        body.addWidget(self.display_panel)
        machine_layout.addLayout(body)
        root.addWidget(machine_wrap, 1)

        insight_panel = QFrame()
        insight_panel.setFixedWidth(340)
        insight_panel.setStyleSheet("QFrame{background:rgba(255,255,255,0.7); border-radius:30px;}")
        side = QVBoxLayout(insight_panel)
        side.setContentsMargins(18, 18, 18, 18)
        side.setSpacing(12)
        label = QLabel("스마트 인사이트")
        label.setStyleSheet("font-size:12px; font-weight:800; color:#2563EB;")
        big = QLabel("운영 상태")
        big.setStyleSheet("font-size:28px; font-weight:900; color:#0F172A;")
        side.addWidget(label)
        side.addWidget(big)
        self.side_cards = [
            StatCard("오늘 순매출", THEME["navy"], inverted=True),
            StatCard("베스트셀러"),
            StatCard("보유 현금"),
            StatCard("저재고 상품"),
        ]
        for card in self.side_cards:
            side.addWidget(card)
        tip = QTextEdit()
        tip.setReadOnly(True)
        tip.setText("UI 포인트\n\n• 투입 패널을 실제 자판기 우측 빈 공간으로 이동\n• 상품 선택은 진열창 아래 버튼으로 유지\n• 관리자 모드에서는 날짜 필터 기반 차트와 제품 편집을 지원\n• 엑셀 기반 백엔드와 즉시 연결되는 구조")
        tip.setStyleSheet("background:#FFF7ED; border:0; border-radius:22px; padding:14px; color:#7C2D12; font-size:14px; font-weight:700;")
        side.addWidget(tip, 1)
        root.addWidget(insight_panel)

        self.display_panel.refund_btn.clicked.connect(self.handle_refund)
        self.display_panel.admin_btn.clicked.connect(self.open_admin)
        for idx, denom in enumerate(DENOMS):
            btn = QPushButton()
            btn.setFixedHeight(82)
            btn.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #F0F9FF, stop:1 #DBEAFE); border:1px solid #BFDBFE; border-radius:18px; text-align:left; padding:12px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E0F2FE, stop:1 #BFDBFE);}"
            )
            btn.setText(f"INSERT\n{format_won(denom)}")
            btn.clicked.connect(lambda checked=False, d=denom: self.handle_insert(d))
            self.display_panel.money_grid.addWidget(btn, idx // 2, idx % 2)

    def refresh_view(self):
        state, session = self.controller.load()
        self.state = state
        self.session = session
        self.display_panel.set_balance(session.inserted_total)
        self._render_products()
        self._refresh_side_panel()

    def _render_products(self):
        while self.slot_grid.count():
            item = self.slot_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        products = sorted(self.state.products.values(), key=lambda p: (p.slot_no or 0, p.product_id))
        for idx, product in enumerate(products):
            card = ProductCard(product, self.image_resolver, self.handle_purchase)
            card.update_from_product(product, self.session.inserted_total)
            self.slot_grid.addWidget(card, 0, idx)

    def _refresh_side_panel(self):
        today = date.today()
        report = self.controller.report_service
        summary = report.summary(today, today)
        cash_total = self.state.cash_inventory.total_amount()
        low_stock_count = len(report.low_stock_products(threshold=2))
        self.side_cards[0].set_value(format_won(summary["net_sales"]), f"오늘 판매 {summary['sales_count']}건")
        self.side_cards[1].set_value(summary["best_seller"], "오늘 가장 많이 팔린 음료")
        self.side_cards[2].set_value(format_won(cash_total), "내부 현금 재고")
        self.side_cards[3].set_value(f"{low_stock_count}개", "재고 2개 이하 상품")

    def handle_insert(self, denomination: int):
        try:
            result = self.controller.insert_cash(denomination)
            self.display_panel.set_status(result.message, ok=True)
            self.display_panel.set_pickup("결제를 계속 진행하거나 원하는 음료를 선택해 주세요")
            self.refresh_view()
        except Exception as exc:
            QMessageBox.warning(self, "금액 투입 실패", str(exc))

    def handle_purchase(self, product_id: str):
        try:
            result = self.controller.purchase(product_id)
            if result.success:
                product_name = self.state.products.get(product_id).name if product_id in self.state.products else "음료"
                change_text = ""
                if result.dispensed_change:
                    change_text = " · 거스름돈 " + ", ".join(f"{k}원 x {v}" for k, v in sorted(result.dispensed_change.items(), reverse=True))
                self.display_panel.set_status(result.message, ok=True)
                self.display_panel.set_pickup(f"{product_name} 준비 완료\n아래 PICK UP에서 수령하세요{change_text}")
            else:
                self.display_panel.set_status(result.message, ok=False)
            self.refresh_view()
        except Exception as exc:
            QMessageBox.warning(self, "구매 실패", str(exc))

    def handle_refund(self):
        try:
            result = self.controller.refund()
            ok = result.success and result.refunded_amount >= 0
            self.display_panel.set_status(result.message, ok=ok)
            if result.refunded_amount:
                detail = "\n" + ", ".join(f"{k}원 x {v}" for k, v in sorted(result.refunded_breakdown.items(), reverse=True))
                self.display_panel.set_pickup(f"반환구에서 {format_won(result.refunded_amount)}을 꺼내세요{detail}")
            else:
                self.display_panel.set_pickup("반환할 금액이 없습니다")
            self.refresh_view()
        except Exception as exc:
            QMessageBox.warning(self, "환불 실패", str(exc))

    def open_admin(self):
        login = AdminLoginDialog(self)
        if login.exec() != QDialog.DialogCode.Accepted:
            return
        if not self.controller.authenticate_admin(login.password):
            QMessageBox.warning(self, "인증 실패", "관리자 비밀번호가 올바르지 않습니다.")
            return
        dialog = AdminDashboardDialog(self.controller, self.image_resolver, self)
        dialog.exec()
        self.refresh_view()


def run(workbook_path: str | Path):
    app = QApplication.instance() or QApplication(sys.argv)
    win = VendingMachineWindow(Path(workbook_path))
    win.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if argv:
        workbook = Path(argv[0])
    else:
        workbook = Path("data/vending_machine_gui_demo.xlsx")
        if not workbook.exists():
            workbook = Path("data/vending_machine.xlsx") if Path("data/vending_machine.xlsx").exists() else Path("data/vending_machine_template.xlsx")
    return run(workbook)


if __name__ == "__main__":
    raise SystemExit(main())
