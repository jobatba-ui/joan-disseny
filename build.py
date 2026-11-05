#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JOAN · generador del sitio web (valenciano, castellano e inglés).

Lee los textos y proyectos de la carpeta `content/` (que edita el panel /admin),
optimiza las imágenes y escribe la web terminada en `dist/`.

Cloudflare Pages lo ejecuta solo cada vez que se guarda un cambio:
    pip install -r requirements.txt && python build.py

Variables de entorno (se configuran en Cloudflare, no hace falta tocar código):
    SITE_URL      Dirección pública de la web, sin barra final.
    GITHUB_REPO   Repositorio donde se guardan los contenidos (usuario/repositorio).
    GITHUB_BRANCH Rama del repositorio (por defecto: main).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
TEMPLATES = ROOT / "templates"
DIST = ROOT / "dist"

SITE_URL = os.environ.get("SITE_URL", "https://joan-disseny.pages.dev").rstrip("/")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "TU-USUARIO/joan-disseny")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# --------------------------------------------------------------------------
# Idiomas y rutas
# --------------------------------------------------------------------------
LANGS = ["va", "es", "en"]  # el primero es el idioma principal (raíz de la web)
DEFAULT_LANG = "va"
LANG_META = {
    "va": {"label": "Valencià", "short": "VA", "html": "ca-valencia", "hreflang": "ca", "og": "ca_ES", "path": ""},
    "es": {"label": "Castellano", "short": "ES", "html": "es", "hreflang": "es", "og": "es_ES", "path": "es"},
    "en": {"label": "English", "short": "EN", "html": "en", "hreflang": "en", "og": "en_GB", "path": "en"},
}
ROUTE_NAMES = {
    "projects": {"va": "projectes", "es": "proyectos", "en": "projects"},
    "services": {"va": "serveis", "es": "servicios", "en": "services"},
    "about": {"va": "sobre-mi", "es": "sobre-mi", "en": "about"},
    "contact": {"va": "contacte", "es": "contacto", "en": "contact"},
    "legal": {"va": "avis-legal", "es": "aviso-legal", "en": "legal"},
}

CATEGORIES = {
    "branding": {"va": "Branding", "es": "Branding", "en": "Branding"},
    "identidad": {"va": "Identitat visual", "es": "Identidad visual", "en": "Visual identity"},
    "editorial": {"va": "Disseny editorial", "es": "Diseño editorial", "en": "Editorial design"},
    "packaging": {"va": "Packaging", "es": "Packaging", "en": "Packaging"},
    "cartel": {"va": "Cartelleria", "es": "Cartelería", "en": "Poster design"},
    "digital": {"va": "Disseny digital", "es": "Diseño digital", "en": "Digital design"},
}
CATEGORY_LABELS_ES = {
    "branding": "Branding",
    "identidad": "Identidad visual",
    "editorial": "Diseño editorial",
    "packaging": "Packaging",
    "cartel": "Cartelería",
    "digital": "Diseño digital",
}

