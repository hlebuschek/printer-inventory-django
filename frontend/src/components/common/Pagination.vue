<template>
  <div class="d-flex justify-content-between align-items-center mt-4">
    <!-- Pagination controls -->
    <nav aria-label="Навигация по страницам">
      <ul class="pagination mb-0">
        <!-- First page -->
        <li v-if="currentPage > 1" class="page-item">
          <a class="page-link" href="#" @click.prevent="changePage(1)">
            «« Первая
          </a>
        </li>

        <!-- Previous page -->
        <li v-if="currentPage > 1" class="page-item">
          <a class="page-link" href="#" @click.prevent="changePage(currentPage - 1)">
            « Предыдущая
          </a>
        </li>

        <!-- Page numbers -->
        <li
          v-for="page in visiblePages"
          :key="page"
          class="page-item"
          :class="{ active: page === currentPage }"
        >
          <a
            v-if="page === currentPage"
            class="page-link"
            href="#"
            @click.prevent
          >
            {{ page }}
          </a>
          <a
            v-else
            class="page-link"
            href="#"
            @click.prevent="changePage(page)"
          >
            {{ page }}
          </a>
        </li>

        <!-- Next page -->
        <li v-if="currentPage < totalPages" class="page-item">
          <a class="page-link" href="#" @click.prevent="changePage(currentPage + 1)">
            Следующая »
          </a>
        </li>

        <!-- Last page -->
        <li v-if="currentPage < totalPages" class="page-item">
          <a class="page-link" href="#" @click.prevent="changePage(totalPages)">
            Последняя »»
          </a>
        </li>
      </ul>
    </nav>

    <!-- Per page selector -->
    <div>
      <select
        :value="perPage"
        class="form-select"
        style="width: auto;"
        @change="changePerPage($event.target.value)"
      >
        <option
          v-for="option in perPageOptions"
          :key="option"
          :value="option"
        >
          {{ option }} на странице
        </option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentPage: {
    type: Number,
    required: true
  },
  totalPages: {
    type: Number,
    required: true
  },
  perPage: {
    type: Number,
    default: 100
  },
  perPageOptions: {
    type: Array,
    default: () => [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]
  }
})

const emit = defineEmits(['page-change', 'per-page-change'])

// Compute visible pages (show current page ± 2 pages)
const visiblePages = computed(() => {
  const pages = []
  const start = Math.max(1, props.currentPage - 2)
  const end = Math.min(props.totalPages, props.currentPage + 2)

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return pages
})

function changePage(page) {
  if (page >= 1 && page <= props.totalPages && page !== props.currentPage) {
    emit('page-change', page)
  }
}

function changePerPage(value) {
  const perPage = parseInt(value, 10)
  if (!isNaN(perPage)) {
    emit('per-page-change', perPage)
  }
}
</script>
