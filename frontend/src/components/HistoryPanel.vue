<template>
  <section class="panel compact-panel">
    <div class="panel-header">
      <div>
        <h2 class="panel-title">🕐 查询历史</h2>
        <p class="panel-subtitle">{{ activeTab === 'history' ? '本次会话最近的问题' : '收藏的查询' }}。</p>
      </div>
      <div class="tab-group">
        <button :class="['tab-btn', { active: activeTab === 'history' }]" @click="activeTab = 'history'">
          历史
        </button>
        <button :class="['tab-btn', { active: activeTab === 'favorites' }]" @click="activeTab = 'favorites'">
          收藏
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'history'">
      <div v-if="history.length" class="history-list">
        <button
          v-for="item in history"
          :key="`${item.createdAt}-${item.question}`"
          class="history-item"
          type="button"
          @click="$emit('select', item.question)"
        >
          <span class="history-question">
            <span class="history-status" :class="item.success ? 'history-status--ok' : 'history-status--fail'">
              {{ item.success ? '✓' : '✗' }}
            </span>
            {{ item.question }}
          </span>
          <div class="history-actions">
            <small>{{ item.createdAt }}</small>
            <button
              class="fav-btn"
              :class="{ 'fav-btn--active': isFavorite(item.question) }"
              @click.stop="$emit('favorite', item)"
              title="收藏"
            >
              {{ isFavorite(item.question) ? '★' : '☆' }}
            </button>
          </div>
        </button>
      </div>
      <div v-else class="empty-small">提交一次分析后会显示历史记录。</div>
    </div>

    <div v-else>
      <div v-if="favorites.length" class="history-list">
        <button
          v-for="item in favorites"
          :key="`fav-${item.question}`"
          class="history-item"
          type="button"
          @click="$emit('select', item.question)"
        >
          <span class="history-question">
            <span class="history-status history-status--fav">★</span>
            {{ item.question }}
          </span>
          <div class="history-actions">
            <small>{{ item.createdAt }}</small>
            <button class="fav-btn fav-btn--remove" @click.stop="$emit('removeFavorite', item.question)" title="取消收藏">
              ✕
            </button>
          </div>
        </button>
      </div>
      <div v-else class="empty-small">点击历史记录旁的 ☆ 收藏常用查询。</div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  history: {
    type: Array,
    required: true,
  },
  favorites: {
    type: Array,
    default: () => [],
  },
  isFavorite: {
    type: Function,
    default: () => false,
  },
})

defineEmits(['select', 'favorite', 'removeFavorite'])

const activeTab = ref('history')
</script>

<style scoped>
.tab-group {
  display: flex;
  gap: 2px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 2px;
}

.tab-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  font-family: var(--font-body);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 150ms ease-out;
}

.tab-btn:hover {
  color: var(--color-text);
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
}

.history-question {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.history-status {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  margin-top: 2px;
}

.history-status--ok {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-accent);
}

[data-theme="dark"] .history-status--ok {
  background: rgba(52, 211, 153, 0.15);
}

.history-status--fail {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

[data-theme="dark"] .history-status--fail {
  background: rgba(248, 113, 113, 0.15);
}

.history-status--fav {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-warning);
  font-size: 11px;
}

.history-item {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-hover);
  font-family: var(--font-body);
  display: grid;
  gap: var(--space-1);
  padding: var(--space-3);
}

.history-item span {
  color: var(--color-text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item:hover {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.08);
  color: var(--color-text);
  transform: translateX(2px);
}

[data-theme="dark"] .history-item:hover {
  background: rgba(96, 165, 250, 0.12);
}

.history-item:active {
  transform: scale(0.98);
  transition: transform var(--transition-active);
}

.history-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.history-actions small {
  color: var(--color-text-muted);
  font-size: 11px;
}

.fav-btn {
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 14px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  transition: color 150ms;
}

.fav-btn:hover {
  color: var(--color-warning);
}

.fav-btn--active {
  color: var(--color-warning);
}

.fav-btn--remove {
  font-size: 12px;
  color: var(--color-text-muted);
}

.fav-btn--remove:hover {
  color: var(--color-danger);
}
</style>
