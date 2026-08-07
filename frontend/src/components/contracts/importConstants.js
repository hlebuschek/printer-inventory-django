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
