"""裂缝处置业务规则：状态流转、字段校验、排序与筛选口径都收在这里。

列表顺序固定为「有效单 + 已取消单」两段：正常状态的处置单按所在路段聚在一起，
已取消的处置单单独成段排在最后，不与已完成等状态混排；字段值与 id 组成确定的
排序键，排序方向来回切换后每一条的位置都能复原。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "crack"
REQUIRED_FIELDS = ["处置单号", "所在路段", "裂缝类型"]
STATUS_ORDER = ["待安排", "处置中", "已完成", "已取消"]
ACTION_RULES = {"安排处置": "处置中", "确认完成": "已完成", "取消处置": "已取消"}
NEGATIVE_ACTIONS = []

SORTABLE_FIELDS = ["所在路段", "裂缝类型", "完成日期"]
SORT_ORDERS = ["asc", "desc"]
CANCELLED_STATUS = "已取消"


class CrackService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        section: str | None = None,
        crack_type: str | None = None,
        sort: str | None = None,
        order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        # 路段名称按全量数据先校验：名称写错时直接报是哪一头不合法，
        # 而不是静默给个空列表让人猜。
        if section:
            if not any(section in str(row.get("所在路段", "")) for row in rows):
                raise ValueError(f"所在路段「{section}」不存在，请核对路段名称是否写错")
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("处置单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if section:
            rows = [row for row in rows if section in str(row.get("所在路段", ""))]
        if crack_type:
            rows = [row for row in rows if crack_type in str(row.get("裂缝类型", ""))]
        if sort is not None:
            rows = self._sort_entries(rows, sort=sort, order=order)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def _sort_entries(
        self, rows: list[dict[str, Any]], *, sort: str, order: str
    ) -> list[dict[str, Any]]:
        field = str(sort).strip()
        if not field:
            raise ValueError(f"排序字段不能为空，可选：{'、'.join(SORTABLE_FIELDS)}")
        if field not in SORTABLE_FIELDS:
            raise ValueError(
                f"排序字段「{field}」不支持，可选：{'、'.join(SORTABLE_FIELDS)}"
            )
        direction = str(order or "").strip().lower()
        if direction not in SORT_ORDERS:
            raise ValueError(f"排序方向「{order}」不支持，可选：asc、desc")
        reverse = direction == "desc"

        # 排序键：所在路段恒为第一键，保证同一路段的处置单始终连着排；
        # id 兜底让同路段同字段值的记录也有确定顺序，方向切回来位置不丢。
        def sort_key(row: dict[str, Any]) -> tuple[str, str, int]:
            return (
                str(row.get("所在路段") or ""),
                str(row.get(field) or ""),
                int(row.get("id", 0)),
            )

        active = [row for row in rows if row.get("status") != CANCELLED_STATUS]
        cancelled = [row for row in rows if row.get("status") == CANCELLED_STATUS]
        active.sort(key=sort_key, reverse=reverse)
        cancelled.sort(key=sort_key, reverse=reverse)
        # 已取消单单独成段垫在最后，排序方向切换也不把它们混回已完成里。
        return active + cancelled

    def summary(self) -> dict[str, Any]:
        """顶部统计卡片：口径与列表保持一致，取消单数与列表中的已取消单对得上。"""
        rows = store.rows(MODULE)
        month_prefix = date.today().strftime("%Y-%m")
        month_length = 0.0
        for row in rows:
            if row.get("status") != "已完成":
                continue
            finished_on = str(row.get("完成日期") or "")
            if not finished_on.startswith(month_prefix):
                continue
            try:
                month_length += float(row.get("裂缝长度") or 0)
            except (TypeError, ValueError):
                continue
        return {
            "待安排处置": sum(1 for row in rows if row.get("status") == "待安排"),
            "本月处置长度": round(month_length, 1),
            "取消单数": sum(1 for row in rows if row.get("status") == CANCELLED_STATUS),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["处置状态"] = entry["status"]
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"处置单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于裂缝处置可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["处置状态"] = target
        return entry, f"处置单已{action}"
