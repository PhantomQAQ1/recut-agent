<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, KeyRound, LoaderCircle, LogOut } from 'lucide-vue-next'
import { api } from '../api/client'
import { useAuth } from '../composables/useAuth'

const { user, logout } = useAuth()

const menuOpen = ref(false)
const passwordOpen = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const currentPassword = ref('')
const newPassword = ref('')

const initials = computed(() => {
  const name = (user.value?.display_name ?? '').trim()
  return name.slice(0, 1).toUpperCase() || '?'
})

function closePassword() {
  passwordOpen.value = false
  currentPassword.value = ''
  newPassword.value = ''
  error.value = ''
}

async function submitPassword() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/api/v1/auth/password', {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    closePassword()
    notice.value = '密码已更新，其他设备已下线'
    window.setTimeout(() => (notice.value = ''), 2600)
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : '修改失败'
  } finally {
    busy.value = false
  }
}

async function signOut() {
  menuOpen.value = false
  await logout()
}
</script>

<template>
  <div class="user-menu">
    <button class="user-chip" type="button" @click="menuOpen = !menuOpen">
      <span class="avatar">{{ initials }}</span>
      <span class="user-name">{{ user?.display_name }}</span>
      <ChevronDown :size="13" />
    </button>

    <div v-if="menuOpen" class="user-dropdown">
      <p class="user-email">{{ user?.email }}</p>
      <button type="button" @click="passwordOpen = true; menuOpen = false">
        <KeyRound :size="14" />修改密码
      </button>
      <button type="button" class="danger" @click="signOut"><LogOut :size="14" />退出登录</button>
    </div>

    <p v-if="notice" class="user-notice">{{ notice }}</p>

    <div v-if="passwordOpen" class="login-gate user-gate" role="dialog" aria-modal="true">
      <form class="login-card" @submit.prevent="submitPassword">
        <div class="login-brand">
          <span class="brand-icon"><KeyRound :size="18" /></span>
          <div><b>修改密码</b><small>修改后其他设备需要重新登录</small></div>
        </div>
        <label class="login-field">
          <span>当前密码</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" required />
        </label>
        <label class="login-field">
          <span>新密码</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" required />
        </label>
        <p v-if="error" class="login-error">{{ error }}</p>
        <div class="login-actions">
          <button class="login-ghost" type="button" @click="closePassword">取消</button>
          <button class="login-submit" type="submit" :disabled="busy">
            <LoaderCircle v-if="busy" class="spin" :size="15" />保存
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
