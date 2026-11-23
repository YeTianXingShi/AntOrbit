<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['notify'])

const sites = ref([])
const channels = ref([])
const loading = ref(false)
const search = ref('')

// Create quick HTML site modal
const showCreate = ref(false)
const createForm = ref({
  slug: '',
  title: '',
  description: '',
  html: '<!DOCTYPE html>\n<html lang="zh-CN">\n<head><meta charset="UTF-8"><title>Hello AntOrbit</title></head>\n<body style="font-family:sans-serif;padding:40px">\n  <h1>Hello from AntOrbit!</h1>\n</body>\n</html>',
  password: '',
  ttl_hours: '',
  allow_submit: false,
  kv_mode: 'off',
  notify_on_submit: false,
  notify_channel: '',
  notify_on_publish: false
})

// Edit site settings modal
const editingSite = ref(null)
const editForm = ref({})

// Inspect submissions & KV drawer
const activeSite = ref(null)
const detailTab = ref('submissions')
const submissions = ref([])
const kvItems = ref([])
const newKvKey = ref('')
const newKvValue = ref('{}')

const filteredSites = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return sites.value
  return sites.value.filter(
    (s) =>
      s.slug.toLowerCase().includes(q) ||
      (s.title || '').toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q)
  )
})

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatTime(iso) {
  if (!iso) return '永久'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [sRes, cRes] = await Promise.all([api.listSites(), api.listChannels()])
    sites.value = sRes.sites || []
    channels.value = cRes.channels || []
  } catch (err) {
    emit('notify', err.message, 'error')
  } finally {
    loading.value = false
  }
}

async function copyUrl(url) {
  try {
    await navigator.clipboard.writeText(url)
    emit('notify', `已复制链接：${url}`)
  } catch {
    emit('notify', url)
  }
}

