export const CLASS_LABELS = {
  new: 'Новое',
  match: 'Обновление',
  moved: 'Другая организация',
  dup_in_file: 'Дубль в пачке',
  error: 'Ошибка'
}

export const CLASS_BADGES = {
  new: 'bg-primary',
  match: 'bg-success',
  moved: 'bg-warning text-dark',
  dup_in_file: 'bg-warning text-dark',
  error: 'bg-danger'
}

export const CLASS_ORDER = ['new', 'match', 'moved', 'dup_in_file', 'error']

export const CONFLICT_CLASSES = ['moved', 'dup_in_file']

export const PRICE_FIELDS = [
  { key: 'price_a4_bw', label: 'A4 ч/б' },
  { key: 'price_a4_color', label: 'A4 цвет' },
  { key: 'price_a3_bw', label: 'A3 ч/б' },
  { key: 'price_a3_color', label: 'A3 цвет' }
]
