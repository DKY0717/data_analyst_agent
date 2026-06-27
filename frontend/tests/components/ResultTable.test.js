import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ResultTable from '@/components/ResultTable.vue'

function mountTable(data) {
  return mount(ResultTable, {
    props: { data },
    global: { plugins: [ElementPlus] },
  })
}

describe('ResultTable', () => {
  it('无数据时显示空状态', () => {
    const wrapper = mountTable(null)
    expect(wrapper.text()).toContain('暂无结果数据')
  })

  it('显示列数和行数', () => {
    const wrapper = mountTable({
      columns: ['name', 'value'],
      rows: [['A', 1], ['B', 2]],
    })
    expect(wrapper.text()).toContain('共 2 行')
    expect(wrapper.text()).toContain('2 列')
  })

  it('显示导出按钮', () => {
    const wrapper = mountTable({
      columns: ['a', 'b'],
      rows: [[1, 2]],
    })
    expect(wrapper.text()).toContain('CSV')
    expect(wrapper.text()).toContain('Excel')
  })

  it('大量数据时显示分页', () => {
    const rows = Array.from({ length: 100 }, (_, i) => [`row${i}`, i])
    const wrapper = mountTable({
      columns: ['name', 'value'],
      rows,
    })
    expect(wrapper.find('.table-pagination').exists()).toBe(true)
  })

  it('少量数据不显示分页', () => {
    const rows = Array.from({ length: 10 }, (_, i) => [`row${i}`, i])
    const wrapper = mountTable({
      columns: ['name', 'value'],
      rows,
    })
    expect(wrapper.find('.table-pagination').exists()).toBe(false)
  })
})