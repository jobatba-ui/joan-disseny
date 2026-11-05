// Termina el acceso con GitHub y entrega el permiso al panel /admin (Decap CMS).
// Cloudflare Pages ejecuta este archivo en la dirección /api/callback.

function respond(kind, payload, httpStatus) {
  const message = `authorization:github:${kind}:${JSON.stringify(payload)}`;
  const safeMessage = JSON.stringify(message).replace(/</g, '\\u003c');
  const text = kind === 'success'
    ? 'Acceso correcto. Puedes cerrar esta ventana.'
    : 'No se ha podido iniciar sesión. Cierra esta ventana y vuelve a intentarlo.';
  const html = `<!doctype html><html lang="es"><meta charset="utf-8"><title>Acceso</title>
<body style="font-family:sans-serif;padding:2rem"><p>${text}</p>
<script>
(function () {
  var message = ${safeMessage};
  var origin = window.location.origin;
  if (!window.opener) { return; }
  function receive(e) {
    if (e.origin !== origin) { return; }
    window.opener.postMessage(message, origin);
    window.removeEventListener('message', receive, false);
  }
  window.addEventListener('message', receive, false);
  window.opener.postMessage('authorizing:github', origin);
})();
</script></body></html>`;
  return new Response(html, {
    status: httpStatus,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'Set-Cookie': 'oauth_state=; Path=/api; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
    },
  });
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const cookie = (request.headers.get('Cookie') || '')
    .split(';').map((s) => s.trim()).find((s) => s.startsWith('oauth_state='));
  const saved = cookie ? cookie.slice('oauth_state='.length) : '';

  // Protección contra accesos falsificados: el "state" debe coincidir con el que guardamos al empezar.
  if (!code || !state || !saved || state !== saved) {
    return respond('error', { message: 'La sesión de acceso no es válida.' }, 400);
  }
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) {
    return respond('error', { message: 'Falta configurar las variables de GitHub en Cloudflare.' }, 500);
  }

  let data;
  try {
    const response = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'User-Agent': 'joan-disseny-cms' },
      body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code }),
    });
    data = await response.json();
  } catch (err) {
    return respond('error', { message: 'No se ha podido contactar con GitHub.' }, 502);
  }

  if (!data || !data.access_token) {
    return respond('error', { message: (data && data.error_description) || 'GitHub no ha concedido el acceso.' }, 401);
  }
  return respond('success', { token: data.access_token, provider: 'github' }, 200);
}
