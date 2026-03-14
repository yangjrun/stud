"""数据导出 API routes (CSV / Markdown / PDF)。"""

import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.data.database import get_session
from src.data.repository import (
    DragonTigerRepository,
    DragonTigerSeatRepository,
    EmotionRepository,
    LimitUpRepository,
    RecapRepository,
)

router = APIRouter()


# ─── CSV Export ───


@router.get("/limit-up/csv")
def export_limit_up_csv(
    date_str: Optional[str] = Query(None, alias="date", description="日期 YYYY-MM-DD"),
):
    """导出涨停列表为 CSV。"""
    trade_date = _parse_date(date_str)
    with get_session() as s:
        repo = LimitUpRepository(s)
        records = repo.get_by_date(trade_date)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "日期", "代码", "名称", "涨幅%", "收盘价", "成交额",
            "封单金额", "首封时间", "末封时间", "炸板次数", "连板数", "题材",
        ])
        for r in records:
            writer.writerow([
                str(r.trade_date), r.code, r.name, r.change_pct,
                r.close_price, r.amount, r.seal_amount,
                r.first_seal_time, r.last_seal_time,
                r.open_count, r.continuous_count, r.concept,
            ])

        buf.seek(0)
        filename = f"limit_up_{trade_date}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/emotion/csv")
def export_emotion_csv(
    days: int = Query(60, ge=1, le=500, description="导出天数"),
):
    """导出情绪历史数据为 CSV。"""
    end = date.today()
    start = end - timedelta(days=days * 2)
    with get_session() as s:
        repo = EmotionRepository(s)
        records = list(repo.get_range(start, end))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "日期", "涨停数", "涨停数(真)", "跌停数", "炸板数",
            "封板成功率", "涨跌比", "最高连板", "最高连板股",
            "昨涨停溢价%", "总成交额", "情绪阶段", "情绪评分",
        ])
        for r in records:
            writer.writerow([
                str(r.trade_date), r.limit_up_count, r.limit_up_count_real,
                r.limit_down_count, r.burst_count, r.seal_success_rate,
                r.advance_decline_ratio, r.max_continuous,
                r.max_continuous_name, r.yesterday_premium_avg,
                r.total_amount, r.emotion_phase, r.emotion_score,
            ])

        buf.seek(0)
        filename = f"emotion_{end}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/dragon-tiger/csv")
def export_dragon_tiger_csv(
    date_str: Optional[str] = Query(None, alias="date", description="日期 YYYY-MM-DD"),
):
    """导出龙虎榜为 CSV。"""
    trade_date = _parse_date(date_str)
    with get_session() as s:
        dt_repo = DragonTigerRepository(s)
        seat_repo = DragonTigerSeatRepository(s)
        dragons = dt_repo.get_by_date(trade_date)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "日期", "代码", "名称", "涨幅%", "上榜原因",
            "方向", "排名", "席位", "买入额", "卖出额", "净额", "知名游资",
        ])
        for dt in dragons:
            seats = seat_repo.get_seats_for_stock(trade_date, dt.code)
            if not seats:
                writer.writerow([
                    str(dt.trade_date), dt.code, dt.name,
                    dt.change_pct, dt.reason,
                    "", "", "", "", "", "", "",
                ])
            for seat in seats:
                writer.writerow([
                    str(dt.trade_date), dt.code, dt.name,
                    dt.change_pct, dt.reason,
                    seat.direction, seat.rank, seat.seat_name,
                    seat.buy_amount, seat.sell_amount, seat.net_amount,
                    seat.player_name or "",
                ])

        buf.seek(0)
        filename = f"dragon_tiger_{trade_date}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


# ─── Markdown Export ───


