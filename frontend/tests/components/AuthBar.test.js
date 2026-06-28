import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AuthBar from '@/components/AuthBar.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

const elementStubs = {
  'el-tag': { template: '<span><slot /></span>' },
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-button-group': { template: '<div><slot /></div>' },
}

describe('AuthBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('未登录时展示三个演示角色按钮', () => {
    const wrapper = mount(AuthBar, {
      global: {
        stubs: elementStubs,
      },
    })

    expect(wrapper.text()).toContain('未认证')
    expect(wrapper.text()).toContain('Admin')
    expect(wrapper.text()).toContain('Analyst')
    expect(wrapper.text()).toContain('Support')
  })

  it('点击角色按钮调用 demoLogin', async () => {
    const auth = useAuthStore()
    auth.demoLogin = vi.fn()
    const wrapper = mount(AuthBar, {
      global: {
        stubs: elementStubs,
      },
    })

    await wrapper.find('[data-test="role-analyst"]').trigger('click')

    expect(auth.demoLogin).toHaveBeenCalledWith('analyst')
  })

  it('登录后展示用户和退出按钮', () => {
    const auth = useAuthStore()
    auth.token = 'token-1'
    auth.user = { user_id: 'demo:admin', auth_method: 'jwt', roles: ['admin'] }
    const wrapper = mount(AuthBar, {
      global: {
        stubs: elementStubs,
      },
    })

    expect(wrapper.text()).toContain('demo:admin')
    expect(wrapper.text()).toContain('jwt')
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('退出')
  })
})
