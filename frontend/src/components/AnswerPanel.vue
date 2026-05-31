<template>
  <section class="panel answer-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">结果解释</h2>
        <p class="panel-subtitle">优先展示业务结论，再查看 SQL 和明细。</p>
      </div>
      <el-tag v-if="result?.used_mock" type="warning" effect="light">Mock 数据</el-tag>
    </div>

    <div class="answer-content">
      <template v-if="loading">
        <el-steps :active="2" finish-status="success" simple>
          <el-step title="读取 Schema" />
          <el-step title="生成 SQL" />
          <el-step title="安全校验" />
          <el-step title="执行查询" />
        </el-steps>
      </template>

      <template v-else-if="error">
        <el-alert
          title="分析失败"
          type="error"
          :description="error.message || '接口请求失败，请检查后端服务。'"
          show-icon
          :closable="false"
        />
      </template>

      <template v-else-if="result">
        <p class="answer-text">{{ result.answer }}</p>
        <div class="metric-row">
          <div class="metric-card">
            <span>返回行数</span>
            <strong>{{ result.rows?.length || 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>执行耗时</span>
            <strong>{{ result.execution_time_ms }}ms</strong>
          </div>
          <div class="metric-card">
            <span>修复次数</span>
            <strong>{{ result.retry_count }}</strong>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="empty-state">
          <h3>从一个业务问题开始</h3>
          <p>例如分析销售趋势、商品排行、地区表现或退款率。</p>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: Object,
    default: null,
  },
})
</script>
