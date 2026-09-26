<template>
  <section class="page" data-module="crack">
    <header class="page-head">
      <div>
        <h2>裂缝处置管理</h2>
        <p class="page-desc">维护处置单，围绕处置单号、所在路段、裂缝类型、裂缝长度做登记、筛选与状态流转；列表按路段连着排，取消单单独列示。</p>
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
      <label class="filter-item">
        <span>处置单号</span>
        <input v-model="filters.keyword" placeholder="按处置单号检索" />
      </label>
      <label class="filter-item">
        <span>裂缝类型</span>
        <input v-model="filters.crackType" placeholder="按裂缝类型检索" />
      </label>
      <label class="filter-item">
        <span>路段定位</span>
        <input v-model="filters.section" list="crack-section-options" placeholder="输入或选择所在路段" />
        <datalist id="crack-section-options">
          <option v-for="section in sections" :key="section" :value="section" />
        </datalist>
      </label>
      <label class="filter-item">
        <span>处置状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
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
            :class="{ sortable: isSortable(column), sorted: sortField === column }"
            @click="isSortable(column) && toggleSort(column)"
          >
            {{ column }}
            <span v-if="isSortable(column)" class="sort-mark">{{ sortMark(column) }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的裂缝处置单，可调整筛选条件或先登记处置单</td>
        </tr>
      </tbody>
    </table>

    <div class="page-bar">
      <button class="btn" type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ pages }} 页 · 本页 {{ rows.length }} 条</span>
      <button class="btn" type="button" :disabled="page >= pages" @click="changePage(page + 1)">下一页</button>
      <label class="page-size">
        每页
        <select v-model.number="size" @change="changeSize">
          <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
        条
      </label>
    </div>

    <section class="cancelled-block">
      <h3>已取消处置单（{{ cancelledTotal }}）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in cancelledRows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
          <tr v-if="!cancelledRows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无已取消的处置单</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>本页 {{ rows.length }} 条 · 共 {{ total }} 条处置单（已取消 {{ cancelledTotal }} 条单独列示）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface CrackPage {
  items: Row[]
  total: number
  page: number
  size: number
  pages: number
  cancelled: Row[]
  cancelled_total: number
  sections: string[]
  summary: Record<string, number>
  sort: string
  order: string
}

const ENDPOINT = '/api/crack'
const columns = ["处置单号", "所在路段", "裂缝类型", "裂缝长度", "灌缝材料", "作业班组", "完成日期", "处置状态"]
const SORTABLE_COLUMNS = ["所在路段", "裂缝类型", "完成日期"]
const actions = ["安排处置", "确认完成", "取消处置"]
const statuses = ["待安排", "处置中", "已完成", "已取消"]
const sizeOptions = [20, 50, 100]

const rows = ref<Row[]>([])
const cancelledRows = ref<Row[]>([])
const total = ref(0)
const cancelledTotal = ref(0)
const page = ref(1)
const pages = ref(1)
const size = ref(20)
const sortField = ref('所在路段')
const sortOrder = ref<'asc' | 'desc'>('asc')
const sections = ref<string[]>([])
const errorMessage = ref('')
const filters = ref({ keyword: '', crackType: '', section: '', status: '' })
const stats = ref([
  { label: '待安排处置', value: 0 },
  { label: '本月处置长度', value: 0 },
  { label: '取消单数', value: 0 },
])

function isSortable(column: string) {
  return SORTABLE_COLUMNS.includes(column)
}

function sortMark(column: string) {
  if (sortField.value !== column) {
    return '⇅'
  }
  return sortOrder.value === 'asc' ? '▲' : '▼'
}

function toggleSort(column: string) {
  if (sortField.value === column) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = column
    sortOrder.value = 'asc'
  }
  // 不重置页码：排序方向切回来之后位置不丢
  void reload()
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = { keyword: '', crackType: '', section: '', status: '' }
  page.value = 1
  void reload()
}

function changePage(target: number) {
  page.value = target
  void reload()
}

function changeSize() {
  page.value = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '处置单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('裂缝处置动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '裂缝处置操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.value.keyword.trim()) {
    params.set('keyword', filters.value.keyword.trim())
  }
  if (filters.value.crackType.trim()) {
    params.set('crack_type', filters.value.crackType.trim())
  }
  if (filters.value.section.trim()) {
    params.set('section', filters.value.section.trim())
  }
  if (filters.value.status) {
    params.set('status', filters.value.status)
  }
  params.set('sort', sortField.value)
  params.set('order', sortOrder.value)
  params.set('page', String(page.value))
  params.set('size', String(size.value))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = payload && typeof payload.detail === 'string' ? payload.detail : '处置单列表读取失败'
      throw new Error(detail)
    }
    const data = payload as CrackPage
    rows.value = data.items ?? []
    total.value = data.total ?? 0
    page.value = data.page ?? 1
    pages.value = data.pages ?? 1
    cancelledRows.value = data.cancelled ?? []
    cancelledTotal.value = data.cancelled_total ?? 0
    sections.value = data.sections ?? []
    stats.value[0].value = data.summary?.['待安排'] ?? 0
    stats.value[2].value = data.summary?.['已取消'] ?? cancelledTotal.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '裂缝处置列表读取失败'
  }
}

onMounted(reload)
</script>
