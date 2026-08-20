'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { HistoryItem } from '../_lib/api-client'

interface ChatMessageProps {
  item: HistoryItem
}

export default function ChatMessage({ item }: ChatMessageProps) {
  return (
    <div className="flex flex-col gap-2">
      {/* Pregunta del usuario */}
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-zinc-100 px-4 py-2.5 text-sm text-zinc-900">
          {item.question}
        </div>
      </div>

      {/* Respuesta del agente */}
      <div className="flex justify-start">
        <div className="max-w-[75%] rounded-2xl rounded-tl-sm border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-800">
          {item.answer
            ? <div className="prose prose-sm prose-zinc max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.answer}</ReactMarkdown>
              </div>
            : <p className="text-zinc-400">Pensando…</p>
          }
        </div>
      </div>
    </div>
  )
}
