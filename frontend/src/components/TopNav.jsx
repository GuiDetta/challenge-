import { BarChart3, Bell, CircleHelp, LayoutDashboard, Settings } from 'lucide-react'
import BrandMark from './BrandMark'

const navigationItems = [
  { label: 'Visão Geral', icon: LayoutDashboard, active: true },
  { label: 'Carregadores', icon: ZapIcon },
  { label: 'Relatórios', icon: BarChart3 },
  { label: 'Configurações', icon: Settings },
  { label: 'Ajuda', icon: CircleHelp },
]

function ZapIcon({ size, strokeWidth }) {
  return <span className="nav-zap" style={{ width: size, height: size, borderWidth: strokeWidth }} />
}

function TopNav() {
  return <header className="top-nav"><BrandMark /><nav aria-label="Navegação principal">{navigationItems.map(({ label, icon: Icon, active }) => <button className={`nav-item ${active ? 'is-active' : ''}`} key={label} type="button"><Icon size={15} strokeWidth={2} /><span>{label}</span></button>)}</nav><button className="icon-button notification-button" type="button" aria-label="Notificações"><Bell size={17} /><span className="notification-dot" /></button></header>
}

export default TopNav