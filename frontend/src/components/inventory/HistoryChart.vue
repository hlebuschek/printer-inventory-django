<template>
  <div class="chart-container">
    <canvas ref="chartCanvas"></canvas>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

// Register Chart.js components
Chart.register(
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  historyData: {
    type: Array,
    default: () => []
  }
})

const chartCanvas = ref(null)
let chartInstance = null

// Create gradient for dataset
function createGradient(ctx, color, alpha = 0.1) {
  const gradient = ctx.createLinearGradient(0, 0, 0, 400)
  gradient.addColorStop(0, color + Math.round(alpha * 255).toString(16).padStart(2, '0'))
  gradient.addColorStop(1, color + '00')
  return gradient
}

function createChart() {
  if (!chartCanvas.value || !props.historyData.length) return

  // Destroy existing chart
  if (chartInstance) {
    chartInstance.destroy()
  }

  // Sort data by timestamp in ascending order (oldest to newest)
  const sortedData = [...props.historyData].sort((a, b) =>
    new Date(a.task_timestamp) - new Date(b.task_timestamp)
  )

  const labels = sortedData.map(row =>
    new Date(row.task_timestamp).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  )

  const ctx = chartCanvas.value.getContext('2d')

  // Modern color palette
  const colors = {
    bwA4: { border: '#374151', bg: '#374151' },      // Gray-700
    colorA4: { border: '#EF4444', bg: '#EF4444' },   // Red-500
    bwA3: { border: '#3B82F6', bg: '#3B82F6' },      // Blue-500
    colorA3: { border: '#10B981', bg: '#10B981' },   // Green-500
    total: { border: '#8B5CF6', bg: '#8B5CF6' },     // Purple-500
    tonerK: { border: '#1F2937', bg: '#1F2937' },    // Gray-800
    tonerC: { border: '#06B6D4', bg: '#06B6D4' },    // Cyan-500
    tonerM: { border: '#EC4899', bg: '#EC4899' },    // Pink-500
    tonerY: { border: '#F59E0B', bg: '#F59E0B' },    // Amber-500
    drumK: { border: '#4B5563', bg: '#4B5563' },     // Gray-600
    drumC: { border: '#0EA5E9', bg: '#0EA5E9' },     // Sky-500
    drumM: { border: '#D946EF', bg: '#D946EF' },     // Fuchsia-500
    drumY: { border: '#FBBF24', bg: '#FBBF24' },     // Amber-400
    fuser: { border: '#F97316', bg: '#F97316' },     // Orange-500
    transfer: { border: '#14B8A6', bg: '#14B8A6' },  // Teal-500
    waste: { border: '#A855F7', bg: '#A855F7' }      // Purple-500
  }

  const datasets = [
    {
      label: 'ЧБ A4',
      data: sortedData.map(row => row.bw_a4 || 0),
      borderColor: colors.bwA4.border,
      backgroundColor: createGradient(ctx, colors.bwA4.bg, 0.15),
      yAxisID: 'y',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.bwA4.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Цвет A4',
      data: sortedData.map(row => row.color_a4 || 0),
      borderColor: colors.colorA4.border,
      backgroundColor: createGradient(ctx, colors.colorA4.bg, 0.15),
      yAxisID: 'y',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.colorA4.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'ЧБ A3',
      data: sortedData.map(row => row.bw_a3 || 0),
      borderColor: colors.bwA3.border,
      backgroundColor: createGradient(ctx, colors.bwA3.bg, 0.15),
      yAxisID: 'y',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.bwA3.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Цвет A3',
      data: sortedData.map(row => row.color_a3 || 0),
      borderColor: colors.colorA3.border,
      backgroundColor: createGradient(ctx, colors.colorA3.bg, 0.15),
      yAxisID: 'y',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.colorA3.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Всего',
      data: sortedData.map(row => row.total_pages || 0),
      borderColor: colors.total.border,
      backgroundColor: createGradient(ctx, colors.total.bg, 0.15),
      yAxisID: 'y',
      borderWidth: 3,
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.total.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Тонер (K)',
      data: sortedData.map(row => row.toner_black || 0),
      borderColor: colors.tonerK.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.tonerK.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Тонер (C)',
      data: sortedData.map(row => row.toner_cyan || 0),
      borderColor: colors.tonerC.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.tonerC.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Тонер (M)',
      data: sortedData.map(row => row.toner_magenta || 0),
      borderColor: colors.tonerM.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.tonerM.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Тонер (Y)',
      data: sortedData.map(row => row.toner_yellow || 0),
      borderColor: colors.tonerY.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.tonerY.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Барабан (K)',
      data: sortedData.map(row => row.drum_black || 0),
      borderColor: colors.drumK.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 0,
      tension: 0.4,
      pointStyle: 'circle',
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: colors.drumK.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Барабан (C)',
      data: sortedData.map(row => row.drum_cyan || 0),
      borderColor: colors.drumC.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 0,
      tension: 0.4,
      pointStyle: 'circle',
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: colors.drumC.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Барабан (M)',
      data: sortedData.map(row => row.drum_magenta || 0),
      borderColor: colors.drumM.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 0,
      tension: 0.4,
      pointStyle: 'circle',
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: colors.drumM.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Барабан (Y)',
      data: sortedData.map(row => row.drum_yellow || 0),
      borderColor: colors.drumY.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 0,
      tension: 0.4,
      pointStyle: 'circle',
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: colors.drumY.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Fuser Kit',
      data: sortedData.map(row => row.fuser_kit || 0),
      borderColor: colors.fuser.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.fuser.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Transfer Kit',
      data: sortedData.map(row => row.transfer_kit || 0),
      borderColor: colors.transfer.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.transfer.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    },
    {
      label: 'Waste Toner',
      data: sortedData.map(row => row.waste_toner || 0),
      borderColor: colors.waste.border,
      backgroundColor: 'transparent',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [8, 4],
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: colors.waste.border,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      hidden: false
    }
  ]

  // Check if dataset has non-zero values
  const hasNonZero = (dataset) => {
    return dataset.data.some(v => v != null && v !== 0)
  }

  // Hide datasets with all zero values
  datasets.forEach(ds => {
    ds.hidden = !hasNonZero(ds)
  })

  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      animation: {
        duration: 750,
        easing: 'easeInOutQuart'
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(0, 0, 0, 0.05)',
            drawBorder: false
          },
          ticks: {
            font: {
              size: 11,
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#6B7280'
          }
        },
        y: {
          position: 'left',
          title: {
            display: true,
            text: 'Счётчики (страницы)',
            font: {
              size: 13,
              weight: '600',
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#374151'
          },
          grid: {
            color: 'rgba(0, 0, 0, 0.05)',
            drawBorder: false
          },
          ticks: {
            font: {
              size: 11,
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#6B7280',
            callback: function(value) {
              return value.toLocaleString('ru-RU')
            }
          }
        },
        y1: {
          position: 'right',
          title: {
            display: true,
            text: 'Расходники (%)',
            font: {
              size: 13,
              weight: '600',
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#374151'
          },
          max: 100,
          min: 0,
          grid: {
            drawOnChartArea: false,
            drawBorder: false
          },
          ticks: {
            font: {
              size: 11,
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#6B7280',
            callback: function(value) {
              return value + '%'
            }
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'start',
          labels: {
            boxWidth: 12,
            boxHeight: 12,
            padding: 15,
            font: {
              size: 12,
              family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
            },
            color: '#374151',
            usePointStyle: true,
            filter: (legendItem, chartData) => {
              return hasNonZero(chartData.datasets[legendItem.datasetIndex])
            }
          },
          onClick: (e, legendItem, legend) => {
            const index = legendItem.datasetIndex
            const ci = legend.chart
            const meta = ci.getDatasetMeta(index)
            meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null
            ci.data.datasets[index].hidden = !ci.data.datasets[index].hidden
            ci.update()
          }
        },
        tooltip: {
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          titleColor: '#111827',
          bodyColor: '#374151',
          borderColor: '#E5E7EB',
          borderWidth: 1,
          padding: 12,
          bodySpacing: 6,
          mode: 'index',
          intersect: false,
          titleFont: {
            size: 13,
            weight: '600',
            family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
          },
          bodyFont: {
            size: 12,
            family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial'
          },
          filter: (tip) => tip.raw !== 0,
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || ''
              if (label) {
                label += ': '
              }
              if (context.parsed.y !== null) {
                if (context.dataset.yAxisID === 'y1') {
                  label += context.parsed.y + '%'
                } else {
                  label += context.parsed.y.toLocaleString('ru-RU')
                }
              }
              return label
            }
          }
        }
      }
    }
  })
}

// Watch for data changes
watch(
  () => props.historyData,
  () => {
    createChart()
  },
  { deep: true }
)

onMounted(() => {
  createChart()
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})
</script>

<style scoped>
.chart-container {
  height: 500px;
  padding: 20px;
  background: linear-gradient(to bottom, #ffffff, #f9fafb);
  border-radius: 12px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(229, 231, 235, 0.8);
}
</style>
