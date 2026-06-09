import streamlit as st
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from google.genai import types as gtypes
from datetime import datetime, date
import cohere

# ── Configuración ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="RegistroVentas IA", page_icon="🛒", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Space Mono', monospace !important; }
.stApp { background-color: #0f1117; color: #e8e8e8; }
.main-header { font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700; color: #00e5a0; letter-spacing: -1px; margin-bottom: 0; }
.sub-header { font-size: 1rem; color: #888; margin-bottom: 2rem; }
.card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
.tag { display: inline-block; background: #00e5a020; color: #00e5a0; border: 1px solid #00e5a040; border-radius: 20px; padding: 2px 12px; font-size: 0.75rem; font-family: 'Space Mono', monospace; margin-bottom: 1rem; }
.producto-row { background: #12141e; border: 1px solid #2a2d3a; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; }
.producto-promo { background: #12141e; border: 1px solid #00e5a060; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; }
.producto-sin-precio { background: #12141e; border: 1px solid #ffb30060; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; }
.total-box { background: #00e5a015; border: 1px solid #00e5a040; border-radius: 10px; padding: 1rem 1.5rem; font-family: 'Space Mono', monospace; font-size: 1.1rem; color: #00e5a0; margin-top: 1rem; }
.perfil-box { background: #1a1d27; border: 1px solid #00e5a030; border-radius: 10px; padding: 1rem; font-size: 0.82rem; color: #aaa; margin-top: 0.5rem; }
.perfil-box b { color: #00e5a0; }
.chat-user { background: #1e2235; border-radius: 10px 10px 2px 10px; padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.9rem; border-left: 3px solid #00e5a0; }
.chat-bot { background: #12141e; border-radius: 10px 10px 10px 2px; padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.9rem; border-left: 3px solid #444; }
.alerta-fiscal { background: #ffb30015; border: 1px solid #ffb300; border-radius: 10px; padding: 1rem; color: #ffb300; font-size: 0.88rem; margin-bottom: 1rem; }
.promo-badge { background: #00e5a020; border: 1px solid #00e5a0; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.82rem; color: #00e5a0; margin-bottom: 0.4rem; }
.precio-normal { color: #888; text-decoration: line-through; font-size: 0.85rem; }
.precio-promo { color: #00e5a0; font-weight: 700; }
.stButton > button { background: #00e5a0 !important; color: #0f1117 !important; font-family: 'Space Mono', monospace !important; font-weight: 700 !important; border: none !important; border-radius: 8px !important; padding: 0.6rem 1.5rem !important; font-size: 0.85rem !important; }
.stButton > button:hover { background: #00c484 !important; }
.stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div { background: #1a1d27 !important; border: 1px solid #2a2d3a !important; color: #e8e8e8 !important; border-radius: 8px !important; }
div[data-testid="stSidebar"] { background: #12141e !important; border-right: 1px solid #2a2d3a !important; }
.success-box { background: #00e5a015; border: 1px solid #00e5a0; border-radius: 10px; padding: 1rem; color: #00e5a0; font-family: 'Space Mono', monospace; font-size: 0.85rem; }
.error-box { background: #ff4b4b15; border: 1px solid #ff4b4b; border-radius: 10px; padding: 1rem; color: #ff4b4b; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)


# ── Servicios ──────────────────────────────────────────────────────────────────
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None

@st.cache_resource
def init_cohere():
    api_key = st.secrets.get("COHERE_API_KEY") or os.environ.get("COHERE_API_KEY")
    if not api_key:
        return None
    return cohere.ClientV2(api_key=api_key)

@st.cache_resource
def init_sheets():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None

SHEET_ID = "1oPxcn0ucIs1mq6ImIBLp3lFznHxwjQtzhnuEkfEmuIc"

def get_sheet(gc):
    headers = ["Fecha","Hora","Nro_Comprobante","Tipo_Comprobante","Vendedor_CUIT","Vendedor_Nombre",
               "Categoria_Monotributo","Cliente","CUIT_DNI_Cliente","Condicion_IVA_Cliente",
               "Producto","Cantidad","Unidad","Precio_Unitario","Subtotal_Linea","Total_Venta",
               "Observaciones","Fuente"]
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1
    if not ws.row_values(1):
        ws.append_row(headers)
    return ws


# ── Session State ──────────────────────────────────────────────────────────────
if "perfil" not in st.session_state:
    st.session_state.perfil = {"nombre_negocio": "", "cuit": "", "categoria": "C", "rubro": "Verdulería"}
if "historial_fiscal" not in st.session_state:
    st.session_state.historial_fiscal = []
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = None
if "fuente_actual" not in st.session_state:
    st.session_state.fuente_actual = ""
if "ultimo_guardado" not in st.session_state:
    st.session_state.ultimo_guardado = None
if "input_key" not in st.session_state:
    st.session_state.input_key = 0
if "tab_activa" not in st.session_state:
    st.session_state.tab_activa = "venta"
if "lista_precios" not in st.session_state:
    st.session_state.lista_precios = []


# ── Helpers ────────────────────────────────────────────────────────────────────
def emoji_producto(nombre):
    n = nombre.lower()
    mapa = {
        "banana": "🍌", "manzana": "🍎", "naranja": "🍊", "mandarina": "🍊",
        "limon": "🍋", "limón": "🍋", "pera": "🍐", "uva": "🍇", "frutilla": "🍓",
        "sandia": "🍉", "sandía": "🍉", "melon": "🍈", "melón": "🍈",
        "durazno": "🍑", "ciruela": "🍑", "kiwi": "🥝", "ananá": "🍍",
        "anana": "🍍", "mango": "🥭", "cereza": "🍒", "pomelo": "🍊",
        "tomate": "🍅", "zanahoria": "🥕", "lechuga": "🥬", "espinaca": "🥬",
        "acelga": "🥬", "repollo": "🥬", "papa": "🥔", "batata": "🍠",
        "boniato": "🍠", "cebolla": "🧅", "ajo": "🧄", "brocoli": "🥦",
        "brócoli": "🥦", "coliflor": "🥦", "choclo": "🌽", "maiz": "🌽",
        "pimiento": "🫑", "morron": "🫑", "morrón": "🫑",
        "pepino": "🥒", "zapallo": "🎃", "zapallito": "🥒", "berenjena": "🍆",
        "apio": "🥬", "puerro": "🧅", "rucula": "🥬", "rúcula": "🥬",
        "albahaca": "🌿", "perejil": "🌿", "cilantro": "🌿",
        "huevo": "🥚", "lenteja": "🫘", "garbanzo": "🫘", "poroto": "🫘",
        "arroz": "🌾", "harina": "🌾", "jugo": "🧃",
    }
    for clave, emoji in mapa.items():
        if clave in n:
            return emoji
    return "🛒"

def buscar_precio(nombre):
    hoy = date.today()
    n = nombre.lower().strip()
    for item in st.session_state.lista_precios:
        prod = item["producto"].lower().strip()
        if prod in n or n in prod:
            precio_normal = item["precio_normal"]
            precio_aplicado = precio_normal
            promo_activa = False
            promo_desc = ""
            if item.get("tiene_promo"):
                fi, ff = item.get("fecha_inicio"), item.get("fecha_fin")
                en_rango = True
                if fi: en_rango = en_rango and hoy >= fi
                if ff: en_rango = en_rango and hoy <= ff
                if en_rango:
                    promo_activa = True
                    if item["tipo_promo"] == "Precio especial":
                        precio_aplicado = item["valor_promo"]
                        promo_desc = f"Precio especial: ${precio_aplicado:,.0f}"
                    else:
                        precio_aplicado = precio_normal * (1 - item["valor_promo"] / 100)
                        promo_desc = f"{item['valor_promo']:.0f}% OFF → ${precio_aplicado:,.0f}"
            return {"precio_normal": precio_normal, "precio_aplicado": round(precio_aplicado, 2),
                    "promo_activa": promo_activa, "promo_desc": promo_desc, "unidad": item["unidad"]}
    return None

def enriquecer_con_precios(productos):
    for p in productos:
        info = buscar_precio(p.get("descripcion", ""))
        if info:
            p["precio_normal"] = info["precio_normal"]
            p["precio_aplicado"] = info["precio_aplicado"]
            p["precio_unitario"] = info["precio_aplicado"]
            p["promo_activa"] = info["promo_activa"]
            p["promo_desc"] = info["promo_desc"]
            if not p.get("unidad") or p.get("unidad") == "otro":
                p["unidad"] = info["unidad"]
        else:
            p.setdefault("precio_normal", p.get("precio_unitario"))
            p.setdefault("precio_aplicado", p.get("precio_unitario"))
            p.setdefault("promo_activa", False)
            p.setdefault("promo_desc", "")
    return productos

def normalizar_texto(texto):
    reemplazos = {
        "1/2": "0.5", "1/4": "0.25", "3/4": "0.75",
        "½": "0.5", "¼": "0.25", "¾": "0.75",
        "medio ": "0.5 ", "media ": "0.5 ",
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto


# ── Prompts ────────────────────────────────────────────────────────────────────
def build_ventas_prompt(perfil):
    rubro = perfil.get("rubro") or "comercio"
    return f"""Sos un asistente contable para monotributistas argentinos. Extraé datos de ventas.
El negocio es una/un {rubro}.

Devolvé ÚNICAMENTE este JSON (sin markdown, sin backticks):

{{
  "tipo_comprobante": "Factura C",
  "cliente": null,
  "cuit_dni": null,
  "condicion_iva": "Consumidor Final",
  "productos": [
    {{"descripcion": "nombre", "cantidad": 1, "unidad": "kg", "precio_unitario": null, "fuera_de_rubro": false}}
  ],
  "observaciones": null
}}

Reglas:
- Precio faltante → null
- Cantidad faltante → 1
- Unidad por contexto: frutas/verduras→kg, huevos→docena
- Tipo comprobante siempre: Factura C
- Interpretá abreviaciones y errores: tom→tomate, zana→zanahoria
- fuera_de_rubro: true solo si el producto claramente no corresponde al rubro {rubro}
- Respondé SOLO con el JSON"""

def fiscal_system_prompt(perfil):
    return f"""Sos un asistente fiscal para monotributistas argentinos.
Negocio: {perfil.get('nombre_negocio','—')} | CUIT: {perfil.get('cuit','—')} | Cat. {perfil.get('categoria','—')} | Rubro: {perfil.get('rubro','—')}
Respondé simple y directo en español rioplatense. Máx 5 oraciones. Los monotributistas SOLO emiten Factura C."""


# ── Procesamiento ──────────────────────────────────────────────────────────────
def procesar_con_cohere(co_client, prompt, texto):
    r = co_client.chat(
        model="command-r-08-2024",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": texto},
        ],
    )
    return r.message.content[0].text

def procesar_venta(gemini_client, co_client, contenido, tipo, perfil=None):
    prompt = build_ventas_prompt(perfil or {})

    try:
        # Cohere para texto
        if tipo == "texto" and co_client:
            texto = normalizar_texto(contenido)
            raw = procesar_con_cohere(co_client, prompt, texto)
            raw = raw.strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)

        # Gemini para audio e imagen
        if gemini_client:
            if tipo == "audio":
                r = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, "Transcribí el audio y extraé los datos.", contenido]
                )
            elif tipo == "imagen":
                r = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, "Analizá la imagen y extraé los datos.", contenido]
                )
            raw = r.text.strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)

    except json.JSONDecodeError:
        st.warning("⚠️ No pudo interpretar el texto. Intentá reformular.")
        return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None

def consulta_fiscal(gemini_client, co_client, pregunta, historial, perfil):
    system = fiscal_system_prompt(perfil)
    if co_client:
        try:
            msgs = [{"role": "system", "content": system}]
            for m in historial[-6:]:
                msgs.append({"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]})
            msgs.append({"role": "user", "content": pregunta})
            r = co_client.chat(model="command-r-08-2024", messages=msgs)
            return r.message.content[0].text
        except Exception:
            pass
    if gemini_client:
        try:
            msgs = [system] + [f"{'Empleado' if m['role']=='user' else 'Asistente'}: {m['text']}" for m in historial[-6:]]
            msgs.append(f"Empleado: {pregunta}")
            r = gemini_client.models.generate_content(model="gemini-2.5-flash", contents="\n\n".join(msgs))
            return r.text
        except Exception as e:
            return f"Error: {e}"
    return "❌ No hay servicio de IA disponible."

def guardar_en_sheets(ws, datos, nro_comprobante, fuente, perfil):
    ahora = datetime.now()
    productos = datos.get("productos", [])
    total = sum((p.get("cantidad") or 1) * (p.get("precio_unitario") or 0) for p in productos)
    for p in productos:
        sub = (p.get("cantidad") or 1) * (p.get("precio_unitario") or 0)
        ws.append_row([
            ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M"),
            nro_comprobante, datos.get("tipo_comprobante",""),
            perfil.get("cuit",""), perfil.get("nombre_negocio",""), perfil.get("categoria",""),
            datos.get("cliente") or "Consumidor Final", datos.get("cuit_dni") or "",
            datos.get("condicion_iva",""),
            p.get("descripcion",""), p.get("cantidad",""), p.get("unidad",""),
            p.get("precio_unitario",""), round(sub, 2), round(total, 2),
            datos.get("observaciones") or "", fuente,
        ])
    return total, len(productos)


# ── Init servicios ─────────────────────────────────────────────────────────────
gemini_client = init_gemini()
co_client = init_cohere()
gc = init_sheets()
sheets_ok = gc is not None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-family:Space Mono;color:#00e5a0;font-weight:700;font-size:1.1rem;">🏪 Mi Negocio</p>', unsafe_allow_html=True)
    nombre_neg = st.text_input("Nombre", value=st.session_state.perfil["nombre_negocio"], placeholder="Verdulería Don José")
    cuit_neg = st.text_input("Mi CUIT", value=st.session_state.perfil["cuit"], placeholder="20-12345678-9")
    cats = ["A","B","C","D","E","F","G","H","I","J","K"]
    cat_idx = cats.index(st.session_state.perfil["categoria"]) if st.session_state.perfil["categoria"] in cats else 2
    categoria_neg = st.selectbox("Categoría Monotributo", cats, index=cat_idx)
    rubro_neg = st.text_input("Rubro", value=st.session_state.perfil["rubro"])
    if st.button("💾 Guardar perfil"):
        st.session_state.perfil = {"nombre_negocio": nombre_neg, "cuit": cuit_neg, "categoria": categoria_neg, "rubro": rubro_neg}
        st.success("Perfil guardado!")
    if st.session_state.perfil["nombre_negocio"]:
        p = st.session_state.perfil
        st.markdown(f'<div class="perfil-box"><b>{p["nombre_negocio"]}</b><br>CUIT: {p["cuit"] or "—"}<br>Monotributista Cat. <b>{p["categoria"]}</b><br>{p["rubro"]}</div>', unsafe_allow_html=True)
    st.markdown("---")
    sheet_name = st.text_input("Google Sheet", value="Ventas_Verduleria")
    nro_comprobante = st.text_input("Nro. Comprobante", value=f"C-{datetime.now().strftime('%Y%m%d%H%M')}")
    st.markdown(f'<p style="color:{"#00e5a0" if sheets_ok else "#ff4b4b"};font-size:0.82rem;">{"✅ Sheets conectado" if sheets_ok else "❌ Sheets no configurado"}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:{"#00e5a0" if co_client else "#ff4b4b"};font-size:0.82rem;">{"✅ Cohere conectado" if co_client else "❌ Cohere no configurado"}</p>', unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🛒 RegistroVentas IA</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Registrá ventas · Gestioná precios y promos · Consultá dudas fiscales</p>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Texto", "🎙️ Audio", "📷 Imagen", "💰 Precios y Promos", "🧾 Consultas Fiscales"])


# ── Tab 1: Texto ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="tag">REGISTRAR VENTA POR TEXTO</div>', unsafe_allow_html=True)
    st.markdown("Escribí la venta como si mandaras un WhatsApp:")
    st.markdown("> *\"2 tom 3 papa\"* · *\"4 banana, 2kg cebolla, 1/2 zapallito\"* · *\"fac a juan 2kg tomate 500\"*")
    texto_input = st.text_area("Tu mensaje:", height=100, placeholder="Escribí acá...", key=f"texto_{st.session_state.input_key}")
    if st.button("Procesar →", key="btn_texto"):
        if texto_input.strip():
            with st.spinner("Analizando..."):
                resultado = procesar_venta(gemini_client, co_client, texto_input.strip(), "texto", st.session_state.perfil)
                if resultado:
                    resultado["productos"] = enriquecer_con_precios(resultado.get("productos", []))
                    st.session_state.datos_procesados = resultado
                    st.session_state.fuente_actual = "texto"
                    st.session_state.tab_activa = "venta"
        else:
            st.warning("Escribí algo primero.")


# ── Tab 2: Audio ───────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="tag">REGISTRAR VENTA POR AUDIO</div>', unsafe_allow_html=True)
    st.markdown("Subí un audio de WhatsApp (.ogg, .mp3, .wav, .m4a).")
    audio_file = st.file_uploader("Seleccioná el audio:", type=["ogg","mp3","wav","m4a","webm"])
    if audio_file:
        st.audio(audio_file)
        if st.button("Procesar →", key="btn_audio"):
            with st.spinner("Transcribiendo y analizando..."):
                audio_bytes = audio_file.read()
                ext = audio_file.name.split(".")[-1].lower()
                mime = {"ogg":"audio/ogg","mp3":"audio/mpeg","wav":"audio/wav","m4a":"audio/mp4","webm":"audio/webm"}.get(ext,"audio/ogg")
                resultado = procesar_venta(gemini_client, co_client, gtypes.Part.from_bytes(data=audio_bytes, mime_type=mime), "audio", st.session_state.perfil)
                if resultado:
                    resultado["productos"] = enriquecer_con_precios(resultado.get("productos", []))
                    st.session_state.datos_procesados = resultado
                    st.session_state.fuente_actual = "audio"
                    st.session_state.tab_activa = "venta"


# ── Tab 3: Imagen ──────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="tag">REGISTRAR VENTA POR IMAGEN</div>', unsafe_allow_html=True)
    st.markdown("Subí foto de un ticket, remito o pizarra de precios.")
    img_file = st.file_uploader("Seleccioná la imagen:", type=["jpg","jpeg","png","webp"])
    if img_file:
        st.image(img_file, width=350)
        if st.button("Procesar →", key="btn_imagen"):
            with st.spinner("Analizando imagen..."):
                img_bytes = img_file.read()
                ext = img_file.name.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ("jpg","jpeg") else f"image/{ext}"
                resultado = procesar_venta(gemini_client, co_client, gtypes.Part.from_bytes(data=img_bytes, mime_type=mime), "imagen", st.session_state.perfil)
                if resultado:
                    resultado["productos"] = enriquecer_con_precios(resultado.get("productos", []))
                    st.session_state.datos_procesados = resultado
                    st.session_state.fuente_actual = "imagen"
                    st.session_state.tab_activa = "venta"


# ── Tab 4: Precios y Promos ────────────────────────────────────────────────────
with tab4:
    st.session_state.tab_activa = "precios"  # OK acá porque no muestra datos
    st.markdown('<div class="tag">LISTA DE PRECIOS Y PROMOS</div>', unsafe_allow_html=True)
    hoy = date.today()

    promos_activas = []
    for item in st.session_state.lista_precios:
        if item.get("tiene_promo"):
            fi, ff = item.get("fecha_inicio"), item.get("fecha_fin")
            en_rango = True
            if fi: en_rango = en_rango and hoy >= fi
            if ff: en_rango = en_rango and hoy <= ff
            if en_rango:
                promos_activas.append(item)

    if promos_activas:
        st.markdown("### 🔥 Promos activas hoy")
        for p in promos_activas:
            vence = f"hasta el {p['fecha_fin'].strftime('%d/%m')}" if p.get("fecha_fin") else "sin vencimiento"
            if p["tipo_promo"] == "Precio especial":
                desc = f"${p['valor_promo']:,.0f}/{p['unidad']} (normal: ${p['precio_normal']:,.0f})"
            else:
                desc = f"{p['valor_promo']:.0f}% OFF → ${p['precio_normal']*(1-p['valor_promo']/100):,.0f}/{p['unidad']}"
            st.markdown(f'<div class="promo-badge">🏷️ <b>{p["producto"]}</b> — {desc} — {vence}</div>', unsafe_allow_html=True)
        st.markdown("---")

    st.markdown("### ➕ Agregar / actualizar producto")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        nuevo_prod = st.text_input("Producto", placeholder="Ej: Banana")
    with col2:
        nueva_unidad = st.selectbox("Unidad", ["kg","unidad","docena","litro","atado","bolsa"])
    with col3:
        nuevo_precio = st.number_input("Precio ($)", min_value=0.0, step=10.0, format="%.2f")

    tiene_promo = st.checkbox("¿Tiene promoción?")
    if tiene_promo:
        cp1, cp2, cp3, cp4 = st.columns([1,1,1,1])
        with cp1:
            tipo_promo = st.selectbox("Tipo", ["Precio especial","Descuento %"])
        with cp2:
            valor_promo = st.number_input("Valor", min_value=0.0, step=10.0 if tipo_promo=="Precio especial" else 1.0)
        with cp3:
            fecha_inicio = st.date_input("Desde", value=hoy)
        with cp4:
            fecha_fin = st.date_input("Hasta", value=hoy)
    else:
        tipo_promo, valor_promo, fecha_inicio, fecha_fin = None, None, None, None

    if st.button("✅ Agregar producto"):
        if nuevo_prod.strip() and nuevo_precio > 0:
            encontrado = False
            for item in st.session_state.lista_precios:
                if item["producto"].lower() == nuevo_prod.strip().lower():
                    item.update({"unidad": nueva_unidad, "precio_normal": nuevo_precio,
                                 "tiene_promo": tiene_promo, "tipo_promo": tipo_promo,
                                 "valor_promo": valor_promo, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin})
                    encontrado = True
                    break
            if not encontrado:
                st.session_state.lista_precios.append({
                    "producto": nuevo_prod.strip(), "unidad": nueva_unidad, "precio_normal": nuevo_precio,
                    "tiene_promo": tiene_promo, "tipo_promo": tipo_promo,
                    "valor_promo": valor_promo, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin
                })
            st.success(f"✅ {nuevo_prod.strip()} guardado a ${nuevo_precio:,.2f}/{nueva_unidad}")
            st.rerun()
        else:
            st.warning("Completá nombre y precio.")

    if st.session_state.lista_precios:
        st.markdown("---")
        st.markdown("### 📋 Lista actual")
        for i, item in enumerate(st.session_state.lista_precios):
            ca, cb, cc, cd = st.columns([2,1,2,1])
            ca.write(f"**{item['producto']}**")
            cb.write(f"${item['precio_normal']:,.0f}/{item['unidad']}")
            if item.get("tiene_promo"):
                fi, ff = item.get("fecha_inicio"), item.get("fecha_fin")
                en_rango = True
                if fi: en_rango = en_rango and hoy >= fi
                if ff: en_rango = en_rango and hoy <= ff
                estado = "🟢" if en_rango else "⚪"
                cc.write(f"{estado} {item['tipo_promo']} — {item['valor_promo']}")
            else:
                cc.write("Sin promo")
            if cd.button("🗑️", key=f"del_{i}"):
                st.session_state.lista_precios.pop(i)
                st.rerun()
    else:
        st.info("Todavía no cargaste ningún producto.")


# ── Tab 5: Consultas Fiscales ──────────────────────────────────────────────────
with tab5:
    st.session_state.tab_activa = "fiscal"  # OK acá porque no muestra datos
    st.markdown('<div class="tag">ASISTENTE FISCAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="alerta-fiscal">⚠️ <b>Recordá siempre:</b> Como monotributista solo podés emitir <b>Factura C</b>.</div>', unsafe_allow_html=True)

    preguntas_rapidas = [
        "¿Qué hago si me piden Factura A?",
        "¿Cuándo debo emitir un remito?",
        "¿Tengo que facturar si el cliente no pide comprobante?",
        "¿Qué pasa si supero el límite de mi categoría?",
        "¿Cómo facturo a una empresa con CUIT?",
        "¿Qué datos necesito del cliente para facturar?",
    ]
    cols = st.columns(2)
    for i, pq in enumerate(preguntas_rapidas):
        with cols[i % 2]:
            if st.button(pq, key=f"pq_{i}"):
                with st.spinner("Consultando..."):
                    resp = consulta_fiscal(gemini_client, co_client, pq, st.session_state.historial_fiscal, st.session_state.perfil)
                    st.session_state.historial_fiscal.append({"role": "user", "text": pq})
                    st.session_state.historial_fiscal.append({"role": "bot", "text": resp})

    st.markdown("---")
    for m in st.session_state.historial_fiscal:
        css = "chat-user" if m["role"] == "user" else "chat-bot"
        icon = "🙋" if m["role"] == "user" else "🤖"
        st.markdown(f'<div class="{css}">{icon} {m["text"]}</div>', unsafe_allow_html=True)

    pregunta_libre = st.chat_input("Escribí tu duda fiscal...")
    if pregunta_libre:
        with st.spinner("Consultando..."):
            resp = consulta_fiscal(gemini_client, co_client, pregunta_libre, st.session_state.historial_fiscal, st.session_state.perfil)
            st.session_state.historial_fiscal.append({"role": "user", "text": pregunta_libre})
            st.session_state.historial_fiscal.append({"role": "bot", "text": resp})
            st.rerun()

    if st.session_state.historial_fiscal:
        if st.button("🗑️ Limpiar historial"):
            st.session_state.historial_fiscal = []
            st.rerun()


# ── Mensaje de éxito y deshacer ───────────────────────────────────────────────
if st.session_state.ultimo_guardado and st.session_state.tab_activa == "venta":
    ug = st.session_state.ultimo_guardado
    st.markdown(f'<div class="success-box">✅ Guardado — {ug["nro_filas"]} producto(s) — Total: ${ug["total"]:,.2f}</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col_undo, col_nueva = st.columns([1, 1])
    with col_undo:
        if st.button("↩️ Deshacer último guardado"):
            if sheets_ok:
                try:
                    ws = get_sheet(gc)
                    filas_total = len(ws.get_all_values())
                    for _ in range(ug["nro_filas"]):
                        ws.delete_rows(filas_total)
                        filas_total -= 1
                    st.session_state.ultimo_guardado = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col_nueva:
        if st.button("✅ Nueva venta"):
            st.session_state.ultimo_guardado = None
            st.session_state.datos_procesados = None
            st.session_state.fuente_actual = ""
            st.session_state.input_key += 1
            st.rerun()


# ── Vista previa y guardado ────────────────────────────────────────────────────
datos_procesados = st.session_state.datos_procesados
fuente_actual = st.session_state.fuente_actual

if datos_procesados and st.session_state.tab_activa == "venta":
    st.markdown("---")
    st.markdown("### 📋 Datos extraídos — revisá y confirmá")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        tc_opts = ["Factura C","Ticket","Remito","Otro"]
        tc_val = datos_procesados.get("tipo_comprobante","Factura C")
        tc = st.selectbox("Tipo comprobante", tc_opts, index=tc_opts.index(tc_val) if tc_val in tc_opts else 0)
        datos_procesados["tipo_comprobante"] = tc
        if tc != "Factura C":
            st.markdown('<div class="alerta-fiscal">⚠️ Como monotributista emitís <b>Factura C</b>.</div>', unsafe_allow_html=True)
        cliente = st.text_input("Cliente", value=datos_procesados.get("cliente") or "Consumidor Final")
        datos_procesados["cliente"] = cliente
        cuit = st.text_input("CUIT / DNI del cliente", value=datos_procesados.get("cuit_dni") or "")
        datos_procesados["cuit_dni"] = cuit
        cond_opts = ["Consumidor Final","Responsable Inscripto","Monotributista","Exento","No especificado"]
        cond_val = datos_procesados.get("condicion_iva","Consumidor Final")
        cond = st.selectbox("Condición IVA", cond_opts, index=cond_opts.index(cond_val) if cond_val in cond_opts else 0)
        datos_procesados["condicion_iva"] = cond
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Productos — editá si hace falta**")
        productos = datos_procesados.get("productos", [])

        fuera_rubro = [p for p in productos if p.get("fuera_de_rubro")]
        if fuera_rubro:
            nombres = ", ".join(p.get("descripcion","") for p in fuera_rubro)
            st.markdown(f'<div class="alerta-fiscal">⚠️ Posiblemente fuera de rubro: <b>{nombres}</b></div>', unsafe_allow_html=True)

        ik = st.session_state.input_key
        to_delete = []
        for i, p in enumerate(productos):
            icon = "⚠️" if p.get("fuera_de_rubro") else emoji_producto(p.get("descripcion",""))
            precio_actual = float(p.get("precio_aplicado") or p.get("precio_unitario") or 0)
            cant_actual = float(p.get("cantidad") or 1)
            with st.expander(f"{icon} {p.get('descripcion','Producto')} — {cant_actual} {p.get('unidad','')} × ${precio_actual:,.0f}", expanded=p.get("fuera_de_rubro", False)):
                ec1, ec2, ec3 = st.columns([2,1,1])
                with ec1:
                    p["descripcion"] = st.text_input("Descripción", value=p.get("descripcion",""), key=f"desc_{ik}_{i}")
                with ec2:
                    p["cantidad"] = st.number_input("Cantidad", value=cant_actual, min_value=0.0, step=0.5, key=f"cant_{ik}_{i}")
                with ec3:
                    unis = ["kg","unidad","litro","docena","atado","bolsa","otro"]
                    u_val = p.get("unidad","kg")
                    p["unidad"] = st.selectbox("Unidad", unis, index=unis.index(u_val) if u_val in unis else 0, key=f"uni_{ik}_{i}")
                nuevo_precio = st.number_input("Precio ($)", value=precio_actual, min_value=0.0, step=10.0, key=f"precio_{ik}_{i}")
                p["precio_unitario"] = nuevo_precio
                p["precio_aplicado"] = nuevo_precio
                if st.button("🗑️ Quitar", key=f"del_prod_{ik}_{i}"):
                    to_delete.append(i)

        for idx in reversed(to_delete):
            productos.pop(idx)
        datos_procesados["productos"] = productos
        st.session_state.datos_procesados = datos_procesados

        st.markdown("---")
        st.markdown("**➕ Agregar producto**")
        na1, na2, na3, na4 = st.columns([2,1,1,1])
        with na1:
            nuevo_desc = st.text_input("Producto", key="nuevo_desc", placeholder="Ej: Naranja")
        with na2:
            nuevo_cant = st.number_input("Cantidad", value=1.0, min_value=0.0, step=0.5, key="nuevo_cant")
        with na3:
            nuevo_uni = st.selectbox("Unidad", ["kg","unidad","litro","docena","atado","bolsa","otro"], key="nuevo_uni")
        with na4:
            nuevo_precio_n = st.number_input("Precio ($)", value=0.0, min_value=0.0, step=10.0, key="nuevo_precio")
        if st.button("➕ Agregar", key="btn_agregar_prod"):
            if nuevo_desc.strip():
                info = buscar_precio(nuevo_desc.strip())
                datos_procesados["productos"].append({
                    "descripcion": nuevo_desc.strip(), "cantidad": nuevo_cant, "unidad": nuevo_uni,
                    "precio_unitario": nuevo_precio_n or (info["precio_aplicado"] if info else 0),
                    "precio_aplicado": nuevo_precio_n or (info["precio_aplicado"] if info else 0),
                    "fuera_de_rubro": False,
                })
                st.session_state.datos_procesados = datos_procesados
                st.rerun()

        total = sum((p.get("cantidad") or 1) * (p.get("precio_unitario") or 0) for p in productos)
        st.markdown(f'<div class="total-box">TOTAL: ${total:,.2f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    obs = st.text_input("Observaciones", value=datos_procesados.get("observaciones") or "")
    datos_procesados["observaciones"] = obs

    if st.button("💾 Confirmar y guardar en Sheets"):
        if not sheets_ok:
            st.warning("Google Sheets no configurado.")
        else:
            with st.spinner("Guardando..."):
                try:
                    ws = get_sheet(gc)
                    total_g, n = guardar_en_sheets(ws, datos_procesados, nro_comprobante, fuente_actual, st.session_state.perfil)
                    st.session_state.ultimo_guardado = {"nro_filas": n, "total": total_g, "nro_comprobante": nro_comprobante}
                    st.session_state.datos_procesados = None
                    st.session_state.input_key += 1
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error: {e}</div>', unsafe_allow_html=True)
