import type { ExecutionEvent } from '../../types/domain'
import { AssistantTurn } from './AssistantTurn'

export interface ChatTurnVM {
  /** Execution id of the turn. */
  id: string
  userInput: string
  events: ExecutionEvent[]
  result?: string | null
  /** True while the turn is still streaming. */
  pending?: boolean
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="self-end max-w-[75%] rounded-lg rounded-br-sm bg-blue-600 text-white px-3 py-2 text-sm whitespace-pre-wrap">
      {text}
    </div>
  )
}

/** Renders the conversation as alternating user / assistant turns. */
export function ChatThread({ turns }: { turns: ChatTurnVM[] }) {
  if (turns.length === 0) {
    return (
      <p className="text-sm text-slate-500 text-center py-8">
        Send a message to start the conversation.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      {turns.map(turn => (
        <div key={turn.id} className="flex flex-col gap-2">
          <UserBubble text={turn.userInput} />
          <AssistantTurn events={turn.events} fallbackResult={turn.result} pending={turn.pending} />
        </div>
      ))}
    </div>
  )
}
