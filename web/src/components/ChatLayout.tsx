import type { Message, ModelView } from "../api/client";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { ContextRail } from "./ContextRail";

/**
 * The chat view's frame. The conversation (messages + composer) centers within the
 * space between the nav and the context rail — equal breathing room on both sides so
 * a wide screen stays balanced — while the rail trails flush to the right edge from
 * `lg` up. The whole thing fills the canvas up to a generous cap. The width/centering
 * decisions live here so App and the layout demo share one source of truth.
 */
export function ChatLayout({
  messages,
  streaming,
  onSend,
  railData,
  canLoadEarlier,
  cappedEarlier,
  onLoadEarlier,
  onOpenDiary,
}: {
  messages: Message[];
  streaming: boolean;
  onSend: (text: string) => void;
  railData?: ModelView | null; // omit for the live fetch; inject in the demo
  canLoadEarlier?: boolean;
  cappedEarlier?: boolean;
  onLoadEarlier?: () => void;
  onOpenDiary?: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-0 w-full max-w-[112rem] flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <MessageList
          messages={messages}
          streaming={streaming}
          canLoadEarlier={canLoadEarlier}
          cappedEarlier={cappedEarlier}
          onLoadEarlier={onLoadEarlier}
          onOpenDiary={onOpenDiary}
        />
        <Composer onSend={onSend} disabled={streaming} />
      </div>
      <ContextRail
        turns={messages.length}
        data={railData}
        className="hidden w-[19rem] border-l border-line lg:flex xl:w-[21rem] 2xl:w-[22rem]"
      />
    </div>
  );
}
