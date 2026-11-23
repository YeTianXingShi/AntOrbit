<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['notify'])
const logs = ref([])
const loading = ref(false)

async function loadLogs() {
  loading.value = true
  try {
    const res = await api.listLogs()
    logs.value = res.logs || []
  } catch (err) {
    emit('notify', err.message, 'error')
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(loadLogs)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-white">最近推送记录（最新 100 条）</h2>
      <button
        class="rounded-xl border border-slate-700 px-3.5 py-2 text-sm text-slate-300 hover:bg-slate-800"
        @click="loadLogs"
      >
        刷新
      </button>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-slate-400">加载日志...</div>
    <div
      v-else-if="logs.length === 0"
      class="rounded-2xl border border-dashed border-slate-800 py-14 text-center text-sm text-slate-400"
    >
      暂无推送日志
    </div>

    <div v-else class="space-y-2.5">
      <div
        v-for="log in logs"
        :key="log.id"
        class="rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-sm"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="rounded-full px-2 py-0.5 text-xs font-medium"
              :class="
                log.status === 'success'
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : 'bg-red-500/15 text-red-300'
              "
            >
              {{ log.status === 'success' ? '成功' : '失败' }}
            </span>
            <span class="font-semibold text-white">{{ log.title }}</span>
            <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
              {{ log.channel_name }} ({{ log.provider }})
            </span>
            <span class="rounded bg-sky-500/10 px-2 py-0.5 text-xs text-sky-300">
              {{ log.trigger_type }}
            </span>
          </div>
          <span class="text-xs text-slate-400">{{ formatTime(log.created_at) }}</span>
        </div>
        <p class="mt-2 text-xs text-slate-300">{{ log.body }}</p>
        <div v-if="log.url" class="mt-1.5 text-xs">
          <a :href="log.url" target="_blank" rel="noopener" class="text-sky-400 hover:underline">
            {{ log.url }}
          </a>
        </div>
        <div v-if="log.error_message" class="mt-2 rounded-lg bg-red-950/60 p-2 font-mono text-xs text-red-300">
          {{ log.error_message }}
        </div>
      </div>
    </div>
  </div>
</template>
