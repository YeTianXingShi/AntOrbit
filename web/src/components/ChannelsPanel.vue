<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['notify'])

const channels = ref([])
const showModal = ref(false)
const editingId = ref(null)

const form = ref({
  name: '',
  provider: 'bark',
  is_default: false,
  enabled: true,
  bark_server_url: 'https://api.day.app',
  bark_device_key: '',
  bark_default_group: 'AntOrbit',
  bark_default_sound: '',
  bark_default_icon: '',
  ntfy_server_url: 'https://ntfy.sh',
  ntfy_topic: '',
  ntfy_token: '',
  ntfy_username: '',
  ntfy_password: '',
  ntfy_default_tags: ''
})

const manualPush = ref({
  title: 'AntOrbit 手动测试通知',
  body: '这是一条来自 AntOrbit 管理后台的推送消息。',
  channel: '',
  url: '',
  level: 'active',
  group: 'AntOrbit'
})

async function loadChannels() {
  try {
    const res = await api.listChannels()
    channels.value = res.channels || []
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

function openCreate() {
  editingId.value = null
  form.value = {
    name: '',
    provider: 'bark',
    is_default: channels.value.length === 0,
    enabled: true,
    bark_server_url: 'https://api.day.app',
    bark_device_key: '',
    bark_default_group: 'AntOrbit',
    bark_default_sound: '',
    bark_default_icon: '',
    ntfy_server_url: 'https://ntfy.sh',
    ntfy_topic: '',
    ntfy_token: '',
    ntfy_username: '',
    ntfy_password: '',
    ntfy_default_tags: ''
  }
  showModal.value = true
}

function openEdit(ch) {
  editingId.value = ch.id
  const cfg = ch.config || {}
  form.value = {
    name: ch.name,
    provider: ch.provider,
    is_default: ch.is_default,
    enabled: ch.enabled,
    bark_server_url: cfg.server_url || 'https://api.day.app',
    bark_device_key: cfg.device_key || '',
    bark_default_group: cfg.default_group || 'AntOrbit',
    bark_default_sound: cfg.default_sound || '',
    bark_default_icon: cfg.default_icon || '',
    ntfy_server_url: cfg.server_url || 'https://ntfy.sh',
    ntfy_topic: cfg.topic || '',
    ntfy_token: cfg.token || '',
    ntfy_username: cfg.username || '',
    ntfy_password: cfg.password || '',
    ntfy_default_tags: cfg.default_tags || ''
  }
  showModal.value = true
}

async function saveChannel() {
  try {
    const config =
      form.value.provider === 'bark'
        ? {
            server_url: form.value.bark_server_url,
            device_key: form.value.bark_device_key,
            default_group: form.value.bark_default_group,
            default_sound: form.value.bark_default_sound,
            default_icon: form.value.bark_default_icon
          }
        : {
            server_url: form.value.ntfy_server_url,
            topic: form.value.ntfy_topic,
            token: form.value.ntfy_token,
            username: form.value.ntfy_username,
            password: form.value.ntfy_password,
            default_tags: form.value.ntfy_default_tags
          }

    const payload = {
      name: form.value.name.trim(),
      provider: form.value.provider,
      config,
      is_default: form.value.is_default,
      enabled: form.value.enabled
    }

    if (editingId.value) {
      await api.updateChannel(editingId.value, payload)
      emit('notify', '渠道已更新')
    } else {
      await api.createChannel(payload)
      emit('notify', '渠道已添加')
    }
    showModal.value = false
    await loadChannels()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function handleTest(ch) {
  try {
    await api.testChannel(ch.id)
    emit('notify', `渠道「${ch.name}」测试推送成功！`)
  } catch (err) {
    emit('notify', `测试失败：${err.message}`, 'error')
  }
}

async function handleDelete(ch) {
  if (!confirm(`确定删除通知渠道「${ch.name}」吗？`)) return
  try {
    await api.deleteChannel(ch.id)
    emit('notify', '渠道已删除')
    await loadChannels()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function sendManual() {
  try {
    await api.sendNotification({
      title: manualPush.value.title,
      body: manualPush.value.body,
      channel: manualPush.value.channel || null,
      url: manualPush.value.url.trim() || null,
      level: manualPush.value.level,
      group: manualPush.value.group.trim() || null
    })
    emit('notify', '手动推送发送成功！')
  } catch (err) {
    emit('notify', `推送失败：${err.message}`, 'error')
  }
}

onMounted(loadChannels)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-semibold text-white">Bark / ntfy 通知渠道</h2>
        <p class="text-xs text-slate-400">配置后，反重力客户端可通过渠道名称（或默认渠道）安全推送，无需暴露密钥。</p>
      </div>
      <button
        class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
        @click="openCreate"
      >
        + 添加渠道
      </button>
    </div>

    <div
      v-if="channels.length === 0"
      class="rounded-2xl border border-dashed border-slate-800 py-12 text-center text-sm text-slate-400"
    >
      尚未配置通知渠道，点击右上角添加 Bark 或 ntfy 渠道。
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <div
        v-for="ch in channels"
        :key="ch.id"
        class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
      >
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base font-semibold text-white">{{ ch.name }}</span>
              <span class="rounded-md bg-sky-500/15 px-2 py-0.5 text-xs uppercase text-sky-300">
                {{ ch.provider }}
              </span>
              <span
                v-if="ch.is_default"
                class="rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300"
              >
                默认
              </span>
              <span
                v-if="!ch.enabled"
                class="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-400"
              >
                已停用
              </span>
            </div>
            <p class="mt-1.5 font-mono text-xs text-slate-400">
              {{ ch.config?.server_url }}
              <span v-if="ch.provider === 'ntfy'">/{{ ch.config?.topic }}</span>
            </p>
          </div>
          <div class="flex items-center gap-2 text-xs">
            <button
              class="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-emerald-300 hover:bg-emerald-500/25"
              @click="handleTest(ch)"
            >
              测试
            </button>
            <button class="text-slate-300 hover:underline" @click="openEdit(ch)">编辑</button>
            <button class="text-red-400 hover:underline" @click="handleDelete(ch)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Manual Push Tester -->
    <form
      class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5"
      @submit.prevent="sendManual"
    >
      <h3 class="text-sm font-semibold text-white">手动发送测试推送</h3>
      <div class="grid gap-3 sm:grid-cols-3">
        <input
          v-model="manualPush.title"
          required
          placeholder="推送标题"
          class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        />
        <select
          v-model="manualPush.channel"
          class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        >
          <option value="">默认渠道</option>
          <option v-for="c in channels" :key="c.id" :value="c.name">{{ c.name }} ({{ c.provider }})</option>
        </select>
        <select
          v-model="manualPush.level"
          class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        >
          <option value="passive">低优先级 (passive)</option>
          <option value="active">普通 (active)</option>
          <option value="timeSensitive">时效性 (timeSensitive)</option>
          <option value="critical">紧急 (critical)</option>
        </select>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <input
          v-model="manualPush.body"
          required
          placeholder="消息内容"
          class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        />
        <input
          v-model="manualPush.url"
          placeholder="点击跳转 URL（可选，如 https://...）"
          class="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
        />
      </div>
      <div class="flex justify-end">
        <button
          type="submit"
          class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
        >
          立即推送
        </button>
      </div>
    </form>

    <!-- Channel Modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      @click.self="showModal = false"
    >
      <form
        class="w-full max-w-lg space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
        @submit.prevent="saveChannel"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-white">{{ editingId ? '编辑通知渠道' : '添加通知渠道' }}</h3>
          <button type="button" class="text-slate-400 hover:text-white" @click="showModal = false">✕</button>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs text-slate-400">渠道名称（唯一标识）</label>
            <input
              v-model="form.name"
              required
              placeholder="如 iphone / work"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">推送类型</label>
            <select
              v-model="form.provider"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="bark">Bark (iOS)</option>
              <option value="ntfy">ntfy</option>
            </select>
          </div>
        </div>

        <div v-if="form.provider === 'bark'" class="space-y-3">
          <div>
            <label class="mb-1 block text-xs text-slate-400">Bark 服务器地址</label>
            <input
              v-model="form.bark_server_url"
              required
              placeholder="https://api.day.app"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">Device Key</label>
            <input
              v-model="form.bark_device_key"
              required
              placeholder="你的 Bark Device Key"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs text-slate-400">默认分组</label>
              <input
                v-model="form.bark_default_group"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">默认铃声（可选）</label>
              <input
                v-model="form.bark_default_sound"
                placeholder="如 minuet"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
          </div>
        </div>

        <div v-else class="space-y-3">
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs text-slate-400">ntfy 服务器地址</label>
              <input
                v-model="form.ntfy_server_url"
                required
                placeholder="https://ntfy.sh"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">Topic 主题名</label>
              <input
                v-model="form.ntfy_topic"
                required
                placeholder="my-antorbit-topic"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm"
              />
            </div>
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-400">Access Token（可选，优先于账密）</label>
            <input
              v-model="form.ntfy_token"
              type="password"
              placeholder="tk_..."
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs text-slate-400">用户名（可选）</label>
              <input
                v-model="form.ntfy_username"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">密码（可选）</label>
              <input
                v-model="form.ntfy_password"
                type="password"
                class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              />
            </div>
          </div>
        </div>

        <div class="flex gap-5 text-xs text-slate-300">
          <label class="flex items-center gap-2">
            <input v-model="form.is_default" type="checkbox" /> 设为默认渠道
          </label>
          <label class="flex items-center gap-2">
            <input v-model="form.enabled" type="checkbox" /> 启用该渠道
          </label>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <button
            type="button"
            class="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300"
            @click="showModal = false"
          >
            取消
          </button>
          <button
            type="submit"
            class="rounded-xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          >
            保存渠道
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
