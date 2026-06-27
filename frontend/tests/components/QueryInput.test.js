import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import QueryInput from '@/components/QueryInput.vue'

describe('QueryInput', () => {
  it('渲染输入框和按钮', () => {
    const wrapper = mount(QueryInput, {
      props: { modelValue: '' },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('开始分析')
  })

  it('空输入时按钮禁用', () => {
    const wrapper = mount(QueryInput, {
      props: { modelValue: '' },
      global: { plugins: [ElementPlus] },
    })
    const btn = wrapper.find('.submit-button')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('有输入时按钮可用', () => {
    const wrapper = mount(QueryInput, {
      props: { modelValue: '测试问题' },
      global: { plugins: [ElementPlus] },
    })
    const btn = wrapper.find('.submit-button')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('加载时显示进度条和取消按钮', () => {
    const wrapper = mount(QueryInput, {
      props: {
        modelValue: '测试',
        loading: true,
        loadingStage: '生成 SQL...',
        loadingProgress: 65,
      },
      global: { plugins: [ElementPlus] },
    })
    expect(wrapper.find('.progress-bar-wrap').exists()).toBe(true)
    expect(wrapper.text()).toContain('生成 SQL...')
    expect(wrapper.text()).toContain('取消')
  })

  it('输入内容触发 update:modelValue', async () => {
    const wrapper = mount(QueryInput, {
      props: { modelValue: '' },
      global: { plugins: [ElementPlus] },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('新问题')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
  })
})