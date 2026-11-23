async function request(path, options = {}) {
  const opts = {
    credentials: 'same-origin',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {})
    }
  }
  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(opts.body)
  }
  const resp = await fetch(`/api/v1${path}`, opts)
  const text = await resp.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  if (!resp.ok) {
    const msg = (data && data.detail) || `HTTP ${resp.status}`
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    err.status = resp.status
    throw err
  }
  return data
}

export const api = {
  me: () => request('/admin/me'),
  login: (password) => request('/admin/login', { method: 'POST', body: { password } }),
  logout: () => request('/admin/logout', { method: 'POST' }),

  listSites: () => request('/sites'),
  publishSiteJson: (payload) => request('/sites', { method: 'POST', body: payload }),
  updateSite: (slug, payload) => request(`/sites/${encodeURIComponent(slug)}`, { method: 'PATCH', body: payload }),
  deleteSite: (slug) => request(`/sites/${encodeURIComponent(slug)}`, { method: 'DELETE' }),

  listSubmissions: (slug) => request(`/sites/${encodeURIComponent(slug)}/submissions?limit=200`),
  deleteSubmission: (slug, id) => request(`/sites/${encodeURIComponent(slug)}/submissions/${id}`, { method: 'DELETE' }),
  clearSubmissions: (slug) => request(`/sites/${encodeURIComponent(slug)}/submissions`, { method: 'DELETE' }),

  listKv: (slug) => request(`/sites/${encodeURIComponent(slug)}/kv`),
  setKv: (slug, key, value) =>
    request(`/sites/${encodeURIComponent(slug)}/kv/${encodeURIComponent(key)}`, {
      method: 'PUT',
      body: { value }
    }),
  deleteKv: (slug, key) =>
    request(`/sites/${encodeURIComponent(slug)}/kv/${encodeURIComponent(key)}`, { method: 'DELETE' }),

  listChannels: () => request('/channels'),
  createChannel: (payload) => request('/channels', { method: 'POST', body: payload }),
  updateChannel: (id, payload) => request(`/channels/${encodeURIComponent(id)}`, { method: 'PUT', body: payload }),
  deleteChannel: (id) => request(`/channels/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  testChannel: (id) => request(`/channels/${encodeURIComponent(id)}/test`, { method: 'POST' }),
  sendNotification: (payload) => request('/notify', { method: 'POST', body: payload }),
  listLogs: () => request('/notifications/logs?limit=100'),

  listApiKeys: () => request('/api-keys'),
  createApiKey: (name) => request('/api-keys', { method: 'POST', body: { name } }),
  deleteApiKey: (id) => request(`/api-keys/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
