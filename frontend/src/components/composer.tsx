"use client";

import { useRef, useState } from "react";

export function Composer({
  onSend,
  onAttach,
}: {
  onSend: (content: string) => void;
  onAttach: (file: File) => void;
}) {
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onSend(text);
    setText("");
  }

  function pickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onAttach(file);
    e.target.value = "";
  }

  return (
    <form onSubmit={submit} className="flex items-center gap-2 px-4 py-3">
      <button
        type="button"
        title="Attach image / video / file"
        onClick={() => fileRef.current?.click()}
        className="flex h-9 w-9 items-center justify-center rounded-md bg-bg-panel text-lg text-text-muted"
      >
        📎
      </button>
      <input ref={fileRef} type="file" className="hidden" onChange={pickFile} />
      <input
        className="flex-1 rounded-md border border-surface-DEFAULT bg-bg-panel px-3 py-2 text-sm text-text-DEFAULT"
        placeholder="Type a message…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) submit(e);
        }}
      />
      <button
        type="submit"
        disabled={!text.trim()}
        className="flex h-9 w-9 items-center justify-center rounded-md bg-ac-DEFAULT text-white"
      >
        ➤
      </button>
    </form>
  );
}