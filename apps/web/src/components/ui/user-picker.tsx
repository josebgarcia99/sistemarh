"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { fieldClass } from "@/components/ui/styles";
import { type DirectoryEntry, searchDirectory } from "@/lib/api/vacancies";

type UserPickerProps = {
  label: string;
  selected: DirectoryEntry | null;
  onSelect: (user: DirectoryEntry | null) => void;
  /** Identificadores que no deben ofrecerse (por ejemplo, quien ya tiene acceso). */
  excludeIds?: string[];
};

/** Busca usuarios activos por nombre o correo y permite elegir uno. */
export function UserPicker({ label, selected, onSelect, excludeIds = [] }: UserPickerProps) {
  const inputId = useId();
  const [search, setSearch] = useState("");
  const term = search.trim();
  const { data, isFetching } = useQuery({
    queryKey: ["directory", term],
    queryFn: ({ signal }) => searchDirectory(term, signal),
    enabled: term.length >= 2 && !selected,
    staleTime: 30_000,
  });
  const results = (data ?? []).filter((user) => !excludeIds.includes(user.id));

  if (selected) {
    return (
      <div className="flex flex-col gap-2">
        <span className="text-sm text-ink-muted">{label}</span>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-tile bg-surface-soft px-5 py-3">
          <span className="flex flex-col">
            <span className="font-medium">{selected.full_name}</span>
            <span className="text-sm text-ink-muted">{selected.email}</span>
          </span>
          <button
            type="button"
            className="min-h-11 rounded-full px-4 underline"
            onClick={() => {
              onSelect(null);
              setSearch("");
            }}
          >
            Cambiar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm text-ink-muted">
        {label}
      </label>
      <input
        id={inputId}
        type="search"
        autoComplete="off"
        placeholder="Escribe al menos 2 letras del nombre o correo"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className={fieldClass}
      />
      {term.length >= 2 && (
        <ul aria-label={`Resultados para ${label}`} className="flex flex-col gap-1">
          {results.map((user) => (
            <li key={user.id}>
              <button
                type="button"
                onClick={() => onSelect(user)}
                className="flex min-h-11 w-full flex-col rounded-2xl bg-surface-soft px-4 py-2 text-left hover:bg-neutral-soft"
              >
                <span className="font-medium">{user.full_name}</span>
                <span className="text-sm text-ink-muted">{user.email}</span>
              </button>
            </li>
          ))}
          {!isFetching && results.length === 0 && (
            <li className="px-1 text-sm text-ink-muted">Ningún usuario activo coincide.</li>
          )}
        </ul>
      )}
    </div>
  );
}
