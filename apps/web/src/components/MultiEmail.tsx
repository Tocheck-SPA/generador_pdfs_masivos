"use client";

import { useState, type KeyboardEvent, type ClipboardEvent } from "react";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

/** Split a pasted/typed blob into candidate emails on separators + whitespace. */
function splitCandidates(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export interface MultiEmailProps {
  emails: string[];
  onChange: (emails: string[]) => void;
  max?: number;
  placeholder?: string;
  id?: string;
}

export default function MultiEmail({
  emails,
  onChange,
  max = 20,
  placeholder = "Escribe un correo y presiona Enter",
  id,
}: MultiEmailProps) {
  const [draft, setDraft] = useState("");

  function commit(raw: string): void {
    const candidates = splitCandidates(raw);
    if (candidates.length === 0) return;
    const next = [...emails];
    const existing = new Set(next.map((e) => e.toLowerCase()));
    for (const candidate of candidates) {
      if (next.length >= max) break;
      const key = candidate.toLowerCase();
      if (existing.has(key)) continue;
      existing.add(key);
      next.push(candidate);
    }
    onChange(next);
    setDraft("");
  }

  function remove(index: number): void {
    onChange(emails.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter" || e.key === "," || e.key === ";" || e.key === " ") {
      if (draft.trim()) {
        e.preventDefault();
        commit(draft);
      } else if (e.key !== " ") {
        e.preventDefault();
      }
      return;
    }
    if (e.key === "Backspace" && draft === "" && emails.length > 0) {
      remove(emails.length - 1);
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>): void {
    const text = e.clipboardData.getData("text");
    if (/[\s,;]/.test(text)) {
      e.preventDefault();
      commit(text);
    }
  }

  const atMax = emails.length >= max;

  return (
    <div className="multiemail">
      {emails.map((email, index) => {
        const valid = isValidEmail(email);
        return (
          <span
            key={`${email}-${index}`}
            className={`email-tag ${valid ? "valid" : "invalid"}`}
            data-testid="email-tag"
            data-valid={valid}
          >
            {email}
            <button
              type="button"
              className="email-tag-remove"
              aria-label={`Quitar ${email}`}
              onClick={() => remove(index)}
            >
              ×
            </button>
          </span>
        );
      })}
      <input
        id={id}
        type="text"
        className="multiemail-input"
        value={draft}
        placeholder={emails.length === 0 ? placeholder : ""}
        disabled={atMax}
        aria-label="Destinatarios"
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => draft.trim() && commit(draft)}
      />
    </div>
  );
}
