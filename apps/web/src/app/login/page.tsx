import { AuthError } from "next-auth";
import { redirect } from "next/navigation";
import { signIn } from "@/auth";

export const metadata = { title: "Iniciar sesión · ToCheck Reportes" };

const hasGoogle = Boolean(
  process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
);
const devMode = process.env.AUTH_DEV_MODE === "true" || !hasGoogle;

function safeCallback(raw: string | undefined): string {
  if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return "/";
}

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string; callbackUrl?: string };
}) {
  const callbackUrl = safeCallback(searchParams.callbackUrl);
  const showError = Boolean(searchParams.error);

  async function googleSignIn() {
    "use server";
    await signIn("google", { redirectTo: callbackUrl });
  }

  async function devSignIn(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "").trim();
    try {
      await signIn("dev-credentials", { email, redirectTo: callbackUrl });
    } catch (error) {
      if (error instanceof AuthError) {
        redirect(`/login?error=denied`);
      }
      throw error;
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <h1 className="content-title">ToCheck · Reportes</h1>
        <p className="content-subtitle">Inicia sesión para continuar.</p>

        {showError && (
          <div className="form-alert">
            No pudimos iniciar sesión con ese correo. Verifica que tengas acceso.
          </div>
        )}

        {hasGoogle && (
          <form action={googleSignIn}>
            <button type="submit" className="btn btn-primary">
              Iniciar sesión con Google
            </button>
          </form>
        )}

        {hasGoogle && devMode && <div className="login-divider">o</div>}

        {devMode && (
          <form action={devSignIn}>
            <div className="field" style={{ marginBottom: 12 }}>
              <input
                type="email"
                name="email"
                required
                placeholder="tu.correo@tocheck.cl"
                className="form-control"
                aria-label="Correo"
              />
            </div>
            <button type="submit" className="btn btn-primary">
              Entrar
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
