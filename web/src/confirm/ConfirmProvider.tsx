import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ConfirmDialog, type ConfirmTone } from "../components/ui/ConfirmDialog";

export type ConfirmOptions = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone?: ConfirmTone;
};

type ConfirmRequest = ConfirmOptions & {
  id: number;
  resolve: (confirmed: boolean) => void;
  returnFocus: HTMLElement | null;
};

type Confirm = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Confirm | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ConfirmRequest | null>(null);
  const activeRef = useRef<ConfirmRequest | null>(null);
  const queueRef = useRef<ConfirmRequest[]>([]);
  const nextId = useRef(1);

  const confirm = useCallback<Confirm>((options) => new Promise((resolve) => {
    const request: ConfirmRequest = {
      ...options,
      id: nextId.current++,
      resolve,
      returnFocus:
        activeRef.current?.returnFocus ?? (
          typeof document !== "undefined" && document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null
        ),
    };
    if (activeRef.current) {
      queueRef.current.push(request);
      return;
    }
    activeRef.current = request;
    setActive(request);
  }), []);

  const settle = useCallback((confirmed: boolean) => {
    const request = activeRef.current;
    if (!request) return;
    request.resolve(confirmed);
    const next = queueRef.current.shift() ?? null;
    activeRef.current = next;
    setActive(next);
    if (!next && request.returnFocus?.isConnected) {
      requestAnimationFrame(() => request.returnFocus?.focus());
    }
  }, []);

  useEffect(() => () => {
    activeRef.current?.resolve(false);
    for (const request of queueRef.current) request.resolve(false);
    activeRef.current = null;
    queueRef.current = [];
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {active && (
        <ConfirmDialog
          key={active.id}
          title={active.title}
          message={active.message}
          confirmLabel={active.confirmLabel}
          cancelLabel={active.cancelLabel}
          tone={active.tone}
          onConfirm={() => settle(true)}
          onCancel={() => settle(false)}
        />
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Confirm {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error("useConfirm must be used within <ConfirmProvider>");
  return confirm;
}
