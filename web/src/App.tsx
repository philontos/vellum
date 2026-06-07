import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { useChat } from "./hooks/useChat";

export default function App() {
  const { messages, streaming, send } = useChat();
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <header className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
        Vellum
      </header>
      <MessageList messages={messages} />
      <Composer onSend={send} disabled={streaming} />
    </div>
  );
}
