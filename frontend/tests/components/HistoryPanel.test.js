import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HistoryPanel from '@/components/HistoryPanel.vue'

describe('HistoryPanel', () => {
  const mockHistory = [
    { question: '问题一', createdAt: '10:30', success: true },
    { question: '问题二', createdAt: '10:31', success: false },
  ]

  const mockFavorites = [
    { question: '收藏问题', createdAt: '10:00' },
  ]

  it('显示历史记录', () => {
    const wrapper = mount(HistoryPanel, {
      props: { history: mockHistory },
    })
    expect(wrapper.text()).toContain('问题一')
    expect(wrapper.text()).toContain('问题二')
  })

  it('空历史显示提示', () => {
    const wrapper = mount(HistoryPanel, {
      props: { history: [] },
    })
    expect(wrapper.text()).toContain('提交一次分析后会显示历史记录')
  })

  it('切换到收藏 Tab', async () => {
    const wrapper = mount(HistoryPanel, {
      props: { history: mockHistory, favorites: mockFavorites },
    })
    const favTab = wrapper.findAll('.tab-btn')[1]
    await favTab.trigger('click')
    expect(wrapper.text()).toContain('收藏问题')
  })

  it('收藏 Tab 空状态显示提示', async () => {
    const wrapper = mount(HistoryPanel, {
      props: { history: [], favorites: [] },
    })
    const favTab = wrapper.findAll('.tab-btn')[1]
    await favTab.trigger('click')
    expect(wrapper.text()).toContain('点击历史记录旁的 ☆ 收藏常用查询')
  })

  it('点击历史项触发 select 事件', async () => {
    const wrapper = mount(HistoryPanel, {
      props: { history: mockHistory },
    })
    await wrapper.find('.history-item').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0]).toEqual(['问题一'])
  })

  it('点击收藏按钮触发 favorite 事件', async () => {
    const wrapper = mount(HistoryPanel, {
      props: {
        history: mockHistory,
        isFavorite: () => false,
      },
    })
    await wrapper.find('.fav-btn').trigger('click')
    expect(wrapper.emitted('favorite')).toBeTruthy()
  })
})