@router.get("/recap/markdown")
def export_recap_markdown(
    date_str: Optional[str] = Query(None, alias="date", description="日期 YYYY-MM-DD"),
):
    """导出复盘报告为 Markdown。"""
    trade_date = _parse_date(date_str)
    with get_session() as s:
        repo = RecapRepository(s)
        recap = repo.get_by_date(trade_date)
        if not recap:
            return {"error": "暂无复盘数据"}

        md = _recap_to_markdown(recap)
        filename = f"recap_{trade_date}.md"
        return StreamingResponse(
            iter([md]),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


# ─── PDF Export ───


@router.get("/recap/pdf")
def export_recap_pdf(
    date_str: Optional[str] = Query(None, alias="date", description="日期 YYYY-MM-DD"),
):
    """导出复盘报告为 PDF。"""
    trade_date = _parse_date(date_str)
    with get_session() as s:
        repo = RecapRepository(s)
        recap = repo.get_by_date(trade_date)
        if not recap:
            return {"error": "暂无复盘数据"}

        pdf_bytes = _recap_to_pdf(recap)
        filename = f"recap_{trade_date}.pdf"
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


# ─── Private helpers ───


def _parse_date(date_str: Optional[str]) -> date:
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    return date.today()


def _recap_to_markdown(recap) -> str:
    lines = [
        f"# {recap.trade_date} 复盘报告\n",
    ]
    if recap.emotion_summary:
        lines.append(f"## 情绪总结\n\n{recap.emotion_summary}\n")
    if recap.theme_summary:
        lines.append(f"## 题材总结\n\n{recap.theme_summary}\n")
    if recap.dragon_tiger_summary:
        lines.append(f"## 龙虎榜总结\n\n{recap.dragon_tiger_summary}\n")
    if recap.tomorrow_strategy:
        lines.append(f"## 明日策略\n\n{recap.tomorrow_strategy}\n")
    if recap.user_notes:
        lines.append(f"## 个人笔记\n\n{recap.user_notes}\n")
    return "\n".join(lines)


def _recap_to_pdf(recap) -> bytes:
    """生成简易 PDF (纯文本, 无外部依赖)。

    使用内置的简单 PDF 生成, 避免引入 reportlab 等重依赖。
    对中文支持有限, 后续可替换为 reportlab + 中文字体。
    """
    md = _recap_to_markdown(recap)
    # 简易 PDF: 将 Markdown 文本包装为最小 PDF
    return _text_to_simple_pdf(f"{recap.trade_date} 复盘报告", md)


def _text_to_simple_pdf(title: str, text: str) -> bytes:
    """生成最小可用 PDF (ASCII + 基础中文, 无外部依赖)。

    这是一个极简实现: 将文本按行写入 PDF stream。
    若需更好的排版和完整中文支持, 可 pip install reportlab 后替换此函数。
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4

        # 尝试注册中文字体
        _register_chinese_font()
        font_name = "ChineseFont" if "ChineseFont" in pdfmetrics.getRegisteredFontNames() else "Helvetica"

        c.setFont(font_name, 16)
        c.drawString(50, height - 50, title)

        c.setFont(font_name, 10)
        y = height - 80
        for line in text.split("\n"):
            line = line.replace("#", "").strip()
            if not line:
                y -= 12
                continue
            # 自动换行 (每行约 70 个字符)
            while len(line) > 70:
                c.drawString(50, y, line[:70])
                line = line[70:]
                y -= 14
                if y < 50:
                    c.showPage()
                    c.setFont(font_name, 10)
                    y = height - 50
            c.drawString(50, y, line)
            y -= 14
            if y < 50:
                c.showPage()
                c.setFont(font_name, 10)
                y = height - 50

        c.save()
        return buf.getvalue()
    except ImportError:
        # reportlab 未安装, 回退到纯文本 PDF
        return _minimal_text_pdf(text)


def _register_chinese_font():
    """尝试注册系统中文字体 (Windows 优先)。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "ChineseFont" in pdfmetrics.getRegisteredFontNames():
        return

    import os
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑
        r"C:\Windows\Fonts\simsun.ttc",  # 宋体
        r"C:\Windows\Fonts\simhei.ttf",  # 黑体
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("ChineseFont", path))
            return


def _minimal_text_pdf(text: str) -> bytes:
    """不依赖任何库的最小 PDF 生成 (仅 ASCII)。"""
    # 过滤非 ASCII 字符并标注
    ascii_text = text.encode("ascii", errors="replace").decode("ascii")
    lines = ascii_text.split("\n")

    objects = []
    # obj 1: catalog
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    # obj 2: pages
    objects.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj")
    # obj 3: page
    objects.append(
        "3 0 obj\n<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>\nendobj"
    )
    # obj 5: font
    objects.append(
        "5 0 obj\n<< /Type /Font /Subtype /Type1 "
        "/BaseFont /Courier >>\nendobj"
    )
    # obj 4: content stream
    content_lines = ["BT", "/F1 9 Tf", "50 800 Td"]
    for line in lines[:80]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({safe}) Tj")
        content_lines.append("0 -12 Td")
    content_lines.append("ET")
    stream_body = "\n".join(content_lines)
    objects.append(
        f"4 0 obj\n<< /Length {len(stream_body)} >>\n"
        f"stream\n{stream_body}\nendstream\nendobj"
    )

    body = "%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(body))
        body += obj + "\n"
    xref_pos = len(body)
    body += f"xref\n0 {len(objects) + 1}\n"
    body += "0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n"
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    body += f"startxref\n{xref_pos}\n%%EOF"

    return body.encode("ascii")
