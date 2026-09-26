"""裂缝处置接口：维护处置单，覆盖安排处置、确认完成、取消处置等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, CrackPageResult, EntryPayload
from app.services.crack import CrackService

router = APIRouter(prefix="/api/crack", tags=["裂缝处置"])

service = CrackService()


@router.get("", response_model=CrackPageResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按处置单号检索"),
    crack_type: str | None = Query(default=None, description="按裂缝类型检索"),
    section: str | None = Query(default=None, description="定位到指定所在路段"),
    status: str | None = Query(default=None, description="待安排、处置中、已完成、已取消"),
    sort: str | None = Query(default=None, description="排序字段：所在路段、裂缝类型、完成日期"),
    order: str = Query(default="asc", description="排序方向：asc 升序、desc 降序"),
    page: int = 1,
    size: int = 20,
) -> CrackPageResult:
    """按路段连着排的裂缝处置列表；取消单单独返回；参数不合法时指明是哪一头。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    try:
        result = service.list_entries(
            keyword=keyword,
            crack_type=crack_type,
            section=section,
            status=status,
            sort=sort,
            order=order,
            page=page,
            size=size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CrackPageResult(**result)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出裂缝处置清单：主列表与取消单合在一起的全量数据。"""
    result = service.list_entries(page=1, size=10000)
    items = result["items"] + result["cancelled"]
    return {"module": "crack", "total": result["total"] + result["cancelled_total"], "items": items}


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