# Textos fijos de la interfaz (menús, botones, etiquetas)
T = {
    "nav_projects": {"va": "Projectes", "es": "Proyectos", "en": "Projects"},
    "nav_services": {"va": "Serveis", "es": "Servicios", "en": "Services"},
    "nav_about": {"va": "Sobre mi", "es": "Sobre mí", "en": "About"},
    "nav_contact": {"va": "Contacte", "es": "Contacto", "en": "Contact"},
    "menu": {"va": "Menú", "es": "Menú", "en": "Menu"},
    "skip": {"va": "Anar al contingut", "es": "Saltar al contenido", "en": "Skip to content"},
    "lang_label": {"va": "Idioma", "es": "Idioma", "en": "Language"},
    "featured": {"va": "Projectes seleccionats", "es": "Proyectos seleccionados", "en": "Selected projects"},
    "see_all": {"va": "Tots els projectes", "es": "Todos los proyectos", "en": "All projects"},
    "back_projects": {"va": "Projectes", "es": "Proyectos", "en": "Projects"},
    "filter_all": {"va": "Tots", "es": "Todos", "en": "All"},
    "filter_label": {"va": "Filtrar per categoria", "es": "Filtrar por categoría", "en": "Filter by category"},
    "category": {"va": "Categoria", "es": "Categoría", "en": "Category"},
    "year": {"va": "Any", "es": "Año", "en": "Year"},
    "client": {"va": "Client", "es": "Cliente", "en": "Client"},
    "description": {"va": "El projecte", "es": "El proyecto", "en": "The project"},
    "context": {"va": "Context", "es": "Contexto", "en": "Context"},
    "process": {"va": "Procés creatiu", "es": "Proceso creativo", "en": "Creative process"},
    "applications": {"va": "Aplicacions", "es": "Aplicaciones", "en": "Applications"},
    "gallery": {"va": "Imatges del projecte", "es": "Imágenes del proyecto", "en": "Project images"},
    "prev": {"va": "Projecte anterior", "es": "Proyecto anterior", "en": "Previous project"},
    "next": {"va": "Projecte següent", "es": "Proyecto siguiente", "en": "Next project"},
    "project_nav": {"va": "Més projectes", "es": "Más proyectos", "en": "More projects"},
    "empty_projects": {"va": "Aviat hi haurà projectes nous.", "es": "Pronto habrá nuevos proyectos.", "en": "New projects coming soon."},
    "philosophy": {"va": "Filosofia de treball", "es": "Filosofía de trabajo", "en": "Working philosophy"},
    "specialities": {"va": "Especialitats", "es": "Especialidades", "en": "Specialities"},
    "see_projects": {"va": "Veure projectes", "es": "Ver proyectos", "en": "See projects"},
    "contact_intro": {"va": "Tens un projecte en ment? Parlem-ne.", "es": "¿Tienes un proyecto en mente? Hablemos.", "en": "Have a project in mind? Let's talk."},
    "contact_direct": {"va": "Escriu-me directament", "es": "Escríbeme directamente", "en": "Write to me directly"},
    "form_title": {"va": "O envia'm un missatge", "es": "O envíame un mensaje", "en": "Or send me a message"},
    "form_name": {"va": "Nom", "es": "Nombre", "en": "Name"},
    "form_email": {"va": "Correu electrònic", "es": "Correo electrónico", "en": "Email"},
    "form_message": {"va": "Missatge", "es": "Mensaje", "en": "Message"},
    "form_send": {"va": "Enviar missatge", "es": "Enviar mensaje", "en": "Send message"},
    "form_sending": {"va": "Enviant…", "es": "Enviando…", "en": "Sending…"},
    "form_ok": {"va": "Missatge enviat. Gràcies, et respondré aviat.", "es": "Mensaje enviado. Gracias, te responderé pronto.", "en": "Message sent. Thank you, I'll reply soon."},
    "form_err": {"va": "No s'ha pogut enviar. Escriu-me directament per correu.", "es": "No se ha podido enviar. Escríbeme directamente por correo.", "en": "Could not send. Please email me directly."},
    "consent": {"va": "Accepte que s'usen les meues dades per a respondre a aquest missatge.", "es": "Acepto que se usen mis datos para responder a este mensaje.", "en": "I agree that my data may be used to reply to this message."},
    "legal": {"va": "Avís legal i privacitat", "es": "Aviso legal y privacidad", "en": "Legal notice & privacy"},
    "privacy_link": {"va": "Privacitat", "es": "Privacidad", "en": "Privacy"},
    "not_found": {"va": "Pàgina no trobada", "es": "Página no encontrada", "en": "Page not found"},
    "back_home": {"va": "Tornar a l'inici", "es": "Volver al inicio", "en": "Back to home"},
    "default_desc": {"va": "Disseny gràfic independent.", "es": "Diseño gráfico independiente.", "en": "Independent graphic design."},
}

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"AVISO: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "img"


def load_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        warn(f"{path.name}: el archivo no es válido y se ha ignorado ({exc}).")
        return default


def tr(value, lang: str) -> str:
    """Texto en el idioma pedido; si falta, usa valenciano, castellano o inglés."""
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for code in [lang] + [l for l in LANGS if l != lang]:
        text = value.get(code)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def tri_flat(item: dict, base: str) -> dict:
    """Convierte title_va / title_es / title_en en {'va':…, 'es':…, 'en':…}."""
    return {l: (item.get(f"{base}_{l}") or "") for l in LANGS}


def has_text(value) -> bool:
    return any(tr(value, l) for l in LANGS)


def paragraphs(text) -> Markup:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return Markup("")
    blocks = re.split(r"\n\s*\n", text)
    html = "".join("<p>%s</p>" % str(escape(b.strip())).replace("\n", "<br>") for b in blocks if b.strip())
    return Markup(html)


