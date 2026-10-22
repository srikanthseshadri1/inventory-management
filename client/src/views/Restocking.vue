<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <div>
            <div class="stat-label">{{ t('restocking.budget') }}</div>
            <div class="budget-value">{{ money(budget) }}</div>
          </div>
          <div class="slider-wrap">
            <input
              v-model.number="budget"
              type="range"
              min="0"
              :max="maxBudget"
              step="500"
              class="budget-slider"
              :aria-label="t('restocking.budget')"
            />
            <div class="slider-scale">
              <span>{{ money(0) }}</span>
              <span>{{ money(maxBudget) }}</span>
            </div>
            <div class="hint">{{ t('restocking.budgetHint') }}</div>
          </div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.summary.orderTotal') }}</div>
          <div class="stat-value">{{ money(recommendation.total) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.summary.budgetRemaining') }}</div>
          <div class="stat-value">{{ money(recommendation.remaining) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.summary.leadTime') }}</div>
          <div class="stat-value">
            {{ leadTimeDays === null ? t('restocking.summary.none') : t('restocking.summary.days', { count: leadTimeDays }) }}
          </div>
        </div>
      </div>

      <div v-if="confirmation" class="confirmation">
        <strong>{{ t('restocking.confirmation.title') }}</strong>
        <div>{{ t('restocking.confirmation.orderNumber') }}: <strong>{{ confirmation.order_number }}</strong></div>
        <div>{{ t('restocking.confirmation.expectedDelivery') }}: <strong>{{ formatDate(confirmation.expected_delivery) }}</strong></div>
        <router-link to="/orders" class="confirmation-link">{{ t('restocking.confirmation.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendation.items.length }})</h3>
          <button
            class="place-order-btn"
            :disabled="recommendation.items.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="recommendation.items.length === 0" class="hint empty-hint">{{ t('restocking.noItems') }}</div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th class="col-check">{{ t('restocking.table.include') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
                <th>{{ t('restocking.table.note') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.item_sku" :class="{ dimmed: row.skipped || !row.quantity }">
                <td class="col-check">
                  <input
                    type="checkbox"
                    :checked="!row.skipped"
                    :aria-label="row.item_sku"
                    @change="toggleSku(row.item_sku)"
                  />
                </td>
                <td><strong>{{ row.item_sku }}</strong></td>
                <td>{{ row.item_name }}</td>
                <td>
                  <span :class="['badge', row.trend]">{{ t(`trends.${row.trend}`) }}</span>
                </td>
                <td class="num">{{ money(row.unit_cost, 2) }}</td>
                <td class="num">{{ row.quantity || '-' }}</td>
                <td class="num"><strong>{{ row.quantity ? money(row.line_total, 2) : '-' }}</strong></td>
                <td class="num">{{ row.lead_time_days }}</td>
                <td class="note">{{ row.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'
import { rankForecasts, fullRestockCost, recommendRestock } from '../utils/restock'

const DEFAULT_BUDGET = 25000

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(DEFAULT_BUDGET) // always USD; converted only for display
    // Replace the Set on each toggle so computed values re-evaluate.
    const skippedSkus = ref(new Set())
    const submitting = ref(false)
    const submitError = ref(null)
    const confirmation = ref(null)

    // Slider max: full restock cost rounded up to the nearest 1,000
    const maxBudget = computed(() => Math.ceil(fullRestockCost(forecasts.value) / 1000) * 1000)

    const recommendation = computed(() =>
      recommendRestock(forecasts.value, budget.value, skippedSkus.value)
    )

    // Every forecast item in priority order, merged with its recommendation (if any)
    // so skipped and unfunded items stay visible and can be re-ticked.
    const rows = computed(() => {
      const recommended = new Map(recommendation.value.items.map(i => [i.item_sku, i]))
      return rankForecasts(forecasts.value).map(f => {
        const rec = recommended.get(f.item_sku)
        const skipped = skippedSkus.value.has(f.item_sku)
        let note = ''
        if (skipped) note = t('restocking.skipped')
        else if (!rec) note = t('restocking.notFunded')
        else if (rec.quantity < f.forecasted_demand) note = t('restocking.partial')
        return {
          ...f,
          skipped,
          quantity: rec ? rec.quantity : 0,
          line_total: rec ? rec.line_total : 0,
          note
        }
      })
    })

    // Order lead time is set by the slowest item
    const leadTimeDays = computed(() => {
      const items = recommendation.value.items
      if (items.length === 0) return null
      return Math.max(...items.map(i => i.lead_time_days))
    })

    const money = (amount, decimals = 0) =>
      decimals > 0
        ? formatCurrencyWithDecimals(amount, currentCurrency.value, decimals)
        : formatCurrency(amount, currentCurrency.value)

    const formatDate = (value) => {
      const date = new Date(value)
      if (isNaN(date.getTime())) return '-'
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const toggleSku = (sku) => {
      const next = new Set(skippedSkus.value)
      if (next.has(sku)) next.delete(sku)
      else next.add(sku)
      skippedSkus.value = next
      confirmation.value = null
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()
        budget.value = Math.min(DEFAULT_BUDGET, maxBudget.value)
      } catch (err) {
        error.value = t('restocking.loadFailed') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (submitting.value || recommendation.value.items.length === 0) return
      submitting.value = true
      submitError.value = null
      confirmation.value = null
      try {
        confirmation.value = await api.createRestockOrder({
          budget: budget.value,
          items: recommendation.value.items.map(i => ({ sku: i.item_sku, quantity: i.quantity }))
        })
      } catch (err) {
        submitError.value = err.response?.data?.detail || t('restocking.orderFailed')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      loading,
      error,
      budget,
      maxBudget,
      recommendation,
      rows,
      leadTimeDays,
      submitting,
      submitError,
      confirmation,
      money,
      formatDate,
      toggleSku,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.25rem;
}

.budget-row {
  display: flex;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
}

.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.slider-wrap {
  flex: 1;
  min-width: 260px;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
}

.slider-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
}

.hint {
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.375rem;
}

.empty-hint {
  padding: 0.5rem 0 1rem;
}

.confirmation {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.confirmation-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
  margin-top: 0.25rem;
}

.confirmation-link:hover {
  text-decoration: underline;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.col-check {
  width: 70px;
  text-align: center;
}

th.num,
td.num {
  text-align: right;
}

tr.dimmed td {
  color: #94a3b8;
}

tr.dimmed .badge {
  opacity: 0.5;
}

.note {
  font-size: 0.813rem;
  color: #64748b;
}
</style>
