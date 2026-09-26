"""裂缝处置业务规则：状态流转、字段校验、排序与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "crack"
REQUIRED_FIELDS = ["处置单号", "所在路段", "裂缝类型"]
STATUS_ORDER = ["待安排", "处置中", "已完成", "已取消"]
CANCELLED_STATUS = "已取消"
ACTION_RULES = {"安排处置": "处置中", "确认完成": "已完成", "取消处置": "已取消"}
NEGATIVE_ACTIONS = []
SORTABLE_FIELDS = ["所在路段", "裂缝类型", "完成日期"]
DEFAULT_SORT = "所在路段"
SORT_ORDERS = ("asc", "desc")


def _text(value: Any) -> str:
    return str(value or "").strip()


class CrackService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        crack_type: str | None = None,
        section: str | None = None,
        status: str | None = None,
        sort: str | None = None,
        order: str | None = "asc",
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        rows = store.rows(MODULE)
        sections = sorted({_text(row.get("所在路段")) for row in rows if _text(row.get("所在路段"))})
        sort_field = self._normalize_sort(sort)
        sort_order = self._normalize_order(order)
        section_filter = _text(section)
        if section_filter and section_filter not in sections:
            raise ValueError(f"所在路段「{section_filter}」不存在，请检查路段名称是否写错")
        status_filter = _text(status)
        if status_filter and status_filter not in STATUS_ORDER:
            raise ValueError(f"处置状态「{status_filter}」不存在，可选：{'、'.join(STATUS_ORDER)}")

        summary = {name: sum(1 for row in rows if row.get("status") == name) for name in STATUS_ORDER}

        matched = rows
        keyword_filter = _text(keyword)
        if keyword_filter:
            matched = [row for row in matched if keyword_filter in str(row.get("处置单号", ""))]
        type_filter = _text(crack_type)
        if type_filter:
            matched = [row for row in matched if type_filter in str(row.get("裂缝类型", ""))]
        if section_filter:
            matched = [row for row in matched if _text(row.get("所在路段")) == section_filter]

        # 取消的处置单单独挑出来，不与已完成等其他状态混在一起。
        cancelled = [row for row in matched if row.get("status") == CANCELLED_STATUS]
        active = [row for row in matched if row.get("status") != CANCELLED_STATUS]
        if status_filter and status_filter != CANCELLED_STATUS:
            active = [row for row in active if row.get("status") == status_filter]
        elif status_filter == CANCELLED_STATUS:
            active = []

        active = self._sort_rows(active, sort_field, sort_order)
        cancelled = self._sort_rows(cancelled, sort_field, sort_order)

        total = len(active)
        pages = max(1, (total + size - 1) // size)
        page = min(max(page, 1), pages)
        start = (page - 1) * size
        return {
            "items": active[start:start + size],
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
            "cancelled": cancelled,
            "cancelled_total": len(cancelled),
            "sections": sections,
            "summary": summary,
            "sort": sort_field,
            "order": sort_order,
        }

    def _normalize_sort(self, sort: str | None) -> str:
        if sort is None:
            return DEFAULT_SORT
        value = _text(sort)
        if not value:
            raise ValueError(f"排序字段不能为空，可选：{'、'.join(SORTABLE_FIELDS)}")
        if value not in SORTABLE_FIELDS:
            raise ValueError(f"排序字段「{value}」不支持，可选：{'、'.join(SORTABLE_FIELDS)}")
        return value

    def _normalize_order(self, order: str | None) -> str:
        value = _text(order).lower() or "asc"
        if value not in SORT_ORDERS:
            raise ValueError(f"排序方向「{order}」不支持，可选：asc、desc")
        return value

    def _sort_rows(self, rows: list[dict[str, Any]], sort_field: str, order: str) -> list[dict[str, Any]]:
        """所在路段永远是第一排序键，保证同一路段的处置单连着排；

        处置单号唯一，作为最终排序键后整条列表是全序，排序方向来回切换位置不丢。
        """

        def key(row: dict[str, Any]) -> tuple[str, ...]:
            number = _text(row.get("处置单号"))
            section = _text(row.get("所在路段"))
            if sort_field == "所在路段":
                return (section, number)
            return (section, _text(row.get(sort_field)), number)

        return sorted(rows, key=key, reverse=(order == "desc"))

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
        entry["处置状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
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
        entry["处置状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"处置单已{action}"
