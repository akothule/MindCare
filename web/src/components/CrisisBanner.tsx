import type { ResourceItem } from '../types/chat'

interface Props {
  resources: ResourceItem[]
}

export function CrisisBanner({ resources }: Props) {
  if (resources.length === 0) {
    return null
  }

  return (
    <aside className="crisis-banner" role="region" aria-label="Crisis resources">
      <h2 className="crisis-banner__title">Need immediate support?</h2>
      <ul className="crisis-banner__list">
        {resources.map((r) => (
          <li key={`${r.label}-${r.value}`}>
            <strong>{r.label}</strong>
            <span className="crisis-banner__value">{r.value}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}
