"""裂缝处置接口：维护处置单，覆盖安排处置、确认完成、取消处置等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.crack import SORTABLE_FIELDS, CrackService

router = APIRouter(prefix="/api/crack", tags=["裂缝处置"])

service = CrackService()

LIST_FIELDS = ["处置单号", "所在路段", "裂缝类型", "裂缝长度", "灌缝材料", "作业班组", "完成日期", "处置状态"]
STATUSES = ["待安排", "处置中", "已完成", "已取消"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按处置单号检索"),
    status: str | None = Query(default=None, description="待安排、处置中、已完成、已取消"),
    section: str | None = Query(default=None, description="按所在路段过滤，名称写错时给出提示"),
    crack_type: str | None = Query(default=None, description="按裂缝类型过滤"),
    sort: str | None = Query(
        default=None, description=f"排序字段：{'、'.join(SORTABLE_FIELDS)}；传空值会报错"
    ),
    order: str = Query(default="asc", description="排序方向：asc 升序、desc 降序"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按处置单号、状态、路段、类型过滤并排序裂缝处置列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    try:
        items, total = service.list_entries(
            keyword=keyword,
            status=status,
            section=section,
            crack_type=crack_type,
            sort=sort,
            order=order,
            page=page,
            size=size,
        )
    except ValueError as exc:
        # 路段写错、排序字段空着或方向不合法时，说明白是哪一头的问题。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def crack_summary() -> dict[str, Any]:
    """统计卡片：待安排数量、本月处置长度、取消单数，口径与列表一致。"""
    return service.summary()


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条处置单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"处置单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条处置单，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="处置单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条处置单执行安排处置、确认完成、取消处置；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出裂缝处置清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "crack", "total": total, "items": items}
