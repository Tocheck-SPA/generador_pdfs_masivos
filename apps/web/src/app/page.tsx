import { redirect } from "next/navigation";
import { auth, signOut } from "@/auth";
import Dashboard from "@/components/Dashboard";

export default async function HomePage() {
  const session = await auth();
  if (!session?.user?.email) {
    redirect("/login");
  }

  async function doSignOut() {
    "use server";
    await signOut({ redirectTo: "/login" });
  }

  return (
    <>
      <header className="app-header">
        <span className="app-brand">ToCheck · Reportes</span>
        <div className="app-header-right">
          <span className="app-user-email">{session.user.email}</span>
          <form action={doSignOut}>
            <button type="submit" className="btn btn-secondary btn-sm">
              Cerrar sesión
            </button>
          </form>
        </div>
      </header>
      <main className="app-main">
        <Dashboard />
      </main>
    </>
  );
}
