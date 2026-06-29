<script setup>
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const roles = [
  { key: 'admin', label: 'Admin', type: 'danger' },
  { key: 'analyst', label: 'Analyst', type: 'success' },
  { key: 'support', label: 'Support', type: 'warning' },
]

async function switchRole(role) {
  try {
    await auth.demoLogin(role)
    ElMessage.success(`已切换到 ${role}`)
  } catch (error) {
    ElMessage.error(error.message || '演示登录失败')
  }
}

function logout() {
  auth.logout()
  ElMessage.info('已退出演示身份')
}
</script>

<template>
  <div class="auth-bar">
    <template v-if="!auth.isAuthenticated">
      <el-tag type="warning" effect="dark" round size="small">未认证</el-tag>
    </template>

    <template v-else>
      <el-tag type="success" effect="dark" round size="small">{{ auth.user.user_id }}</el-tag>
      <el-tag type="info" effect="plain" round size="small">{{ auth.user.auth_method }}</el-tag>
      <el-tag type="primary" effect="plain" round size="small">{{ auth.currentRole }}</el-tag>
    </template>

    <el-button-group class="auth-role-group">
      <el-button
        v-for="role in roles"
        :key="role.key"
        :data-test="`role-${role.key}`"
        :type="role.type"
        :loading="auth.loading && auth.selectedRole === role.key"
        size="small"
        plain
        @click="switchRole(role.key)"
      >
        {{ role.label }}
      </el-button>
    </el-button-group>

    <el-button v-if="auth.isAuthenticated" size="small" plain @click="logout">退出</el-button>
  </div>
</template>

<style scoped>
.auth-bar {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.auth-role-group {
  display: inline-flex;
}
</style>
