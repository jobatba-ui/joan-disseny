// Inicia el acceso con GitHub para el panel /admin (Decap CMS).
// Cloudflare Pages ejecuta este archivo en la dirección /api/auth.
// Necesita las variables GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET (ver GUIA_PUBLICACION.md).

export async function onRequestGet({ request, env }) {
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) {
    return new Response(
      'Falta configurar GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET en Cloudflare (Settings > Variables).',
      { status: 500, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' } }
    );
  }

  const url = new URL(request.url);
  const state = crypto.randomUUID();
  const params = new URLSearchParams({
    client_id: env.GITHUB_CLIENT_ID,
    redirect_uri: `${url.origin}/api/callback`,
    // Se ignora el permiso que pida el navegador: lo decide el servidor.
    // "public_repo" basta para un repositorio público y es el permiso más reducido posible.
    scope: env.GITHUB_SCOPE || 'public_repo',
    state,
  });

  return new Response(null, {
    status: 302,
    headers: {
      Location: `https://github.com/login/oauth/authorize?${params}`,
      'Set-Cookie': `oauth_state=${state}; Path=/api; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
      'Cache-Control': 'no-store',
    },
  });
}
