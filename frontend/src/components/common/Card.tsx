import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  title?: string
  subtitle?: string
  actions?: ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  onClick?: () => void
  hoverable?: boolean
  featured?: boolean
}

const paddingStyles = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
}

export const Card = ({
  children,
  title,
  subtitle,
  actions,
  className = '',
  padding = 'md',
  onClick,
  hoverable = false,
  featured = false,
}: CardProps) => {
  const hasHeader = title || subtitle || actions

  return (
    <div
      className={`
        bg-white rounded-2xl shadow-md
        ${featured ? 'border-2 border-[#4ac6d6]' : 'border border-[#4ac6d6]'}
        ${hoverable ? 'cursor-pointer transition-shadow hover:shadow-lg' : ''}
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
    >
      {hasHeader && (
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div>
            {title && (
              <h3 className="text-lg font-heading italic font-medium text-gray-900">{title}</h3>
            )}
            {subtitle && (
              <p className="mt-1 text-sm italic text-gray-500">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={paddingStyles[padding]}>{children}</div>
    </div>
  )
}
