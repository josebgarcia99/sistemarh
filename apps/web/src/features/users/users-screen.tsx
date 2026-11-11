"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  cardClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import { ROLE_LABELS, type User } from "@/lib/api/auth";
import { describeError } from "@/lib/api/client";
import { listUsers } from "@/lib/api/users";
import { CreateUserForm, EditUserForm, ResetPasswordForm, ToggleActiveForm } from "./user-forms";

const PAGE_SIZE = 10;

type Dialog =
  | { kind: "create" }
  | { kind: "edit"; user: User }
  | { kind: "reset"; user: User }
  | { kind: "toggle"; user: User };

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string | null): string {
  return value ? dateFormat.format(new Date(value)) : "Sin actividad";
}

// La tabla exige entradas estables: se definen fuera del componente.
const features = tableFeatures({});
const column = createColumnHelper<typeof features, User>();
const NO_USERS: User[] = [];

export function UsersScreen() {
  const { user: currentUser } = useSession();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isAdmin = currentUser?.role === "ADMINISTRADOR";
  const currentUserId = currentUser?.id;
  const { data, error, isPending } = useQuery({
    queryKey: ["users", { search, page }],
    queryFn: ({ signal }) => listUsers({ search, page, pageSize: PAGE_SIZE }, signal),
    placeholderData: keepPreviousData,
    enabled: isAdmin,
  });

  const columns = useMemo(
    () =>
      column.columns([
        column.accessor("full_name", {
          header: "Nombre",
          cell: ({ row }) => (
            <span className="flex flex-col">
              <span className="font-medium">{row.original.full_name}</span>
              <span className="text-sm text-ink-muted">{row.original.email}</span>
            </span>
          ),
        }),
        column.accessor("role", {
          header: "Rol",
          cell: ({ row }) => ROLE_LABELS[row.original.role],
        }),
        column.accessor("is_active", {
          header: "Estado",
          cell: ({ row }) =>
            row.original.is_active ? (
              <span className="rounded-full bg-accent-blue-soft px-3 py-1 text-sm text-accent-blue-ink">
                Activo
              </span>
            ) : (
              <span className="rounded-full bg-neutral-soft px-3 py-1 text-sm text-neutral-ink">
                Dado de baja
              </span>
            ),
        }),
        column.accessor("last_activity_at", {
          header: "Última actividad",
          cell: ({ row }) => (
            <span className="text-ink-muted">{formatDate(row.original.last_activity_at)}</span>
          ),
        }),
        column.display({
          id: "actions",
          header: "Acciones",
          cell: ({ row }) => {
            const user = row.original;
            return (
              <span className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={secondaryButtonClass}
                  aria-label={`Editar a ${user.full_name}`}
                  onClick={() => setDialog({ kind: "edit", user })}
                >
                  Editar
                </button>
                <button
                  type="button"
                  className={secondaryButtonClass}
                  aria-label={`Restablecer la contraseña de ${user.full_name}`}
                  onClick={() => setDialog({ kind: "reset", user })}
                >
                  Contraseña
                </button>
                {user.id !== currentUserId && (
                  <button
                    type="button"
                    className={secondaryButtonClass}
                    aria-label={`${user.is_active ? "Dar de baja" : "Reactivar"} a ${user.full_name}`}
                    onClick={() => setDialog({ kind: "toggle", user })}
                  >
                    {user.is_active ? "Dar de baja" : "Reactivar"}
                  </button>
                )}
              </span>
            );
          },
        }),
      ]),
    [currentUserId],
  );

  const table = useTable({ features, columns, data: data?.items ?? NO_USERS });

  if (!isAdmin) {
    return (
      <div role="alert" className={cardClass}>
        <h1 className="text-2xl font-medium">Sin acceso</h1>
        <p className="mt-1 text-ink-muted">
          La administración de usuarios es solo para administradores.
        </p>
      </div>
    );
  }

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function finish(message: string) {
    setDialog(null);
    setNotice(message);
    void queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Usuarios</h1>
          <p className="mt-2 text-ink-muted">
            Tú creas las cuentas y defines sus contraseñas. El sistema no envía correos.
          </p>
        </div>
        <button
          type="button"
          className={primaryButtonClass}
          onClick={() => setDialog({ kind: "create" })}
        >
          Nuevo usuario
        </button>
      </div>

      {notice && (
        <p role="status" className="rounded-tile bg-accent-blue-soft px-5 py-4 text-accent-blue-ink">
          {notice}
        </p>
      )}

      <section className={`${cardClass} flex flex-col gap-5`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label htmlFor="user-search" className="sr-only">
            Buscar por nombre o correo
          </label>
          <input
            id="user-search"
            type="search"
            placeholder="Buscar por nombre o correo"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className={`${fieldClass} max-w-sm`}
          />
          <p className="text-sm text-ink-muted">
            {total === 1 ? "1 usuario" : `${total} usuarios`}
          </p>
        </div>

        {error ? (
          <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
            {describeError(error)}
          </p>
        ) : isPending ? (
          <p role="status" className="text-ink-muted">
            Cargando usuarios…
          </p>
        ) : total === 0 ? (
          <p className="text-ink-muted">
            {search ? "Ningún usuario coincide con la búsqueda." : "Todavía no hay usuarios."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-separate border-spacing-y-1.5 text-left">
              <thead>
                {table.getHeaderGroups().map((group) => (
                  <tr key={group.id}>
                    {group.headers.map((header) => (
                      <th
                        key={header.id}
                        scope="col"
                        className="px-4 pb-1 text-sm font-normal text-ink-muted"
                      >
                        <table.FlexRender header={header} />
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getAllCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="bg-surface px-4 py-3 first:rounded-l-3xl last:rounded-r-3xl"
                      >
                        <table.FlexRender cell={cell} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pageCount > 1 && (
          <nav aria-label="Paginación" className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              className={secondaryButtonClass}
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Anterior
            </button>
            <span className="text-sm text-ink-muted">
              Página {page} de {pageCount}
            </span>
            <button
              type="button"
              className={secondaryButtonClass}
              disabled={page >= pageCount}
              onClick={() => setPage((p) => p + 1)}
            >
              Siguiente
            </button>
          </nav>
        )}
      </section>

      {dialog?.kind === "create" && (
        <Modal title="Nuevo usuario" onClose={() => setDialog(null)}>
          <CreateUserForm onDone={finish} onCancel={() => setDialog(null)} />
        </Modal>
      )}
      {dialog?.kind === "edit" && (
        <Modal
          title="Editar usuario"
          description={dialog.user.email}
          onClose={() => setDialog(null)}
        >
          <EditUserForm user={dialog.user} onDone={finish} onCancel={() => setDialog(null)} />
        </Modal>
      )}
      {dialog?.kind === "reset" && (
        <Modal
          title="Restablecer contraseña"
          description={`${dialog.user.full_name} deberá entrar con la contraseña nueva. Sus sesiones abiertas se cierran.`}
          onClose={() => setDialog(null)}
        >
          <ResetPasswordForm user={dialog.user} onDone={finish} onCancel={() => setDialog(null)} />
        </Modal>
      )}
      {dialog?.kind === "toggle" && (
        <Modal
          title={dialog.user.is_active ? "Dar de baja" : "Reactivar usuario"}
          description={
            dialog.user.is_active
              ? `${dialog.user.full_name} perderá el acceso y sus sesiones se cerrarán. Su cuenta y su historial se conservan.`
              : `${dialog.user.full_name} podrá volver a entrar con su contraseña actual.`
          }
          onClose={() => setDialog(null)}
        >
          <ToggleActiveForm user={dialog.user} onDone={finish} onCancel={() => setDialog(null)} />
        </Modal>
      )}
    </>
  );
}
