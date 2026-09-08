"""Colors and widget styling shared by the Windows result views."""

PALETTES = {
    "dark": dict(
        background="#303030",
        table="#242225",
        text="#e6e4e7",
        secondary="#a6a6a8",
        muted="#8e8e93",
        line="#48464a",
        segment="#3b3b3c",
        selected="#68686a",
        button="#626264",
        hover="#747476",
        accent="#0a84ff",
        primary="#0864df",
        green="#32d74b",
        red="#ff453a",
        orange="#ffb340",
        track="#464248",
        error_bg="#39272a",
        warning_bg="#3b3327",
        selection="#35363b",
        green_bg="#2d4030",
        red_bg="#4a3030",
        orange_bg="#493d29",
    ),
    "light": dict(
        background="#f5f5f7",
        table="#ffffff",
        text="#242426",
        secondary="#68686d",
        muted="#727278",
        line="#d8d8dc",
        segment="#e7e7ea",
        selected="#ffffff",
        button="#ffffff",
        hover="#ededf1",
        accent="#007aff",
        primary="#0767df",
        green="#187b31",
        red="#d72b25",
        orange="#946000",
        track="#e4e4e9",
        error_bg="#fff0ef",
        warning_bg="#fff6e6",
        selection="#edf2fb",
        green_bg="#e2f0e5",
        red_bg="#fce5e3",
        orange_bg="#f9ebd2",
    ),
}


def stylesheet(c):
    return f"""
    QWidget#results {{ background: {c["background"]}; color: {c["text"]}; }}
    QLabel {{ color: {c["text"]}; background: transparent; font-size: 13px; }}
    QLabel#unit {{ color: {c["secondary"]}; font-size: 16px; font-weight: 500; }}
    QLabel#status {{ color: {c["secondary"]}; font-size: 12px; }}
    QLabel#note {{ color: {c["muted"]}; font-size: 11px; }}
    QLabel#badge {{ border-radius: 11px; padding: 3px 8px; font-size: 11px; }}
    QFrame#segments {{ background: {c["segment"]}; border: 1px solid {c["line"]};
        border-radius: 7px; }}
    QPushButton {{ background: {c["button"]}; color: {c["text"]}; border: 1px solid {c["line"]};
        border-radius: 6px; padding: 3px 16px; font-size: 13px; font-weight: 500; }}
    QPushButton:hover {{ background: {c["hover"]}; }}
    QPushButton:focus {{ border-color: {c["accent"]}; }}
    QPushButton:disabled {{ color: {c["muted"]}; }}
    QPushButton#primary {{ background: {c["primary"]}; color: white;
        border-color: {c["primary"]}; }}
    QPushButton#primary:hover {{ background: {c["accent"]}; }}
    QPushButton#primary:focus {{ border: 1px solid {c["text"]}; }}
    QPushButton#segment {{ border: none; border-radius: 5px; padding: 1px 10px;
        background: transparent; color: {c["text"]}; font-size: 13px; }}
    QPushButton#segment:checked {{ background: {c["selected"]}; }}
    QPushButton#segment:focus {{ border: 1px solid {c["accent"]}; }}
    QPushButton#link {{ background: transparent; border: none; color: {c["accent"]};
        padding: 0; font-weight: 400; }}
    QPushButton#link:hover {{ text-decoration: underline; }}
    QPushButton#github {{ background: transparent; color: {c["secondary"]}; border: none;
        font-size: 11px; padding: 0; font-weight: 400; }}
    QTableView {{ background: {c["table"]}; color: {c["text"]}; border: none; outline: none; }}
    QTableView[simple="true"] {{ background: {c["background"]}; }}
    QHeaderView {{ background: {c["table"]}; }}
    QHeaderView::section {{ background: {c["table"]}; color: {c["text"]};
        border: none; border-bottom: 1px solid {c["line"]}; padding: 4px 3px;
        font-size: 11px; font-weight: 600; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c["selected"]}; border-radius: 3px;
        min-height: 24px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QProgressBar {{ border: none; border-radius: 2px; background: {c["track"]}; height: 3px; }}
    QProgressBar::chunk {{ background: {c["accent"]}; border-radius: 2px; }}
    QMenu {{ background: {c["table"]}; color: {c["text"]};
        border: 1px solid {c["line"]}; padding: 4px; }}
    QMenu::item {{ padding: 5px 24px 5px 12px; }}
    QMenu::item:selected {{ background: {c["selection"]}; }}
    QToolTip {{ background: {c["table"]}; color: {c["text"]};
        border: 1px solid {c["line"]}; padding: 5px; }}
    """
