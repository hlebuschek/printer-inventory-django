<template>
  <div>
    <canvas ref="chartCanvas" style="max-height: 400px;"></canvas>
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
  Legend
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
  Legend
)

const props = defineProps({
  historyData: {
    type: Array,
    default: () => []
  }
})

const chartCanvas = ref(null)
let chartInstance = null

function createChart() {
  if (!chartCanvas.value || !props.historyData.length) return

  // Destroy existing chart
  if (chartInstance) {
    chartInstance.destroy()
  }

  const labels = props.historyData.map(row =>
    new Date(row.task_timestamp).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  )

  const datasets = [
    {
      label: 'ЧБ A4',
      data: props.historyData.map(row => row.bw_a4 || 0),
      borderColor: '#000000',
      yAxisID: 'y',
      borderWidth: 2,
      borderDash: [],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Цвет A4',
      data: props.historyData.map(row => row.color_a4 || 0),
      borderColor: '#ff0000',
      yAxisID: 'y',
      borderWidth: 2,
      borderDash: [],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'ЧБ A3',
      data: props.historyData.map(row => row.bw_a3 || 0),
      borderColor: '#0000ff',
      yAxisID: 'y',
      borderWidth: 2,
      borderDash: [],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Цвет A3',
      data: props.historyData.map(row => row.color_a3 || 0),
      borderColor: '#00ff00',
      yAxisID: 'y',
      borderWidth: 2,
      borderDash: [],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Всего',
      data: props.historyData.map(row => row.total_pages || 0),
      borderColor: '#ff00ff',
      yAxisID: 'y',
      borderWidth: 2,
      borderDash: [],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Тонер (K)',
      data: props.historyData.map(row => row.toner_black || 0),
      borderColor: '#333333',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Тонер (C)',
      data: props.historyData.map(row => row.toner_cyan || 0),
      borderColor: '#00ffff',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Тонер (M)',
      data: props.historyData.map(row => row.toner_magenta || 0),
      borderColor: '#ff3399',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Тонер (Y)',
      data: props.historyData.map(row => row.toner_yellow || 0),
      borderColor: '#ffff00',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Барабан (K)',
      data: props.historyData.map(row => row.drum_black || 0),
      borderColor: '#666666',
      yAxisID: 'y1',
      borderWidth: 0,
      borderDash: [],
      pointStyle: 'circle',
      pointRadius: 5,
      pointHoverRadius: 7,
      hidden: false
    },
    {
      label: 'Барабан (C)',
      data: props.historyData.map(row => row.drum_cyan || 0),
      borderColor: '#3399ff',
      yAxisID: 'y1',
      borderWidth: 0,
      borderDash: [],
      pointStyle: 'circle',
      pointRadius: 5,
      pointHoverRadius: 7,
      hidden: false
    },
    {
      label: 'Барабан (M)',
      data: props.historyData.map(row => row.drum_magenta || 0),
      borderColor: '#cc00cc',
      yAxisID: 'y1',
      borderWidth: 0,
      borderDash: [],
      pointStyle: 'circle',
      pointRadius: 5,
      pointHoverRadius: 7,
      hidden: false
    },
    {
      label: 'Барабан (Y)',
      data: props.historyData.map(row => row.drum_yellow || 0),
      borderColor: '#cccc00',
      yAxisID: 'y1',
      borderWidth: 0,
      borderDash: [],
      pointStyle: 'circle',
      pointRadius: 5,
      pointHoverRadius: 7,
      hidden: false
    },
    {
      label: 'Fuser Kit',
      data: props.historyData.map(row => row.fuser_kit || 0),
      borderColor: '#ff9933',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Transfer Kit',
      data: props.historyData.map(row => row.transfer_kit || 0),
      borderColor: '#33cc33',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
      hidden: false
    },
    {
      label: 'Waste Toner',
      data: props.historyData.map(row => row.waste_toner || 0),
      borderColor: '#9933ff',
      yAxisID: 'y1',
      borderWidth: 2,
      borderDash: [5, 5],
      pointStyle: 'line',
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
      scales: {
        y: {
          position: 'left',
          title: {
            display: true,
            text: 'Счётчики (страницы)'
          }
        },
        y1: {
          position: 'right',
          title: {
            display: true,
            text: 'Расходники (%)'
          },
          max: 100,
          min: 0
        }
      },
      plugins: {
        legend: {
          position: 'top',
          onClick: (e, legendItem, legend) => {
            const index = legendItem.datasetIndex
            const ci = legend.chart
            const meta = ci.getDatasetMeta(index)
            meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null
            ci.data.datasets[index].hidden = !ci.data.datasets[index].hidden
            ci.update()
          },
          labels: {
            filter: (legendItem, chartData) => {
              return hasNonZero(chartData.datasets[legendItem.datasetIndex])
            }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          filter: (tip) => tip.raw !== 0
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
