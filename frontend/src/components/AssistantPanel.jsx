import { ArrowUp, Bot, SlidersHorizontal } from 'lucide-react'

function AssistantPanel() {
  return <section className="assistant-panel panel-frame"><div className="assistant-header"><div className="assistant-title"><span className="assistant-icon"><Bot size={15} /></span><span>Assistente virtual</span><span className="online-mark" /></div><button className="icon-button" type="button" aria-label="Configurar assistente"><SlidersHorizontal size={16} /></button></div><div className="assistant-body"><p className="assistant-intro">Conecte o backend para iniciar o monitoramento da operação.</p><div className="assistant-message"><span className="message-avatar">GW</span><span>Aguardando comandos ou seleção de carregadores.</span></div></div><form className="assistant-input" onSubmit={(event) => event.preventDefault()}><input aria-label="Mensagem para o assistente" placeholder="Escreva um comando ou pergunta..." /><button type="submit" aria-label="Enviar mensagem"><ArrowUp size={16} /></button></form></section>
}

export default AssistantPanel