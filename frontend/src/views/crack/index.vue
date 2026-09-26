<template>
  <section class="page" data-module="crack">
    <header class="page-head">
      <div>
        <h2>裂缝处置管理</h2>
        <p class="page-desc">维护处置单，围绕处置单号、所在路段、裂缝类型、裂缝长度做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记处置单</button>
        <button class="btn" type="button" @click="exportRows">导出裂缝处置清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>处置状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: sortableFields.includes(column) }"
            @click="toggleSort(column)"
          >
            {{ column }}
            <span v-if="sortableFields.includes(column)" class="sort-icon">{{ sortIcon(column) }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          :class="{ 'row-cancelled': row.status === '已取消' }"
        >
          <td v-for="column in columns" :key="column">
            <span
              v-if="column === '处置状态'"
              class="status-tag"
              :class="{ cancelled: row.status === '已取消' }"
            >{{ displayText(row[column]) }}</span>
            <template v-else>{{ displayText(row[column]) }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条裂缝处置记录，当前第 {{ page }} / {{ pageCount }} 页，本页 {{ rows.length }} 条</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span class="pager">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <button class="btn ghost" type="button" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
      </span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/crack'
const columns = ["处置单号", "所在路段", "裂缝类型", "裂缝长度", "灌缝材料", "作业班组", "完成日期", "处置状态"]
const sortableFields = ["所在路段", "裂缝类型", "完成日期"]
const actions = ["安排处置", "确认完成", "取消处置"]
const statuses = ["待安排", "处置中", "已完成", "已取消"]
const PAGE_SIZE = 20

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const sortField = ref('')
const sortOrder = ref<'asc' | 'desc'>('asc')
const stats = ref([
  { label: '待安排处置', value: 0 },
  { label: '本月处置长度（米）', value: 0 },
  { label: '取消单数', value: 0 },
])

const filterFields = columns.slice(0, 3)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasActiveFilter = computed(() =>
  Boolean(statusFilter.value) || Object.values(filters.value).some((value) => value.trim() !== ''),
)
const emptyText = computed(() =>
  hasActiveFilter.value
    ? '当前筛选条件下没有匹配的裂缝处置单，可调整条件后再查'
    : '暂无裂缝处置数据，可先登记处置单',
)

function displayText(value: string | number | null | undefined) {
  return value === '' || value === null || value === undefined ? '—' : value
}

function sortIcon(column: string) {
  if (sortField.value !== column) {
    return '↕'
  }
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

function toggleSort(column: string) {
  if (!sortableFields.includes(column)) {
    return
  }
  if (sortField.value === column) {
    // 升序点一下变降序，再点回来；后端按 id 兜底，位置可以完整复原
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = column
    sortOrder.value = 'asc'
  }
  page.value = 1
  void reload()
}

function goPage(target: number) {
  if (target < 1 || target > pageCount.value || target === page.value) {
    return
  }
  page.value = target
  void reload()
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  sortField.value = ''
  sortOrder.value = 'asc'
  page.value = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '处置单登记入口尚未接入审批流'
}

function buildQuery() {
  const params = new URLSearchParams()
  if (filters.value['处置单号']?.trim()) {
    params.set('keyword', filters.value['处置单号'].trim())
  }
  if (filters.value['所在路段']?.trim()) {
    params.set('section', filters.value['所在路段'].trim())
  }
  if (filters.value['裂缝类型']?.trim()) {
    params.set('crack_type', filters.value['裂缝类型'].trim())
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  if (sortField.value) {
    params.set('sort', sortField.value)
    params.set('order', sortOrder.value)
  }
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  return params.toString()
}

async function errorDetail(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null)
  return typeof payload?.detail === 'string' ? payload.detail : fallback
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(typeof payload?.detail === 'string' ? payload.detail : '裂缝处置动作未生效，请稍后重试')
    }
    if (payload?.ok === false) {
      throw new Error(typeof payload?.message === 'string' ? payload.message : '裂缝处置动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadSummary()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '裂缝处置操作失败'
  }
}

async function loadSummary() {
  try {
    const response = await request(`${ENDPOINT}/summary`)
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as Record<string, number>
    stats.value[0].value = Number(payload['待安排处置'] ?? 0)
    stats.value[1].value = Number(payload['本月处置长度'] ?? 0)
    stats.value[2].value = Number(payload['取消单数'] ?? 0)
  } catch {
    // 统计卡片拉取失败不影响列表本身
  }
}

async function reload(redirected = false) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error(await errorDetail(response, '处置单列表读取失败'))
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 筛选后当前页可能超出范围（如最后一条被取消），回到末页保持数字对得上
    if (!redirected && page.value > pageCount.value) {
      page.value = pageCount.value
      await reload(true)
    }
  } catch (error) {
    // 报错时清空旧数据，避免页面数字与合计对不上
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '裂缝处置列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadSummary()
})
</script>