async function handleCreate() {
  try {
    const payload = {
      slug: createForm.value.slug.trim() || null,
      title: createForm.value.title.trim() || null,
      description: createForm.value.description.trim(),
      html: createForm.value.html,
      password: createForm.value.password || null,
      ttl_hours: createForm.value.ttl_hours === '' ? null : Number(createForm.value.ttl_hours),
      allow_submit: createForm.value.allow_submit,
      kv_mode: createForm.value.kv_mode,
      notify_on_submit: createForm.value.notify_on_submit,
      notify_channel: createForm.value.notify_channel,
      notify_on_publish: createForm.value.notify_on_publish
    }
    const res = await api.publishSiteJson(payload)
    showCreate.value = false
    emit('notify', `站点已发布：${res.site.url}`)
    await loadAll()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

function openEdit(site) {
  editingSite.value = site
  editForm.value = {
    title: site.title,
    description: site.description,
    password: '',
    clear_password: false,
    ttl_hours: '',
    allow_submit: site.allow_submit,
    kv_mode: site.kv_mode,
    notify_on_submit: site.notify_on_submit,
    notify_channel: site.notify_channel || ''
  }
}

async function saveEdit() {
  if (!editingSite.value) return
  try {
    const payload = {
      title: editForm.value.title,
      description: editForm.value.description,
      allow_submit: editForm.value.allow_submit,
      kv_mode: editForm.value.kv_mode,
      notify_on_submit: editForm.value.notify_on_submit,
      notify_channel: editForm.value.notify_channel,
      clear_password: editForm.value.clear_password
    }
    if (editForm.value.password) payload.password = editForm.value.password
    if (editForm.value.ttl_hours !== '') payload.ttl_hours = Number(editForm.value.ttl_hours)

    await api.updateSite(editingSite.value.slug, payload)
    editingSite.value = null
    emit('notify', '站点配置已更新')
    await loadAll()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function handleDelete(site) {
  if (!confirm(`确定永久删除站点「${site.slug}」及其所有表单提交与 KV 数据吗？`)) return
  try {
    await api.deleteSite(site.slug)
    if (activeSite.value?.slug === site.slug) activeSite.value = null
    emit('notify', `已删除站点 ${site.slug}`)
    await loadAll()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function openDetail(site) {
  activeSite.value = site
  detailTab.value = 'submissions'
  await refreshDetail()
}

async function refreshDetail() {
  if (!activeSite.value) return
  try {
    const [subRes, kvRes] = await Promise.all([
      api.listSubmissions(activeSite.value.slug),
      api.listKv(activeSite.value.slug)
    ])
    submissions.value = subRes.submissions || []
    kvItems.value = kvRes.items || []
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function deleteSub(id) {
  if (!activeSite.value) return
  await api.deleteSubmission(activeSite.value.slug, id)
  await refreshDetail()
  await loadAll()
}

async function clearAllSubs() {
  if (!activeSite.value || !confirm('确定清空该站点的全部表单提交记录吗？')) return
  await api.clearSubmissions(activeSite.value.slug)
  await refreshDetail()
  await loadAll()
}

async function saveKv() {
  if (!activeSite.value || !newKvKey.value.trim()) return
  try {
    const parsed = JSON.parse(newKvValue.value)
    await api.setKv(activeSite.value.slug, newKvKey.value.trim(), parsed)
    newKvKey.value = ''
    newKvValue.value = '{}'
    emit('notify', 'KV 已保存')
    await refreshDetail()
    await loadAll()
  } catch (err) {
    emit('notify', `保存失败（请确认 Value 是合法 JSON）：${err.message}`, 'error')
  }
}

async function removeKv(key) {
  if (!activeSite.value) return
  await api.deleteKv(activeSite.value.slug, key)
  await refreshDetail()
  await loadAll()
}

onMounted(loadAll)
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <input
        v-model="search"
        type="text"
        placeholder="搜索 slug / 标题 / 描述..."
        class="w-full max-w-xs rounded-xl border border-slate-800 bg-slate-900 px-3.5 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
      />
      <div class="flex items-center gap-2">
        <button
          class="rounded-xl border border-slate-700 px-3.5 py-2 text-sm text-slate-300 hover:bg-slate-800"
          @click="loadAll"
        >
          刷新
        </button>
        <button
          class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          @click="showCreate = true"
        >
          + 快速发布 HTML
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-12 text-center text-sm text-slate-400">加载站点列表...</div>
    <div
      v-else-if="filteredSites.length === 0"
      class="rounded-2xl border border-dashed border-slate-800 py-16 text-center text-sm text-slate-400"
    >
      暂无托管站点。可以通过反重力客户端的 AntOrbit MCP 工具发布，或点击右上角“快速发布 HTML”。
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <div
        v-for="site in filteredSites"
        :key="site.slug"
        class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 transition hover:border-slate-700"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="truncate text-base font-semibold text-white">{{ site.title }}</h2>
              <span class="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs text-sky-300">
                /s/{{ site.slug }}/
              </span>
            </div>
            <p v-if="site.description" class="mt-1 line-clamp-2 text-xs text-slate-400">
              {{ site.description }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-1.5">
            <a
              :href="site.url"
              target="_blank"
              rel="noopener"
              class="rounded-lg bg-sky-500/15 px-2.5 py-1 text-xs font-medium text-sky-300 hover:bg-sky-500/25"
            >
              打开
            </a>
            <button
              class="rounded-lg bg-slate-800 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-700"
              @click="copyUrl(site.url)"
            >
              复制
            </button>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-1.5 text-xs">
          <span
            v-if="site.has_password"
            class="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-amber-300"
          >
            密码保护
          </span>
          <span
            v-if="site.is_expired"
            class="rounded-full bg-red-500/15 px-2.5 py-0.5 text-red-300"
          >
            已过期
          </span>
          <span
            v-if="site.allow_submit"
            class="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-emerald-300"
          >
            表单提交 ({{ site.submission_count }})
          </span>
          <span
            v-if="site.kv_mode !== 'off'"
            class="rounded-full bg-violet-500/15 px-2.5 py-0.5 text-violet-300"
          >
            KV: {{ site.kv_mode }} ({{ site.kv_count }})
          </span>
          <span
            v-if="site.notify_on_submit"
            class="rounded-full bg-sky-500/15 px-2.5 py-0.5 text-sky-300"
          >
            提交推送{{ site.notify_channel ? `: ${site.notify_channel}` : '' }}
          </span>
        </div>

        <div class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3 text-xs text-slate-400">
          <div class="space-x-3">
            <span>{{ site.file_count }} 文件 · {{ formatBytes(site.size_bytes) }}</span>
            <span>访问 {{ site.view_count }}</span>
            <span>有效期：{{ formatTime(site.expires_at) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <button class="text-sky-400 hover:underline" @click="openDetail(site)">数据/提交</button>
            <button class="text-slate-300 hover:underline" @click="openEdit(site)">设置</button>
            <button class="text-red-400 hover:underline" @click="handleDelete(site)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Panel: Submissions & KV -->
    <div
      v-if="activeSite"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      @click.self="activeSite = null"
    >
      <div class="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
          <div>
            <h3 class="font-semibold text-white">{{ activeSite.title }} · 站点数据</h3>
            <p class="font-mono text-xs text-slate-400">/s/{{ activeSite.slug }}/</p>
          </div>
          <button class="text-slate-400 hover:text-white" @click="activeSite = null">✕</button>
        </div>

        <div class="flex items-center gap-2 border-b border-slate-800 px-6 py-2.5">
          <button
            class="rounded-lg px-3 py-1.5 text-xs font-medium"
            :class="detailTab === 'submissions' ? 'bg-sky-500 text-white' : 'text-slate-300 hover:bg-slate-800'"
            @click="detailTab = 'submissions'"
          >
            表单提交 ({{ submissions.length }})
          </button>
          <button
            class="rounded-lg px-3 py-1.5 text-xs font-medium"
            :class="detailTab === 'kv' ? 'bg-sky-500 text-white' : 'text-slate-300 hover:bg-slate-800'"
            @click="detailTab = 'kv'"
          >
            KV 状态 ({{ kvItems.length }})
          </button>
          <button
            class="ml-auto text-xs text-slate-400 hover:text-white"
            @click="refreshDetail"
          >
            刷新
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-6">
          <div v-if="detailTab === 'submissions'" class="space-y-3">
            <div v-if="submissions.length > 0" class="flex justify-end">
              <button class="text-xs text-red-400 hover:underline" @click="clearAllSubs">
                清空全部提交
              </button>
            </div>
            <div v-if="submissions.length === 0" class="py-10 text-center text-sm text-slate-500">
              暂无提交记录
            </div>
            <div
              v-for="sub in submissions"
              :key="sub.id"
              class="rounded-xl border border-slate-800 bg-slate-950/70 p-4"
            >
              <div class="mb-2 flex items-center justify-between text-xs text-slate-400">
                <span>#{{ sub.id }} · {{ formatTime(sub.created_at) }} · {{ sub.meta?.ip || '-' }}</span>
                <button class="text-red-400 hover:underline" @click="deleteSub(sub.id)">删除</button>
              </div>
              <pre class="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-emerald-300">{{ JSON.stringify(sub.payload, null, 2) }}</pre>
            </div>
          </div>

          <div v-else class="space-y-4">
            <form class="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4 sm:grid-cols-3" @submit.prevent="saveKv">
              <input
                v-model="newKvKey"
                placeholder="Key（如 config）"
                required
                class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-white outline-none focus:border-sky-500"
              />
              <input
                v-model="newKvValue"
                placeholder='JSON Value（如 {"done":true}）'
                required
                class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-xs text-white outline-none focus:border-sky-500"
              />
              <button
                type="submit"
                class="rounded-lg bg-sky-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-400"
              >
                写入 / 更新 KV
              </button>
            </form>

            <div v-if="kvItems.length === 0" class="py-8 text-center text-sm text-slate-500">
              暂无 KV 数据
            </div>
            <div
              v-for="item in kvItems"
              :key="item.key"
              class="rounded-xl border border-slate-800 bg-slate-950/70 p-4"
            >
              <div class="mb-2 flex items-center justify-between text-xs">
                <span class="font-mono font-semibold text-violet-300">{{ item.key }}</span>
                <div class="flex items-center gap-3 text-slate-400">
                  <span>{{ formatTime(item.updated_at) }}</span>
                  <button class="text-red-400 hover:underline" @click="removeKv(item.key)">删除</button>
                </div>
              </div>
              <pre class="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-200">{{ JSON.stringify(item.value, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Create HTML Modal -->
    <div
      v-if="showCreate"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      @click.self="showCreate = false"
    >
      <form
        class="max-h-[90vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
        @submit.prevent="handleCreate"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-white">快速发布单文件 HTML 站点</h3>
          <button type="button" class="text-slate-400 hover:text-white" @click="showCreate = false">✕</button>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs text-slate-400">自定义 Slug（留空随机生成）</label>
            <input
              v-model="createForm.slug"
              placeholder="my-report"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">标题</label>
            <input
              v-model="createForm.title"
              placeholder="站点标题"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">访问密码（可选）</label>
            <input
              v-model="createForm.password"
              type="password"
              placeholder="留空公开访问"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">有效期（小时，留空或 0 为永久）</label>
            <input
              v-model="createForm.ttl_hours"
              type="number"
              min="0"
              step="0.5"
              placeholder="如 24 或 168"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div>
          <label class="mb-1 block text-xs text-slate-400">HTML 内容</label>
          <textarea
            v-model="createForm.html"
            rows="7"
            required
            class="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 font-mono text-xs"
          />
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs text-slate-400">KV 读写模式</label>
            <select
              v-model="createForm.kv_mode"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="off">关闭 (off)</option>
              <option value="read">仅读 (read)</option>
              <option value="readwrite">读写 (readwrite)</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">推送渠道（留空走默认）</label>
            <select
              v-model="createForm.notify_channel"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="">默认渠道</option>
              <option v-for="c in channels" :key="c.id" :value="c.name">
                {{ c.name }} ({{ c.provider }})
              </option>
            </select>
          </div>
        </div>

        <div class="flex flex-wrap gap-5 text-xs text-slate-300">
          <label class="flex items-center gap-2">
            <input v-model="createForm.allow_submit" type="checkbox" /> 允许表单提交
          </label>
          <label class="flex items-center gap-2">
            <input v-model="createForm.notify_on_submit" type="checkbox" /> 收到提交时推送
          </label>
          <label class="flex items-center gap-2">
            <input v-model="createForm.notify_on_publish" type="checkbox" /> 发布后立即推送链接
          </label>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <button
            type="button"
            class="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300"
            @click="showCreate = false"
          >
            取消
          </button>
          <button
            type="submit"
            class="rounded-xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          >
            发布站点
          </button>
        </div>
      </form>
    </div>

    <!-- Edit Site Modal -->
    <div
      v-if="editingSite"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      @click.self="editingSite = null"
    >
      <form
        class="w-full max-w-lg space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
        @submit.prevent="saveEdit"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-white">站点设置 · {{ editingSite.slug }}</h3>
          <button type="button" class="text-slate-400 hover:text-white" @click="editingSite = null">✕</button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-xs text-slate-400">标题</label>
            <input
              v-model="editForm.title"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">描述</label>
            <input
              v-model="editForm.description"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs text-slate-400">设置新密码（留空保持不变）</label>
              <input
                v-model="editForm.password"
                type="password"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">重设有效期（小时，0=永久）</label>
              <input
                v-model="editForm.ttl_hours"
                type="number"
                min="0"
                step="0.5"
                placeholder="留空保持不变"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
          </div>

          <label class="flex items-center gap-2 text-xs text-amber-300">
            <input v-model="editForm.clear_password" type="checkbox" /> 清除现有访问密码（转为公开）
          </label>

          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs text-slate-400">KV 模式</label>
              <select
                v-model="editForm.kv_mode"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              >
                <option value="off">关闭 (off)</option>
                <option value="read">仅读 (read)</option>
                <option value="readwrite">读写 (readwrite)</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">提交推送渠道</label>
              <select
                v-model="editForm.notify_channel"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              >
                <option value="">默认渠道</option>
                <option v-for="c in channels" :key="c.id" :value="c.name">
                  {{ c.name }} ({{ c.provider }})
                </option>
              </select>
            </div>
          </div>

          <div class="flex flex-wrap gap-5 text-xs text-slate-300">
            <label class="flex items-center gap-2">
              <input v-model="editForm.allow_submit" type="checkbox" /> 允许表单提交
            </label>
            <label class="flex items-center gap-2">
              <input v-model="editForm.notify_on_submit" type="checkbox" /> 收到提交时推送
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <button
            type="button"
            class="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300"
            @click="editingSite = null"
          >
            取消
          </button>
          <button
            type="submit"
            class="rounded-xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          >
            保存设置
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
