import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChartPanel from '@/components/ChartPanel.vue'

const echartsMock = vi.hoisted(() => ({
  init: vi.fn(),
  use: vi.fn(),
  instances: [],
}))

vi.mock('echarts/core', () => ({
  init: echartsMock.init,
  use: echartsMock.use,
}))

vi.mock('echarts/charts', () => ({
  BarChart: {},
  LineChart: {},
  PieChart: {},
  ScatterChart: {},
}))

vi.mock('echarts/components', () => ({
  GridComponent: {},
  LegendComponent: {},
  TooltipComponent: {},
}))

vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

const firstResult = {
  columns: ['category_name', 'sales_amount'],
  rows: [['电子产品', 262581], ['服装', 47281]],
}

const secondResult = {
  columns: ['category_name', 'sales_amount'],
  rows: [['体育用品', 36113], ['家居用品', 33782]],
}

beforeEach(() => {
  echartsMock.instances.length = 0
  echartsMock.init.mockReset()
  echartsMock.use.mockClear()

  // 每个模拟实例都记录绑定 DOM，才能验证第二次查询没有继续使用已销毁画布。
  echartsMock.init.mockImplementation((dom) => {
    const instance = {
      clear: vi.fn(),
      dispose: vi.fn(),
      getDom: vi.fn(() => dom),
      resize: vi.fn(),
      setOption: vi.fn(),
    }
    echartsMock.instances.push(instance)
    return instance
  })
})

describe('ChartPanel', () => {
  it('连续查询时释放旧实例并在新画布重新初始化', async () => {
    const wrapper = mount(ChartPanel, { props: { data: firstResult } })
    await flushPromises()

    expect(echartsMock.init).toHaveBeenCalledTimes(1)
    const firstCanvas = echartsMock.init.mock.calls[0][0]
    const firstInstance = echartsMock.instances[0]
    expect(firstInstance.setOption).toHaveBeenCalled()

    // 查询开始时结果会短暂清空，v-if 会真实销毁第一块画布。
    await wrapper.setProps({ data: null })
    await flushPromises()
    expect(wrapper.find('.chart-canvas').exists()).toBe(false)
    expect(firstInstance.dispose).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ data: secondResult })
    await flushPromises()

    expect(echartsMock.init).toHaveBeenCalledTimes(2)
    const secondCanvas = echartsMock.init.mock.calls[1][0]
    const secondInstance = echartsMock.instances[1]
    expect(secondCanvas).not.toBe(firstCanvas)
    expect(secondInstance.setOption).toHaveBeenCalled()

    const scatterButton = wrapper.findAll('.type-btn').find(button => button.text() === '散点图')
    await scatterButton.trigger('click')
    await flushPromises()
    const latestOption = secondInstance.setOption.mock.calls.at(-1)[0]
    expect(latestOption.series[0].type).toBe('scatter')

    wrapper.unmount()
    expect(secondInstance.dispose).toHaveBeenCalledTimes(1)
  })
})
