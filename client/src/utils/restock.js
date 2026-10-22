// Restock recommendation logic for the Restocking tab.
// Forecast items need `unit_cost` and `lead_time_days` (see server/data/demand_forecasts.json).

// Rising demand is restocked first, falling demand last.
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

const toCents = (amount) => Math.round(amount * 100)

// Order forecast items by restock priority: trend first, then the size of the
// demand gap (forecasted minus current), then SKU so the order is stable.
export function rankForecasts(forecasts) {
  return [...forecasts].sort((a, b) => {
    const trendDiff = (TREND_RANK[a.trend] ?? 3) - (TREND_RANK[b.trend] ?? 3)
    if (trendDiff !== 0) return trendDiff
    const gapDiff = (b.forecasted_demand - b.current_demand) - (a.forecasted_demand - a.current_demand)
    if (gapDiff !== 0) return gapDiff
    return a.item_sku.localeCompare(b.item_sku)
  })
}

// Cost to restock every forecast item to its full forecasted demand.
// Useful as the budget slider's maximum.
export function fullRestockCost(forecasts) {
  return forecasts.reduce((sum, f) => sum + toCents(f.unit_cost) * f.forecasted_demand, 0) / 100
}

// Fill the budget greedily in priority order. Each item asks for its full
// forecasted demand; if that doesn't fit, it gets as many units as the
// remaining budget allows, and later (often cheaper) items can still use
// what's left. Skipped SKUs (unticked by the user) are left out entirely.
//
// Returns { items: [{ ...forecast, quantity, line_total }], total, remaining }.
export function recommendRestock(forecasts, budget, skippedSkus = new Set()) {
  // Work in cents so repeated subtraction doesn't drift.
  let remainingCents = Math.max(0, toCents(budget))
  const items = []

  for (const forecast of rankForecasts(forecasts)) {
    if (skippedSkus.has(forecast.item_sku)) continue

    const unitCents = toCents(forecast.unit_cost)
    if (unitCents <= 0) continue

    const affordable = Math.floor(remainingCents / unitCents)
    const quantity = Math.min(forecast.forecasted_demand, affordable)
    if (quantity <= 0) continue

    const lineCents = quantity * unitCents
    remainingCents -= lineCents
    items.push({ ...forecast, quantity, line_total: lineCents / 100 })
  }

  const totalCents = items.reduce((sum, item) => sum + toCents(item.line_total), 0)
  return { items, total: totalCents / 100, remaining: remainingCents / 100 }
}