def shorten(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.")
    return cut + "…"


def jsonld(obj) -> Markup:
    return Markup(json.dumps(obj, ensure_ascii=False).replace("</", "<\\/"))


# --------------------------------------------------------------------------
# Imágenes: se generan versiones WebP de varios tamaños
# --------------------------------------------------------------------------
WIDTHS = [480, 800, 1200, 1600, 2000, 2400]
MAX_W = 2400
IMG_CACHE: dict = {}


def web_to_file(web_path: str):
    candidate = (STATIC / str(web_path).lstrip("/")).resolve()
    if STATIC.resolve() not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def process_image(web_path):
    if not web_path or not isinstance(web_path, str):
        return None
    if web_path in IMG_CACHE:
        return IMG_CACHE[web_path]
    result = None
    src = web_to_file(web_path)
    if src is None:
        warn(f"No se encuentra la imagen {web_path}")
    else:
        try:
            data = src.read_bytes()
            digest = hashlib.sha1(data).hexdigest()[:8]
            stem = slugify(src.stem)[:40]
            out_dir = DIST / "img"
            out_dir.mkdir(parents=True, exist_ok=True)
            ext = src.suffix.lower()
            if ext == ".svg":
                name = f"{stem}-{digest}.svg"
                (out_dir / name).write_bytes(data)
                result = {"variants": [(0, f"/img/{name}")], "src": f"/img/{name}", "width": None, "height": None}
            else:
                with Image.open(src) as im:
                    if getattr(im, "is_animated", False):
                        name = f"{stem}-{digest}{ext}"
                        shutil.copyfile(src, out_dir / name)
                        w, h = im.size
                        result = {"variants": [(w, f"/img/{name}")], "src": f"/img/{name}", "width": w, "height": h}
                    else:
                        im = ImageOps.exif_transpose(im)
                        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
                        im = im.convert("RGBA" if has_alpha else "RGB")
                        ow, oh = im.size
                        widths = sorted({w for w in WIDTHS if w < ow} | {min(ow, MAX_W)})
                        variants = []
                        for w in widths:
                            h = max(1, round(oh * w / ow))
                            name = f"{stem}-{digest}-{w}.webp"
                            target = out_dir / name
                            if not target.exists():
                                im.resize((w, h), Image.LANCZOS).save(target, "WEBP", quality=86, method=5)
                            variants.append((w, f"/img/{name}"))
                        top = widths[-1]
                        result = {
                            "variants": variants,
                            "src": variants[-1][1],
                            "width": top,
                            "height": max(1, round(oh * top / ow)),
                        }
        except Exception as exc:  # imagen corrupta o formato raro: no rompe la web
            warn(f"No se ha podido procesar la imagen {web_path}: {exc}")
    IMG_CACHE[web_path] = result
    return result


def og_image(web_path):
    """JPEG de 1200×630 para compartir en redes. Devuelve URL absoluta o ''."""
    src = web_to_file(web_path) if web_path else None
    if src is None or src.suffix.lower() == ".svg":
        return ""
    try:
        digest = hashlib.sha1(src.read_bytes()).hexdigest()[:8]
        name = f"og-{slugify(src.stem)[:30]}-{digest}.jpg"
        out_dir = DIST / "img"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / name
        if not target.exists():
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                ImageOps.fit(im, (1200, 630), Image.LANCZOS).save(target, "JPEG", quality=85, optimize=True)
        return f"{SITE_URL}/img/{name}"
    except Exception as exc:
        warn(f"No se ha podido crear la imagen para compartir de {web_path}: {exc}")
        return ""


def img_tag(image, alt="", sizes="100vw", eager=False, cls=""):
    info = process_image(image) if isinstance(image, str) else image
    if not info:
        return Markup("")
    parts = [f'src="{escape(info["src"])}"']
    real = [(w, u) for w, u in info["variants"] if w]
    if len(real) > 1:
        parts.append('srcset="%s"' % escape(", ".join(f"{u} {w}w" for w, u in real)))
        parts.append(f'sizes="{escape(sizes)}"')
    if info.get("width") and info.get("height"):
        parts.append(f'width="{info["width"]}" height="{info["height"]}"')
    parts.append(f'alt="{escape(alt or "")}"')
    if eager:
        parts.append('fetchpriority="high"')
    else:
        parts.append('loading="lazy" decoding="async"')
    if cls:
        parts.append(f'class="{escape(cls)}"')
    return Markup("<img " + " ".join(parts) + ">")


# --------------------------------------------------------------------------
# Contenido
# --------------------------------------------------------------------------
def load_site() -> dict:
    defaults = {
        "studio_name": "JOAN",
        "email": "",
        "instagram": "",
        "location": "",
        "tagline": {},
        "seo_description": {},
        "form_key": "",
        "share_image": "",
    }
    data = load_json(CONTENT / "site.json", {})
    if isinstance(data, dict):
        defaults.update({k: v for k, v in data.items() if v not in (None, "")})
    return defaults


def load_projects() -> list[dict]:
    projects = []
    folder = CONTENT / "projects"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        data = load_json(path, None)
        if not isinstance(data, dict) or data.get("published") is False:
            continue
        if not str(data.get("title", "")).strip():
            warn(f"{path.name}: el proyecto no tiene nombre y no se publica.")
            continue
        data["slug"] = path.stem
        data["title"] = str(data["title"]).strip()
        data["category"] = data.get("category") or ""
        if data["category"] and data["category"] not in CATEGORIES:
            warn(f"{path.name}: categoría desconocida «{data['category']}».")
        gallery = []
        for item in data.get("gallery") or []:
            if isinstance(item, dict) and item.get("image"):
                gallery.append({
                    "image": item["image"],
                    "layout": "half" if item.get("layout") == "half" else "full",
                    "alt": (item.get("alt") or "").strip(),
                })
        data["gallery"] = gallery
        data["cover"] = data.get("cover") or (gallery[0]["image"] if gallery else "")
        if not data["cover"]:
            warn(f"{path.name}: el proyecto no tiene imagen de portada.")
        projects.append(data)
    return projects


def order_projects(projects: list[dict], order_slugs: list[str]) -> list[dict]:
    by_slug = {p["slug"]: p for p in projects}
    ordered, seen = [], set()
    for slug in order_slugs or []:
        if slug in by_slug and slug not in seen:
            ordered.append(by_slug[slug])
            seen.add(slug)
    rest = [p for p in projects if p["slug"] not in seen]
    rest.sort(key=lambda p: (str(p.get("year") or ""), p["title"].lower()), reverse=True)
    return ordered + rest


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
def path_for(lang: str, route: str = "home", slug: str | None = None) -> str:
    prefix = LANG_META[lang]["path"]
    parts = [prefix] if prefix else []
    if route == "project":
        parts += [ROUTE_NAMES["projects"][lang], quote(slug or "")]
    elif route != "home":
        parts.append(ROUTE_NAMES[route][lang])
    return "/" + "/".join(parts) + ("/" if parts else "")


def write_file(path: str, content: str) -> None:
    rel = path.strip("/")
    target = DIST / rel / "index.html" if rel else DIST / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------
# Panel de edición (Decap CMS): la configuración se genera desde aquí
# --------------------------------------------------------------------------
def cms_config() -> dict:
    def tri(label, name, widget="text", hint=None):
        field = {
            "label": label, "name": name, "widget": "object", "required": False,
            "fields": [
                {"label": "Valenciano", "name": "va", "widget": widget, "required": False},
                {"label": "Castellano", "name": "es", "widget": widget, "required": False},
                {"label": "English", "name": "en", "widget": widget, "required": False},
            ],
        }
        if hint:
            field["hint"] = hint
        return field

    def tri_flat_fields(label, base, widget="string"):
        return [
            {"label": f"{label} · Valenciano", "name": f"{base}_va", "widget": widget, "required": False},
            {"label": f"{label} · Castellano", "name": f"{base}_es", "widget": widget, "required": False},
            {"label": f"{label} · English", "name": f"{base}_en", "widget": widget, "required": False},
        ]

    def single_file(name, label, path, fields, description=None):
        entry = {"label": label, "name": name, "file": path, "fields": fields}
        col = {"name": name, "label": label, "files": [entry]}
        if description:
            col["description"] = description
        return col

    project_picker = {
        "label": "Proyecto", "name": "project", "widget": "relation", "collection": "projects",
        "search_fields": ["title"], "value_field": "{{slug}}", "display_fields": ["title"],
    }
    categories = [{"label": CATEGORY_LABELS_ES[k], "value": k} for k in CATEGORIES]
    hint_langs = "Si dejas un idioma vacío, la web mostrará el texto en valenciano."

    projects = {
        "name": "projects", "label": "Proyectos", "label_singular": "Proyecto",
        "description": "Añade, edita o elimina los trabajos que aparecen en la web.",
        "folder": "content/projects", "create": True, "extension": "json", "format": "json",
        "slug": "{{title}}", "identifier_field": "title",
        "summary": "{{title}} · {{year}}",
        "fields": [
            {"label": "Nombre del proyecto", "name": "title", "widget": "string",
             "hint": "Se muestra tal cual en los tres idiomas (por ejemplo, el nombre de la marca o del cliente)."},
            {"label": "Visible en la web", "name": "published", "widget": "boolean", "default": True,
             "hint": "Desmárcalo para ocultar el proyecto sin borrarlo."},
            {"label": "Categoría", "name": "category", "widget": "select", "options": categories},
            {"label": "Año", "name": "year", "widget": "string", "required": False},
            {"label": "Cliente", "name": "client", "widget": "string", "required": False},
            {"label": "Imagen de portada", "name": "cover", "widget": "image",
             "hint": "Mínimo 1600 píxeles de ancho. Máximo 10 MB."},
            tri("Resumen breve", "summary", "text", "Una o dos frases. " + hint_langs),
            tri("Descripción del proyecto", "description", "text", hint_langs),
            tri("Contexto (el encargo)", "context", "text", hint_langs),
            tri("Proceso creativo", "process", "text", hint_langs),
            tri("Aplicaciones", "applications", "text", hint_langs),
            {"label": "Galería de imágenes", "name": "gallery", "widget": "list", "required": False,
             "label_singular": "imagen", "hint": "Arrastra las imágenes para cambiar su orden.",
             "fields": [
                 {"label": "Imagen", "name": "image", "widget": "image", "hint": "Máximo 10 MB."},
                 {"label": "Tamaño en la página", "name": "layout", "widget": "select", "default": "full",
                  "options": [{"label": "Ancho completo", "value": "full"},
                              {"label": "Media anchura (dos por fila)", "value": "half"}]},
                 {"label": "Descripción breve de la imagen", "name": "alt", "widget": "string", "required": False,
                  "hint": "Opcional. Ayuda a personas con lectores de pantalla. Se usa en los tres idiomas."},
             ]},
        ],
    }

    collections = [
        projects,
        single_file("orden", "Orden de los proyectos", "content/order.json", [
            {"label": "Proyectos en orden (arrastra para cambiar el orden)", "name": "projects",
             "widget": "list", "required": False, "field": project_picker,
             "hint": "Los proyectos que no estén en esta lista aparecen después, del más reciente al más antiguo."},
        ], "Cambia el orden en el que aparecen los proyectos."),
        single_file("portada", "Portada", "content/home.json", [
            {"label": "Proyectos destacados en la portada (arrastra para ordenar)", "name": "featured",
             "widget": "list", "required": False, "field": project_picker,
             "hint": "Si lo dejas vacío, se muestran los primeros proyectos del orden general."},
        ], "Proyectos que se ven en la página de inicio."),
        single_file("servicios", "Servicios", "content/services.json", [
            {"label": "Servicios (arrastra para ordenar)", "name": "items", "widget": "list", "required": False,
             "label_singular": "servicio", "summary": "{{fields.title_va}}",
             "hint": "Incluye solo los servicios que respalda tu trabajo real.",
             "fields": tri_flat_fields("Nombre", "title") + tri_flat_fields("Descripción", "description", "text") + [
                 {"label": "Categoría relacionada", "name": "category", "widget": "select", "required": False,
                  "options": categories,
                  "hint": "Opcional. Añade un enlace «Ver proyectos» de esa categoría."}]},
        ], "Los servicios que ofreces."),
        single_file("sobre", "Sobre mí", "content/about.json", [
            {"label": "Foto o retrato", "name": "portrait", "widget": "image", "required": False},
            tri("Presentación", "intro", "text", hint_langs),
            tri("Filosofía de trabajo", "philosophy", "text", hint_langs),
            {"label": "Especialidades", "name": "specialities", "widget": "list", "required": False,
             "label_singular": "especialidad", "summary": "{{fields.name_va}}",
             "fields": tri_flat_fields("Nombre", "name")},
        ], "Presentación personal del diseñador."),
        single_file("contacto", "Contacto y datos generales", "content/site.json", [
            {"label": "Nombre junto al logotipo", "name": "studio_name", "widget": "string"},
            {"label": "Correo electrónico", "name": "email", "widget": "string",
             "hint": "Aparece en la página de contacto."},
            {"label": "Enlace de Instagram", "name": "instagram", "widget": "string", "required": False,
             "hint": "Dirección completa, por ejemplo https://www.instagram.com/tu-usuario/"},
            {"label": "Ciudad", "name": "location", "widget": "string", "required": False},
            tri("Frase de presentación (portada)", "tagline", "string",
                "Una frase que explique a qué te dedicas. " + hint_langs),
            tri("Descripción para buscadores (Google)", "seo_description", "text",
                "Máximo 160 caracteres. " + hint_langs),
            {"label": "Clave del formulario (Web3Forms)", "name": "form_key", "widget": "string", "required": False,
             "hint": "Se obtiene gratis en web3forms.com con tu correo. Si está vacía, el formulario no se muestra."},
            {"label": "Imagen para compartir en redes", "name": "share_image", "widget": "image", "required": False},
        ], "Correo, Instagram, frase de presentación y datos generales."),
        single_file("legal", "Aviso legal y privacidad", "content/legal.json", [
            tri("Texto del aviso legal y la política de privacidad", "text", "text",
                "Si lo rellenas, aparece un enlace en el pie de página y junto al formulario."),
        ], "Texto legal. Debe incluir tus datos como titular."),
    ]

    return {
        "backend": {"name": "github", "repo": GITHUB_REPO, "branch": GITHUB_BRANCH,
                    "base_url": SITE_URL, "auth_endpoint": "api/auth"},
        "locale": "es",
        "site_url": SITE_URL,
        "display_url": SITE_URL,
        "logo_url": f"{SITE_URL}/logo/joan-negro.svg",
        "media_folder": "static/uploads",
        "public_folder": "/uploads",
        "show_preview_links": True,
        "slug": {"encoding": "ascii", "clean_accents": True, "sanitize_replacement": "-"},
        "commit_messages": {
            "create": "Nuevo: {{collection}} «{{slug}}»",
            "update": "Actualizar: {{collection}} «{{slug}}»",
            "delete": "Eliminar: {{collection}} «{{slug}}»",
            "uploadMedia": "Subir imagen «{{path}}»",
            "deleteMedia": "Eliminar imagen «{{path}}»",
        },
        "collections": collections,
    }


# --------------------------------------------------------------------------
# Construcción
# --------------------------------------------------------------------------
def build() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # Archivos estáticos (css, js, logotipos, iconos, admin) y subidas del panel
    shutil.copytree(STATIC, DIST, dirs_exist_ok=True, ignore=shutil.ignore_patterns("uploads", ".DS_Store"))
    uploads = STATIC / "uploads"
    if uploads.is_dir():
        for f in uploads.rglob("*"):
            if not f.is_file() or f.name.startswith("."):
                continue
            if f.stat().st_size > 24 * 1024 * 1024:
                warn(f"{f.name} pesa más de 24 MB y no se publica (Cloudflare no admite archivos tan grandes). Súbela más ligera.")
                continue
            target = DIST / "uploads" / f.relative_to(uploads)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)

    css = (STATIC / "css" / "style.css").read_bytes()
    js = (STATIC / "js" / "main.js").read_bytes()
    assets_v = hashlib.sha1(css + js).hexdigest()[:8]

    site = load_site()
    all_projects = load_projects()
    order = load_json(CONTENT / "order.json", {}).get("projects", [])
    projects = order_projects(all_projects, order)
    by_slug = {p["slug"]: p for p in projects}
    home_cfg = load_json(CONTENT / "home.json", {})
    featured = [by_slug[s] for s in home_cfg.get("featured", []) if s in by_slug] or projects[:6]
    services_raw = load_json(CONTENT / "services.json", {}).get("items", []) or []
    services = [
        {"title": tri_flat(s, "title"), "description": tri_flat(s, "description"), "category": s.get("category") or ""}
        for s in services_raw if isinstance(s, dict) and has_text(tri_flat(s, "title"))
    ]
    about_raw = load_json(CONTENT / "about.json", {})
    about = {
        "portrait": about_raw.get("portrait") or "",
        "intro": about_raw.get("intro") or {},
        "philosophy": about_raw.get("philosophy") or {},
        "specialities": [tri_flat(s, "name") for s in (about_raw.get("specialities") or []) if isinstance(s, dict)],
    }
    has_about = bool(has_text(about["intro"]) or has_text(about["philosophy"]) or about["specialities"])
    legal_text = (load_json(CONTENT / "legal.json", {}).get("text")) or {}
    has_legal = has_text(legal_text)

    cats_present = [c for c in CATEGORIES if any(p["category"] == c for p in projects)]
    for s in services:
        if s["category"] and s["category"] not in cats_present:
            warn(f"El servicio «{tr(s['title'], DEFAULT_LANG)}» está enlazado a una categoría sin proyectos.")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["paragraphs"] = paragraphs
    env.globals["img"] = img_tag

    sitemap: list[dict] = []
    site_name = site["studio_name"]
    site_email = site.get("email", "")
    # Si el nombre es «JOAN» no hay nada más que mostrar; si lleva algo detrás (p. ej. «JOAN Disseny»), eso va como texto pequeño junto al logotipo
    brand_sub = re.sub(r"^\s*joan\b\s*", "", site_name, flags=re.I).strip()

    def common(lang: str) -> dict:
        nav = []
        nav.append({"route": "projects", "label": T["nav_projects"][lang]})
        if services:
            nav.append({"route": "services", "label": T["nav_services"][lang]})
        if has_about:
            nav.append({"route": "about", "label": T["nav_about"][lang]})
        nav.append({"route": "contact", "label": T["nav_contact"][lang]})
        for item in nav:
            item["url"] = path_for(lang, item["route"])
        return {
            "lang": lang, "lm": LANG_META[lang], "langs": LANGS, "LANG_META": LANG_META,
            "t": lambda key, _l=lang: T[key][_l],
            "tr": lambda value, _l=lang: tr(value, _l),
            "url": lambda route="home", slug=None, _l=lang: path_for(_l, route, slug),
            "cat_name": lambda c, _l=lang: CATEGORIES.get(c, {}).get(_l, c),
            "site": site, "nav": nav, "year": date.today().year, "brand_sub": brand_sub,
            "has_legal": has_legal, "site_url": SITE_URL, "assets_v": assets_v,
            "body_class": "", "og_image": "", "jsonld": "", "og_type": "website",
        }

    def render_page(template: str, route: str, make, slug: str | None = None) -> None:
        paths = {l: path_for(l, route, slug) for l in LANGS}
        alternates = {l: SITE_URL + p for l, p in paths.items()}
        for lang in LANGS:
            ctx = common(lang)
            ctx.update(route=route, paths=paths, alternates=alternates, canonical=alternates[lang])
            ctx.update(make(lang))
            write_file(paths[lang], env.get_template(template).render(**ctx))
        sitemap.append(alternates)

    default_og = og_image(site.get("share_image")) or (og_image(projects[0]["cover"]) if projects and projects[0]["cover"] else "")
    org_ld = {"@context": "https://schema.org", "@type": "Organization", "name": site_name, "url": SITE_URL}
    if site_email:
        org_ld["email"] = site_email
    if site.get("instagram"):
        org_ld["sameAs"] = [site["instagram"]]

    def desc(lang: str, *candidates: str) -> str:
        for c in candidates:
            if c:
                return shorten(c)
        return T["default_desc"][lang]

    # Portada
    def make_home(lang):
        tagline = tr(site.get("tagline"), lang)
        seo = tr(site.get("seo_description"), lang)
        return {
            "page_title": f"{site_name} · {tagline or T['default_desc'][lang].rstrip('.')}",
            "page_description": desc(lang, seo, tagline),
            "og_image": default_og, "body_class": "home",
            "tagline": tagline, "featured": featured,
            "jsonld": jsonld(org_ld),
        }
    render_page("home.html", "home", make_home)

    # Listado de proyectos
    def make_projects(lang):
        return {
            "page_title": f"{T['nav_projects'][lang]} · {site_name}",
            "page_description": desc(lang, tr(site.get("seo_description"), lang)),
            "og_image": default_og, "projects": projects,
            "categories": cats_present, "body_class": "page-projects",
        }
    render_page("projects.html", "projects", make_projects)

    # Una página por proyecto
    for index, p in enumerate(projects):
        prev_p = projects[index - 1] if len(projects) > 1 else None
        next_p = projects[(index + 1) % len(projects)] if len(projects) > 1 else None

        def make_project(lang, p=p, prev_p=prev_p, next_p=next_p):
            summary = tr(p.get("summary"), lang)
            description = tr(p.get("description"), lang)
            cover_og = og_image(p["cover"]) if p["cover"] else default_og
            ld = {"@context": "https://schema.org", "@type": "CreativeWork", "name": p["title"],
                  "inLanguage": LANG_META[lang]["hreflang"],
                  "creator": {"@type": "Organization", "name": site_name, "url": SITE_URL}}
            if cover_og:
                ld["image"] = [cover_og]
            if summary or description:
                ld["description"] = shorten(summary or description, 300)
            return {
                "page_title": f"{p['title']} · {site_name}",
                "page_description": desc(lang, summary, description, tr(site.get("seo_description"), lang)),
                "og_image": cover_og, "body_class": "page-project", "og_type": "article",
                "p": p, "prev_p": prev_p, "next_p": next_p,
                "summary": summary,
                "blocks": [(T[k][lang], tr(p.get(k), lang)) for k in ("description", "context", "process", "applications")
                           if tr(p.get(k), lang)],
                "jsonld": jsonld(ld),
            }
        render_page("project.html", "project", make_project, slug=p["slug"])

    # Servicios
    if services:
        def make_services(lang):
            items = [{
                "title": tr(s["title"], lang), "description": tr(s["description"], lang),
                "category": s["category"] if s["category"] in cats_present else "",
            } for s in services]
            return {
                "page_title": f"{T['nav_services'][lang]} · {site_name}",
                "page_description": desc(lang, tr(site.get("seo_description"), lang)),
                "og_image": default_og, "items": items, "body_class": "page-services",
            }
        render_page("services.html", "services", make_services)

    # Sobre mí
    if has_about:
        def make_about(lang):
            intro = tr(about["intro"], lang)
            return {
                "page_title": f"{T['nav_about'][lang]} · {site_name}",
                "page_description": desc(lang, intro, tr(site.get("seo_description"), lang)),
                "og_image": og_image(about["portrait"]) or default_og, "body_class": "page-about",
                "intro": intro, "philosophy": tr(about["philosophy"], lang),
                "specialities": [tr(s, lang) for s in about["specialities"] if tr(s, lang)],
                "portrait": about["portrait"],
            }
        render_page("about.html", "about", make_about)

    # Contacto
    def make_contact(lang):
        ld = dict(org_ld)
        ld["@type"] = "ProfessionalService"
        return {
            "page_title": f"{T['nav_contact'][lang]} · {site_name}",
            "page_description": desc(lang, T["contact_intro"][lang]),
            "og_image": default_og, "body_class": "page-contact", "jsonld": jsonld(ld),
        }
    render_page("contact.html", "contact", make_contact)

    # Aviso legal
    if has_legal:
        def make_legal(lang):
            return {
                "page_title": f"{T['legal'][lang]} · {site_name}",
                "page_description": T["legal"][lang],
                "body_class": "page-legal", "legal": tr(legal_text, lang),
            }
        render_page("legal.html", "legal", make_legal)

    # 404, robots, sitemap, cabeceras y panel de edición
    common404 = common(DEFAULT_LANG)
    common404.update(page_title=f"404 · {site_name}", page_description="", canonical=SITE_URL + "/",
                     alternates={l: SITE_URL + path_for(l) for l in LANGS}, paths={l: path_for(l) for l in LANGS},
                     route="404", body_class="page-404")
    (DIST / "404.html").write_text(env.get_template("404.html").render(**common404, T=T, LANGS=LANGS), encoding="utf-8")

    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for alts in sitemap:
        for lang in LANGS:
            lines.append("  <url>")
            lines.append(f"    <loc>{escape(alts[lang])}</loc>")
            for other in LANGS:
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{LANG_META[other]["hreflang"]}" href="{escape(alts[other])}"/>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{escape(alts[DEFAULT_LANG])}"/>')
            lines.append("  </url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (DIST / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n  X-Frame-Options: SAMEORIGIN\n\n"
        "/img/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/admin/*\n  Cache-Control: no-store\n  X-Robots-Tag: noindex\n",
        encoding="utf-8")

    admin = DIST / "admin"
    admin.mkdir(exist_ok=True)
    # JSON es YAML válido: así no hace falta ninguna librería para generar config.yml
    (admin / "config.yml").write_text(json.dumps(cms_config(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pages = len(sitemap) * len(LANGS)
    print(f"Web generada en {DIST}: {pages} páginas, {len(projects)} proyectos, {len(IMG_CACHE)} imágenes.")
    if SITE_URL.endswith(".pages.dev") and "joan-disseny" in SITE_URL and not os.environ.get("SITE_URL"):
        print("Nota: usando la dirección por defecto. Define SITE_URL en Cloudflare si tu web tiene otra dirección.")
    if GITHUB_REPO.startswith("TU-USUARIO"):
        print("Nota: define GITHUB_REPO (usuario/repositorio) en Cloudflare para que funcione el panel /admin.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
