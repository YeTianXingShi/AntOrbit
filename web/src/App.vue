<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'
import SitesPanel from './components/SitesPanel.vue'
import ChannelsPanel from './components/ChannelsPanel.vue'
import LogsPanel from './components/LogsPanel.vue'
import ApiKeysPanel from './components/ApiKeysPanel.vue'

const loading = ref(true)
const authenticated = ref(false)
const serverInfo = ref({ version: '0.1.0', public_url: '', default_password_warning: false })
const password = ref('')
const loginError = ref('')
const activeTab = ref('sites')
const toast = ref({ show: false, text: '', type: 'info' })

function notify(text, type = 'info') {
  toast.value = { show: true, text, type }
  setTimeout(() => {
    if (toast.value.text === text) {
      toast.value.show = false
    }
  }, 3500)
}

async function checkAuth() {
  loading.value = true
  try {
    const info = await api.me()
    serverInfo.value = info
    authenticated.value = Boolean(info.authenticated)
  } catch (err) {
    notify(err.message || '连接服务端失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handleLogin() {
  loginError.value = ''
  try {
    await api.login(password.value)
    password.value = ''
    await checkAuth()
  } catch (err) {
    loginError.value = err.message || '登录失败'
  }
}

async function handleLogout() {
  await api.logout()
  authenticated.value = false
}

onMounted(checkAuth)
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-100">
    <!-- Toast -->
    <div
      v-if="toast.show"
      class="fixed right-5 top-5 z-50 rounded-xl border px-4 py-2.5 text-sm shadow-xl backdrop-blur"
      :class="
        toast.type === 'error'
          ? 'border-red-500/40 bg-red-950/90 text-red-200'
          : 'border-sky-500/40 bg-slate-900/95 text-sky-200'
      "
    >
      {{ toast.text }}
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex min-h-screen items-center justify-center text-slate-400">
      正在连接 AntOrbit 服务端...
    </div>

    <!-- Login -->
    <div v-else-if="!authenticated" class="flex min-h-screen items-center justify-center px-4">
      <div class="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/90 p-7 shadow-2xl">
        <div class="mb-5 flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400 font-bold">
            AO
          </div>
          <div>
            <h1 class="text-lg font-semibold tracking-tight">AntOrbit 管理后台</h1>
            <p class="text-xs text-slate-400">v{{ serverInfo.version }}</p>
          </div>
        </div>

        <div
          v-if="serverInfo.default_password_warning"
          class="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200"
        >
          当前仍在使用默认管理员密码 <code>antorbit</code>，请在环境变量中设置强密码 <code>ANTORBIT_ADMIN_PASSWORD</code>。
        </div>

        <div
          v-if="loginError"
          class="mb-4 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300"
        >
          {{ loginError }}
        </div>

        <form class="space-y-4" @submit.prevent="handleLogin">
          <div>
            <label class="mb-1.5 block text-xs font-medium text-slate-300">管理员密码</label>
            <input
              v-model="password"
              type="password"
              required
              autofocus
              placeholder="输入 ANTORBIT_ADMIN_PASSWORD"
              class="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-slate-100 outline-none focus:border-sky-500"
            />
          </div>
          <button
            type="submit"
            class="w-full rounded-xl bg-sky-500 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-400"
          >
            登录后台
          </button>
        </form>
      </div>
    </div>

    <!-- Main Console -->
    <div v-else class="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400 font-bold">
            AO
          </div>
          <div>
            <h1 class="text-xl font-bold tracking-tight">AntOrbit</h1>
            <p class="text-xs text-slate-400">
              在线站点托管 &amp; 通知推送中心 · v{{ serverInfo.version }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-for="tab in [
              { id: 'sites', label: '站点管理' },
              { id: 'channels', label: '通知渠道' },
              { id: 'logs', label: '推送日志' },
              { id: 'keys', label: 'API 密钥' }
            ]"
            :key="tab.id"
            class="rounded-xl px-3.5 py-2 text-sm font-medium transition"
            :class="
              activeTab === tab.id
                ? 'bg-sky-500 text-white shadow'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            "
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
          <button
            class="ml-2 rounded-xl border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
            @click="handleLogout"
          >
            退出
          </button>
        </div>
      </header>

      <div
        v-if="serverInfo.default_password_warning"
        class="mb-5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200"
      >
        安全提醒：当前管理员密码仍为默认值 <code>antorbit</code>，建议尽快通过环境变量 <code>ANTORBIT_ADMIN_PASSWORD</code> 修改。
      </div>

      <SitesPanel v-if="activeTab === 'sites'" :public-url="serverInfo.public_url" @notify="notify" />
      <ChannelsPanel v-else-if="activeTab === 'channels'" @notify="notify" />
      <LogsPanel v-else-if="activeTab === 'logs'" @notify="notify" />
      <ApiKeysPanel v-else-if="activeTab === 'keys'" :public-url="serverInfo.public_url" @notify="notify" />
    </div>
  </div>
</template>
