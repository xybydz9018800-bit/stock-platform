"""
操盘平台 - 工具函数
"""
import json
from datetime import datetime, date


def safe_float(v, default=0.0):
    """安全转换为float"""
    try:
        return float(v) if v else default
    except (ValueError, TypeError):
        return default


def format_money(amount, unit="亿"):
    """格式化金额"""
    if unit == "亿":
        return f"{amount:.2f}亿"
    elif unit == "万":
        return f"{amount:.0f}万"
    else:
        return f"{amount:.2f}"


def format_pct(pct: float) -> str:
    """格式化百分比"""
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def color_for_change(change: float) -> str:
    """中国股市：涨红跌绿"""
    return "#FF0000" if change >= 0 else "#00AA00"


def get_today_str() -> str:
    """获取今日日期字符串"""
    return date.today().isoformat()


def json_dumps(obj, **kwargs):
    """安全的JSON序列化"""
    return json.dumps(obj, ensure_ascii=False, default=str, **kwargs)
