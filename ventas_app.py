import streamlit as st
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from google.genai import types as gtypes
from datetime import datetime, date

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
.stFileUploader > div { background: #1a1d27 !important; border: 1px dashed #2a2d3a !important; border-radius: 8px !important; }
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
        st.error("Falta GEMINI_API_KEY en los secrets.")
        st.stop()
    return genai.Client(api_key=api_key)

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

def get_or_create_sheet(gc, sheet_name=None):
    headers = ["Fecha","Hora","Nro_Comprobante","Tipo_Comprobante","Vendedor_CUIT","Vendedor_Nombre",
               "Categoria_Monotributo","Cliente","CUIT_DNI_Cliente","Condicion_IVA_Cliente",
               "Producto","Cantidad","Unidad","Precio_Normal","Precio_Aplicado","Descuento_Pct",
               "Promo_Activa","Subtotal_Linea","Total_Venta","Observaciones","Fuente"]
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
if "lista_precios" not in st.session_state:
    st.session_state.lista_precios = []
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = None
if "fuente_actual" not in st.session_state:
    st.session_state.fuente_actual = ""
if "ultimo_guardado" not in st.session_state:
    st.session_state.ultimo_guardado = None  # {"nro_filas": n, "total": x, "nro_comprobante": "..."}


# ── Helpers de precios ─────────────────────────────────────────────────────────
def buscar_precio(nombre_producto: str) -> dict | None:
    """Busca el precio vigente de un producto. Retorna dict con precio_normal, precio_aplicado, promo_info."""
    hoy = date.today()
    nombre_lower = nombre_producto.lower().strip()

    mejor = None
    for item in st.session_state.lista_precios:
        prod_lower = item["producto"].lower().strip()
        # Match exacto o parcial
        if prod_lower in nombre_lower or nombre_lower in prod_lower:
            mejor = item
            break

    if not mejor:
        return None

    precio_normal = mejor["precio_normal"]
    precio_aplicado = precio_normal
    promo_activa = False
    promo_desc = ""

    if mejor.get("tiene_promo"):
        fi = mejor.get("fecha_inicio")
        ff = mejor.get("fecha_fin")
        en_rango = True
        if fi:
            en_rango = en_rango and hoy >= fi
        if ff:
            en_rango = en_rango and hoy <= ff

        if en_rango:
            promo_activa = True
            if mejor["tipo_promo"] == "Precio especial":
                precio_aplicado = mejor["valor_promo"]
                promo_desc = f"Precio especial: ${precio_aplicado:,.0f}"
            elif mejor["tipo_promo"] == "Descuento %":
                descuento = mejor["valor_promo"]
                precio_aplicado = precio_normal * (1 - descuento / 100)
                promo_desc = f"{descuento:.0f}% OFF → ${precio_aplicado:,.0f}"

    return {
        "precio_normal": precio_normal,
        "precio_aplicado": round(precio_aplicado, 2),
        "promo_activa": promo_activa,
        "promo_desc": promo_desc,
        "unidad": mejor["unidad"],
    }

def enriquecer_con_precios(productos: list) -> list:
    """Completa precios faltantes y aplica promos automáticamente."""
    for p in productos:
        info = buscar_precio(p.get("descripcion", ""))
        if info:
            p["precio_normal"] = info["precio_normal"]
            p["precio_aplicado"] = info["precio_aplicado"]
            p["promo_activa"] = info["promo_activa"]
            p["promo_desc"] = info["promo_desc"]
            if not p.get("precio_unitario"):
                p["precio_unitario"] = info["precio_aplicado"]
        else:
            p.setdefault("precio_normal", p.get("precio_unitario"))
            p.setdefault("precio_aplicado", p.get("precio_unitario"))
            p.setdefault("promo_activa", False)
            p.setdefault("promo_desc", "")
    return productos


# ── Prompts ────────────────────────────────────────────────────────────────────
VENTAS_PROMPT = """Sos un asistente contable para monotributistas argentinos. Extraé datos de ventas de forma flexible.

Devolvé ÚNICAMENTE este JSON (sin markdown, sin backticks):

{
  "tipo_comprobante": "Factura C" | "Ticket" | "Remito" | "Otro",
  "cliente": "nombre o null",
  "cuit_dni": "número o null",
  "condicion_iva": "Consumidor Final" | "Responsable Inscripto" | "Monotributista" | "Exento" | "No especificado",
  "productos": [
    {"descripcion": "nombre", "cantidad": número o null, "unidad": "kg"|"unidad"|"litro"|"docena"|"atado"|"bolsa"|"otro", "precio_unitario": número o null}
  ],
  "observaciones": "texto o null"
}

Reglas:
- Precio faltante → null (nunca inventes precios, el sistema los completa desde la lista de precios)
- Cantidad faltante → 1
- Inferí unidad: frutas/verduras→kg, huevos→docena
- Tipo comprobante por defecto: Factura C
- Cliente faltante → null
- Interpretá abreviaciones, errores, lunfardo, mensajes a las apuradas
- "tom"→tomate, "zana"→zanahoria, "1k"→1000, "1.200"→1200
"""

def fiscal_system_prompt(perfil):
    return f"""Sos un asistente fiscal para monotributistas argentinos.
Negocio: {perfil.get('nombre_negocio','—')} | CUIT: {perfil.get('cuit','—')} | Cat. {perfil.get('categoria','—')} | Rubro: {perfil.get('rubro','—')}
Respondé simple, directo, en español rioplatense. Máx 5 oraciones. Los monotributistas SOLO emiten Factura C.
Si excede tu conocimiento, decilo y recomendá un contador."""

def procesar_venta(client, contenido, tipo):
    try:
        if tipo == "texto":
            r = client.models.generate_content(model="gemini-2.5-flash", contents=[VENTAS_PROMPT, contenido])
        elif tipo == "audio":
            r = client.models.generate_content(model="gemini-2.5-flash", contents=[VENTAS_PROMPT, "Transcribí el audio y extraé los datos.", contenido])
        elif tipo == "imagen":
            r = client.models.generate_content(model="gemini-2.5-flash", contents=[VENTAS_PROMPT, "Analizá la imagen y extraé los datos de venta.", contenido])
        raw = r.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        st.error("Gemini no devolvió JSON válido. Intentá de nuevo.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def consulta_fiscal(client, pregunta, historial, perfil):
    try:
        msgs = [fiscal_system_prompt(perfil)]
        for m in historial:
            msgs.append(f"{'Empleado' if m['role']=='user' else 'Asistente'}: {m['text']}")
        msgs.append(f"Empleado: {pregunta}")
        r = client.models.generate_content(model="gemini-2.5-flash", contents="\n\n".join(msgs))
        return r.text
    except Exception as e:
        return f"Error: {e}"

def guardar_en_sheets(ws, datos, nro_comprobante, fuente, perfil):
    ahora = datetime.now()
    productos = datos.get("productos", [])
    total_venta = sum((p.get("cantidad") or 1) * (p.get("precio_aplicado") or p.get("precio_unitario") or 0) for p in productos)
    for p in productos:
        precio_aplicado = p.get("precio_aplicado") or p.get("precio_unitario") or 0
        subtotal = (p.get("cantidad") or 1) * precio_aplicado
        descuento_pct = ""
        if p.get("precio_normal") and p.get("precio_aplicado") and p["precio_normal"] != p["precio_aplicado"]:
            descuento_pct = round((1 - p["precio_aplicado"] / p["precio_normal"]) * 100, 1)
        ws.append_row([
            ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M"),
            nro_comprobante, datos.get("tipo_comprobante",""),
            perfil.get("cuit",""), perfil.get("nombre_negocio",""), perfil.get("categoria",""),
            datos.get("cliente") or "Consumidor Final", datos.get("cuit_dni") or "",
            datos.get("condicion_iva","No especificado"),
            p.get("descripcion",""), p.get("cantidad",""), p.get("unidad",""),
            p.get("precio_normal",""), precio_aplicado, descuento_pct,
            "Sí" if p.get("promo_activa") else "No",
            round(subtotal, 2), round(total_venta, 2),
            datos.get("observaciones") or "", fuente,
        ])
    return total_venta, len(productos)


# ── Init ───────────────────────────────────────────────────────────────────────
client = init_gemini()
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
        st.markdown(f'<div class="perfil-box"><b>{p["nombre_negocio"]}</b><br>CUIT: {p["cuit"] or "—"}<br>Monotributista Cat. <b>{p["categoria"]}</b><br>Rubro: {p["rubro"]}</div>', unsafe_allow_html=True)
    st.markdown("---")
    sheet_name = st.text_input("Google Sheet", value="Ventas_Verduleria")
    nro_comprobante = st.text_input("Nro. Comprobante", value=f"C-{datetime.now().strftime('%Y%m%d%H%M')}")
    st.markdown(f'<p style="color:{"#00e5a0" if sheets_ok else "#ff4b4b"};font-size:0.82rem;">{"✅ Google Sheets conectado" if sheets_ok else "❌ Google Sheets no configurado"}</p>', unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🛒 RegistroVentas IA</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Registrá ventas · Gestioná precios y promos · Consultá dudas fiscales</p>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Texto", "🎙️ Audio", "📷 Imagen", "💰 Precios y Promos", "🧾 Consultas Fiscales"])

# datos_procesados se persiste en session_state

# ── Tab 1: Texto ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="tag">REGISTRAR VENTA POR TEXTO</div>', unsafe_allow_html=True)
    st.markdown("Escribí la venta como si mandaras un WhatsApp. Informal, incompleto, abreviado — todo vale:")
    st.markdown("> *\"2 tom 3 papa\"* · *\"tomate 500 zana 300\"* · *\"fac a juan 2kg tomate\"* · *\"Vendí 3kg tomate, 1 lechuga, 2 doc huevo\"*")
    texto_input = st.text_area("Tu mensaje:", height=100, placeholder="Escribí acá...")
    if st.button("Procesar →", key="btn_texto"):
        if texto_input.strip():
            with st.spinner("Analizando..."):
                st.session_state.datos_procesados = procesar_venta(client, texto_input.strip(), "texto")
                if st.session_state.datos_procesados:
                    st.session_state.datos_procesados["productos"] = enriquecer_con_precios(st.session_state.datos_procesados.get("productos", []))
                st.session_state.fuente_actual = "texto"
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
                st.session_state.datos_procesados = procesar_venta(client, gtypes.Part.from_bytes(data=audio_bytes, mime_type=mime), "audio")
                if st.session_state.datos_procesados:
                    st.session_state.datos_procesados["productos"] = enriquecer_con_precios(st.session_state.datos_procesados.get("productos", []))
                st.session_state.fuente_actual = "audio"

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
                st.session_state.datos_procesados = procesar_venta(client, gtypes.Part.from_bytes(data=img_bytes, mime_type=mime), "imagen")
                if st.session_state.datos_procesados:
                    st.session_state.datos_procesados["productos"] = enriquecer_con_precios(st.session_state.datos_procesados.get("productos", []))
                st.session_state.fuente_actual = "imagen"

# ── Tab 4: Lista de Precios y Promos ──────────────────────────────────────────
with tab4:
    st.markdown('<div class="tag">LISTA DE PRECIOS Y PROMOS</div>', unsafe_allow_html=True)
    st.markdown("El dueño carga los precios acá. Cuando se registra una venta, los precios y promos se aplican automáticamente.")

    # Mostrar promos activas
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

    # Formulario para agregar producto
    st.markdown("### ➕ Agregar / actualizar producto")
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            nuevo_prod = st.text_input("Producto", placeholder="Ej: Banana, Tomate cherry...")
        with col2:
            nueva_unidad = st.selectbox("Unidad", ["kg", "unidad", "docena", "litro", "atado", "bolsa"])
        with col3:
            nuevo_precio = st.number_input("Precio normal ($)", min_value=0.0, step=10.0, format="%.2f")

        tiene_promo = st.checkbox("¿Tiene promoción?")
        if tiene_promo:
            col_p1, col_p2, col_p3, col_p4 = st.columns([1, 1, 1, 1])
            with col_p1:
                tipo_promo = st.selectbox("Tipo de promo", ["Precio especial", "Descuento %"])
            with col_p2:
                if tipo_promo == "Precio especial":
                    valor_promo = st.number_input("Precio promocional ($)", min_value=0.0, step=10.0, format="%.2f")
                else:
                    valor_promo = st.number_input("Descuento (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.1f")
            with col_p3:
                fecha_inicio = st.date_input("Desde", value=hoy)
            with col_p4:
                fecha_fin = st.date_input("Hasta", value=hoy)
        else:
            tipo_promo, valor_promo, fecha_inicio, fecha_fin = None, None, None, None

        if st.button("✅ Agregar producto"):
            if nuevo_prod.strip() and nuevo_precio > 0:
                # Actualizar si ya existe
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

    # Tabla de precios actual
    if st.session_state.lista_precios:
        st.markdown("---")
        st.markdown("### 📋 Lista de precios actual")
        for i, item in enumerate(st.session_state.lista_precios):
            col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 1])
            with col_a:
                st.write(f"**{item['producto']}**")
            with col_b:
                st.write(f"${item['precio_normal']:,.0f}/{item['unidad']}")
            with col_c:
                if item.get("tiene_promo"):
                    fi, ff = item.get("fecha_inicio"), item.get("fecha_fin")
                    en_rango = True
                    if fi: en_rango = en_rango and hoy >= fi
                    if ff: en_rango = en_rango and hoy <= ff
                    estado = "🟢 ACTIVA" if en_rango else "⚪ Inactiva"
                    if item["tipo_promo"] == "Precio especial":
                        st.write(f"{estado} — Precio especial ${item['valor_promo']:,.0f}")
                    else:
                        st.write(f"{estado} — {item['valor_promo']:.0f}% OFF")
                else:
                    st.write("Sin promo")
            with col_d:
                if st.button("🗑️", key=f"del_precio_{i}"):
                    st.session_state.lista_precios.pop(i)
                    st.rerun()
    else:
        st.info("Todavía no cargaste ningún producto. Agregá uno arriba para empezar.")

# ── Tab 5: Consultas Fiscales ──────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="tag">ASISTENTE FISCAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="alerta-fiscal">⚠️ <b>Recordá siempre:</b> Como monotributista solo podés emitir <b>Factura C</b>. Nunca A ni B.</div>', unsafe_allow_html=True)

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
                    resp = consulta_fiscal(client, pq, st.session_state.historial_fiscal, st.session_state.perfil)
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
            resp = consulta_fiscal(client, pregunta_libre, st.session_state.historial_fiscal, st.session_state.perfil)
            st.session_state.historial_fiscal.append({"role": "user", "text": pregunta_libre})
            st.session_state.historial_fiscal.append({"role": "bot", "text": resp})
            st.rerun()

    if st.session_state.historial_fiscal:
        if st.button("🗑️ Limpiar historial"):
            st.session_state.historial_fiscal = []
            st.rerun()


# ── Resultado y guardado ───────────────────────────────────────────────────────
# ── Mensaje de éxito y deshacer ───────────────────────────────────────────────
if st.session_state.ultimo_guardado:
    ug = st.session_state.ultimo_guardado
    st.markdown(f'<div class="success-box">✅ Guardado correctamente — {ug["nro_filas"]} producto(s) — Total: ${ug["total"]:,.2f}</div>', unsafe_allow_html=True)
    if st.button("↩️ Deshacer último guardado"):
        if sheets_ok:
            try:
                ws = get_or_create_sheet(gc)
                filas_total = len(ws.get_all_values())
                for _ in range(ug["nro_filas"]):
                    ws.delete_rows(filas_total)
                    filas_total -= 1
                st.session_state.ultimo_guardado = None
                st.success("↩️ Filas eliminadas. Podés volver a cargar la venta.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al deshacer: {e}")
        else:
            st.warning("Google Sheets no configurado.")

datos_procesados = st.session_state.datos_procesados
fuente_actual = st.session_state.fuente_actual
if datos_procesados:
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
        cond = st.selectbox("Condición IVA del cliente", cond_opts, index=cond_opts.index(cond_val) if cond_val in cond_opts else 0)
        datos_procesados["condicion_iva"] = cond
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Productos**")
        productos = datos_procesados.get("productos", [])
        total = 0
        for p in productos:
            precio_aplicado = p.get("precio_aplicado") or p.get("precio_unitario") or 0
            sub = (p.get("cantidad") or 1) * precio_aplicado
            total += sub

            if p.get("promo_activa"):
                precio_normal = p.get("precio_normal", 0)
                st.markdown(
                    f'<div class="producto-promo">🏷️ <b>{p.get("descripcion","")}</b> — '
                    f'{p.get("cantidad") or 1} {p.get("unidad","")} × '
                    f'<span class="precio-normal">${precio_normal:,.0f}</span> '
                    f'<span class="precio-promo">${precio_aplicado:,.2f}</span> '
                    f'({p.get("promo_desc","")}) = <b>${sub:,.2f}</b></div>',
                    unsafe_allow_html=True
                )
            elif not precio_aplicado:
                st.markdown(
                    f'<div class="producto-sin-precio">⚠️ <b>{p.get("descripcion","")}</b> — '
                    f'{p.get("cantidad") or 1} {p.get("unidad","")} × precio a confirmar</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="producto-row">🥬 <b>{p.get("descripcion","")}</b> — '
                    f'{p.get("cantidad") or 1} {p.get("unidad","")} × ${precio_aplicado:,.2f} = <b>${sub:,.2f}</b></div>',
                    unsafe_allow_html=True
                )

        st.markdown(f'<div class="total-box">TOTAL: ${total:,.2f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    obs = st.text_input("Observaciones", value=datos_procesados.get("observaciones") or "")
    datos_procesados["observaciones"] = obs

    if st.button("💾 Confirmar y guardar en Sheets"):
        if not sheets_ok:
            st.warning("Google Sheets no está configurado. Revisá los Secrets.")
        else:
            with st.spinner("Guardando..."):
                try:
                    ws = get_or_create_sheet(gc, sheet_name)
                    total_g, n = guardar_en_sheets(ws, datos_procesados, nro_comprobante, fuente_actual, st.session_state.perfil)
                    st.session_state.ultimo_guardado = {"nro_filas": n, "total": total_g, "nro_comprobante": nro_comprobante}
                    st.session_state.datos_procesados = None
                    st.session_state.fuente_actual = ""
                    st.rerun()
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error al guardar: {e}</div>', unsafe_allow_html=True)
