<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps({
  publicUrl: { type: String, default: '' }
})
const emit = defineEmits(['notify'])

const keys = ref([])
const newKeyName = ref('')
const createdKey = ref('')

const mcpSnippet = computed(() => {
  const url = props.publicUrl || window.location.origin
  const token = createdKey.value || '<YOUR_ANTORBIT_API_KEY>'
  return JSON.stringify(
    {
      mcpServers: {
        antorbit: {
          command: 'uvx',
          args: [
            '--from',
            'git+https://github.com/YeTianXingShi/AntOrbit.git#subdirectory=mcp',
            'antorbit-mcp'
          ],
          env: {
            ANTORBIT_URL: url,
            ANTORBIT_API_KEY: token
          }
        }
      }
    },
    null,
    2
  )
})

async function loadKeys() {
  try {
    const res = await api.listApiKeys()
    keys.value = res.api_keys || []
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function handleCreate() {
  if (!newKeyName.value.trim()) return
  try {
    const res = await api.createApiKey(newKeyName.value.trim())
    createdKey.value = res.raw_key
    newKeyName.value = ''
    emit('notify', 'API Key 已生成，请立即复制保存！')
    await loadKeys()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function handleDelete(item) {
  if (!confirm(`确定吊销密钥「${item.name}」吗？使用该密钥的客户端将无法访问。`)) return
  try {
    await api.deleteApiKey(item.id)
    emit('notify', '密钥已吊销')
    await loadKeys()
  } catch (err) {
    emit('notify', err.message, 'error')
  }
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text)
    emit('notify', `已复制${label}`)
  } catch {
    emit('notify', '复制失败，请手动选中复制', 'error')
  }
}

onMounted(loadKeys)
</script>

<template>
  <div class="space-y-6">
    <form
      class="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
      @submit.prevent="handleCreate"
    >
      <input
        v-model="newKeyName"
        required
        placeholder="新 API Key 备注（如 macbook-antigravity）"
        class="flex-1 min-w-[220px] rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm"
      />
      <button
        type="submit"
        class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
      >
        生成新 API Key
      </button>
    </form>

    <div
      v-if="createdKey"
      class="space-y-3 rounded-2xl border border-emerald-500/40 bg-emerald-950/30 p-5"
    >
      <div class="flex items-center justify-between">
        <span class="text-sm font-semibold text-emerald-300">新密钥已生成（仅展示一次，请立即保存）</span>
        <button
          class="rounded-lg bg-emerald-500/20 px-3 py-1 text-xs text-emerald-200 hover:bg-emerald-500/30"
          @click="copyText(createdKey, ' API Key')"
        >
          复制密钥
        </button>
      </div>
      <div class="break-all rounded-xl bg-slate-950 p-3 font-mono text-xs text-emerald-200">
        {{ createdKey }}
      </div>
    </div>

    <div class="space-y-2.5">
      <h3 class="text-sm font-semibold text-white">现有 API Keys</h3>
      <div
        v-if="keys.length === 0"
        class="rounded-xl border border-dashed border-slate-800 py-8 text-center text-sm text-slate-400"
      >
        暂无 API Key，请先生成一个用于反重力客户端配置。
      </div>
      <div
        v-for="item in keys"
        :key="item.id"
        class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm"
      >
        <div>
          <div class="flex items-center gap-2">
            <span class="font-medium text-white">{{ item.name }}</span>
            <span class="font-mono text-xs text-slate-400">{{ item.key_prefix }}</span>
            <span
              v-if="item.is_env"
              class="rounded bg-sky-500/15 px-2 py-0.5 text-xs text-sky-300"
            >
              ENV
            </span>
          </div>
          <p class="mt-0.5 text-xs text-slate-400">
            创建于 {{ new Date(item.created_at).toLocaleString() }}
            <span v-if="item.last_used_at">
              · 最近使用 {{ new Date(item.last_used_at).toLocaleString() }}
            </span>
          </p>
        </div>
        <button
          v-if="!item.is_env"
          class="text-xs text-red-400 hover:underline"
          @click="handleDelete(item)"
        >
          吊销
        </button>
      </div>
    </div>

    <!-- Ready-to-paste mcp_config.json -->
    <div class="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-white">反重力插件 mcp_config.json 配置参考</h3>
        <button
          class="rounded-lg bg-slate-800 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700"
          @click="copyText(mcpSnippet, ' mcp_config.json')"
        >
          复制配置
        </button>
      </div>
      <pre class="overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-xs text-sky-200">{{ mcpSnippet }}</pre>
    </div>
  </div>
</template>
