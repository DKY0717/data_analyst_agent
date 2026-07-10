import { describe, expect, it } from 'vitest'
import { exampleQuestions } from '@/api/agent'

describe('agent example questions', () => {
  it('starts with the v1.6 core business demo questions', () => {
    // 核心路径问题放在首页最前面，保证演示时不用临场搜索合适问题。
    expect(exampleQuestions.slice(0, 6)).toEqual([
      '统计 2024 年每个月的销售额',
      '找出销售额最高的 5 个商品',
      '统计各商品类别的销售额',
      '分析各商品类别的退款率',
      '计算 2024 年的平均客单价',
      '统计各支付方式对应的销售额',
    ])
  })

  it('keeps exactly twelve homepage examples', () => {
    expect(exampleQuestions).toHaveLength(12)
  })
})
