import streamlit as st
import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from google.genai import types as gtypes
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RegistroVentas IA",
    page_icon="🛒",
    layout="wide",
)

# CSS personalizado
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Space Mono', monospace !important;
}

.stApp {
    background-color: #0f1117;
    color: #e8e8e8;
}

.main-header {
    font-family: 'Space Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #00e5a0;
    letter-spacing: -1px;
    margin-bottom: 0;
}

.sub-header {
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    color: #888;
    margin-bottom: 2rem;
}

.card {
    background: #1a1d27;
    border: 1px solid #2a2d3a;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.tag {
    display: inline-block;
    background: #00e5a020;
    color: #00e5a0;
    border: 1px solid #00e5a040;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.75rem;
    font-family: 'Space Mono', monospace;
    margin-bottom: 1rem;
}

.producto-row {
    background: #12141e;
    border: 1px solid #2a2d3a;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.total-box {
    background: #00e5a015;
    border: 1px solid #00e5a040;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    font-family: 'Space Mono', monospace;
    font-size: 1.1rem;
    color: #00e5a0;
    margin-top: 1rem;
}

.stButton > button {
    background: #00e5a0 !important;
    color: #0f1117 !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important;
    font-size: 0.85rem !important;
    transition: all 0.2s !important;
}

.stButton > button:hover {
    background: #00c484 !important;
    transform: translateY(-1px) !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #1a1d27 !important;
    border: 1px solid #2a2d3a !important;
    color: #e8e8e8 !important;
    border-radius: 8px !important;
}

.stFileUploader > div {
    background: #1a1d27 !important;
    border: 1px dashed #2a2d3a !important;
    border-radius: 8px !important;
}

div[data-testid="stSidebar"] {
    background: #12141e !important;
    border-right: 1px solid #2a2d3a !important;
}

.success-box {
    background: #00e5a015;
    border: 1px solid #00e5a0;
    border-radius: 10px;
    padding: 1rem;
    color: #00e5a0;
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
}

.error-box {
    background: #ff4b4b15;
    border: 1px solid #ff4b4b;
    border-radius: 10px;
    padding: 1rem;
    color: #ff4b4b;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ── Inicializar Gemini ─────────────────────────────────────────────────────────
@st.cache_resource
def init_gemini():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Falta GEMINI_API_KEY en los secrets.")
        st.stop()
    return genai.Client(api_key=api_key)


# ── Inicializar Google Sheets ──────────────────────────────────────────────────
@st.cache_resource
def init_sheets():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        return None


def get_or_create_sheet(gc, sheet_name: str):
    """Abre o crea la hoja y garantiza los encabezados."""
    headers = [
        "Fecha", "Hora", "Nro_Comprobante", "Tipo_Comprobante",
        "Cliente", "CUIT_DNI", "Condicion_IVA",
        "Producto", "Cantidad", "Unidad", "Precio_Unitario",
        "Subtotal_Linea", "Total_Venta", "Observaciones", "Fuente"
    ]
    try:
        sh = gc.open(sheet_name)
        ws = sh.sheet1
    except gspread.SpreadsheetNotFound:
        sh = gc.create(sheet_name)
        sh.share(None, perm_type="anyone", role="writer")
        ws = sh.sheet1
        ws.append_row(headers)
    # Verificar que tenga encabezados
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(headers)
    return ws


# ── Prompt para Gemini ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Sos un asistente contable para monotributistas argentinos.
Tu tarea es extraer datos de ventas para emitir facturas válidas ante ARCA.
Analizá el mensaje (texto, audio transcripto o imagen de ticket/remito) y devolvé ÚNICAMENTE un JSON con esta estructura:

{
  "tipo_comprobante": "Factura C" | "Ticket" | "Remito" | "Otro",
  "cliente": "nombre o razón social, null si no se menciona",
  "cuit_dni": "número, null si no se menciona",
  "condicion_iva": "Consumidor Final" | "Responsable Inscripto" | "Monotributista" | "Exento" | "No especificado",
  "productos": [
    {
      "descripcion": "nombre del producto",
      "cantidad": número,
      "unidad": "kg" | "unidad" | "litro" | "docena" | "atado" | "bolsa" | "otro",
      "precio_unitario": número
    }
  ],
  "observaciones": "cualquier info extra relevante o null"
}

Reglas:
- Si el precio total de una línea está dado pero no el unitario, calculá el unitario dividiendo.
- Si la unidad no se especifica, usá "unidad".
- Si es una verdulería, los productos típicos son frutas, verduras, etc.
- Respondé SOLO con el JSON, sin texto adicional, sin markdown, sin backticks.
"""


def procesar_con_gemini(client, contenido, tipo: str) -> dict:
    """Llama a Gemini y parsea el JSON de vuelta."""
    try:
        if tipo == "texto":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[SYSTEM_PROMPT, contenido],
            )
        elif tipo == "audio":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    SYSTEM_PROMPT,
                    "Primero transcribí el audio y luego extraé los datos de venta.",
                    contenido,  # gtypes.Part con el audio
                ],
            )
        elif tipo == "imagen":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    SYSTEM_PROMPT,
                    "Analizá esta imagen (ticket, remito o foto de venta) y extraé los datos.",
                    contenido,  # gtypes.Part con la imagen
                ],
            )
        raw = response.text.strip()
        # Limpiar posibles backticks
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        st.error("Gemini no devolvió un JSON válido. Intentá de nuevo.")
        st.code(response.text)
        return None
    except Exception as e:
        st.error(f"Error al procesar con Gemini: {e}")
        return None


def guardar_en_sheets(ws, datos: dict, nro_comprobante: str, fuente: str):
    """Guarda una fila por producto en Google Sheets."""
    ahora = datetime.now()
    fecha = ahora.strftime("%d/%m/%Y")
    hora = ahora.strftime("%H:%M")

    productos = datos.get("productos", [])
    total_venta = sum(
        p.get("cantidad", 1) * p.get("precio_unitario", 0)
        for p in productos
    )

    rows = []
    for p in productos:
        subtotal = p.get("cantidad", 1) * p.get("precio_unitario", 0)
        rows.append([
            fecha,
            hora,
            nro_comprobante,
            datos.get("tipo_comprobante", ""),
            datos.get("cliente") or "Consumidor Final",
            datos.get("cuit_dni") or "",
            datos.get("condicion_iva", "No especificado"),
            p.get("descripcion", ""),
            p.get("cantidad", ""),
            p.get("unidad", ""),
            p.get("precio_unitario", ""),
            round(subtotal, 2),
            round(total_venta, 2),
            datos.get("observaciones") or "",
            fuente,
        ])

    for row in rows:
        ws.append_row(row)

    return total_venta, len(rows)


# ── UI Principal ───────────────────────────────────────────────────────────────
client = init_gemini()
gc = init_sheets()

# Sidebar
with st.sidebar:
    st.markdown('<p style="font-family:Space Mono;color:#00e5a0;font-weight:700;font-size:1.1rem;">⚙️ Configuración</p>', unsafe_allow_html=True)

    sheet_name = st.text_input(
        "Nombre del Google Sheet",
        value="Ventas_Verduleria",
        help="Si no existe, se crea automáticamente.",
    )

    nro_comprobante = st.text_input(
        "Nro. de Comprobante",
        value=f"C-{datetime.now().strftime('%Y%m%d%H%M')}",
    )

    st.markdown("---")
    st.markdown('<p style="color:#888;font-size:0.8rem;">Conectado a Google Sheets via Service Account.<br>Configurá <code>gcp_service_account</code> en los Secrets.</p>', unsafe_allow_html=True)

    sheets_ok = gc is not None
    if sheets_ok:
        st.markdown('<p style="color:#00e5a0;font-size:0.85rem;">✅ Google Sheets conectado</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color:#ff4b4b;font-size:0.85rem;">❌ Google Sheets no configurado<br>(los datos se mostrarán pero no se guardarán)</p>', unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">🛒 RegistroVentas IA</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Cargá tus ventas por texto, audio o foto — la IA extrae los datos y los guarda en tu planilla.</p>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3 = st.tabs(["📝 Texto", "🎙️ Audio", "📷 Imagen"])

datos_procesados = None
fuente_actual = ""

# ── Tab 1: Texto ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="tag">ENTRADA DE TEXTO</div>', unsafe_allow_html=True)
    st.markdown("Escribí la venta como si le mandaras un mensaje a alguien. Ejemplos:")
    st.markdown("""
    > *"Vendí 3kg de tomate a $500 el kilo, 1 lechuga a $300 y 2 docenas de huevos a $1200 la docena. Cliente: Juan Pérez, DNI 12345678"*
    
    > *"Factura C a La Huerta SRL, CUIT 30-12345678-9. 10kg papa $180/kg, 5kg cebolla $220/kg"*
    """)

    texto_input = st.text_area("Tu mensaje de venta:", height=120, placeholder="Escribí acá el detalle de la venta...")

    if st.button("Procesar texto →", key="btn_texto"):
        if texto_input.strip():
            with st.spinner("Gemini analizando..."):
                datos_procesados = procesar_con_gemini(client, texto_input.strip(), "texto")
                fuente_actual = "texto"
        else:
            st.warning("Escribí algo primero.")

# ── Tab 2: Audio ───────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="tag">ENTRADA DE AUDIO</div>', unsafe_allow_html=True)
    st.markdown("Subí un audio de WhatsApp (.ogg, .mp3, .wav, .m4a) contando la venta.")

    audio_file = st.file_uploader("Seleccioná el audio:", type=["ogg", "mp3", "wav", "m4a", "webm"])

    if audio_file:
        st.audio(audio_file)

        if st.button("Procesar audio →", key="btn_audio"):
            with st.spinner("Gemini transcribiendo y analizando..."):
                audio_bytes = audio_file.read()
                ext = audio_file.name.split(".")[-1].lower()
                mime_map = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "webm": "audio/webm"}
                mime = mime_map.get(ext, "audio/ogg")
                audio_part = gtypes.Part.from_bytes(data=audio_bytes, mime_type=mime)
                datos_procesados = procesar_con_gemini(client, audio_part, "audio")
                fuente_actual = "audio"

# ── Tab 3: Imagen ──────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="tag">ENTRADA DE IMAGEN</div>', unsafe_allow_html=True)
    st.markdown("Subí una foto de un ticket, remito o pizarra de precios.")

    img_file = st.file_uploader("Seleccioná la imagen:", type=["jpg", "jpeg", "png", "webp"])

    if img_file:
        st.image(img_file, width=350)

        if st.button("Procesar imagen →", key="btn_imagen"):
            with st.spinner("Gemini analizando imagen..."):
                img_bytes = img_file.read()
                ext = img_file.name.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                img_part = gtypes.Part.from_bytes(data=img_bytes, mime_type=mime)
                datos_procesados = procesar_con_gemini(client, img_part, "imagen")
                fuente_actual = "imagen"

# ── Resultado y guardado ───────────────────────────────────────────────────────
if datos_procesados:
    st.markdown("---")
    st.markdown("### 📋 Datos extraídos por la IA")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Comprobante**")
        tc = st.selectbox("Tipo", ["Factura C", "Ticket", "Remito", "Otro"],
                          index=["Factura C", "Ticket", "Remito", "Otro"].index(datos_procesados.get("tipo_comprobante", "Factura C")) if datos_procesados.get("tipo_comprobante") in ["Factura C", "Ticket", "Remito", "Otro"] else 0)
        datos_procesados["tipo_comprobante"] = tc

        cliente = st.text_input("Cliente", value=datos_procesados.get("cliente") or "Consumidor Final")
        datos_procesados["cliente"] = cliente

        cuit = st.text_input("CUIT / DNI", value=datos_procesados.get("cuit_dni") or "")
        datos_procesados["cuit_dni"] = cuit

        cond_options = ["Consumidor Final", "Responsable Inscripto", "Monotributista", "Exento", "No especificado"]
        cond_val = datos_procesados.get("condicion_iva", "Consumidor Final")
        cond = st.selectbox("Condición IVA", cond_options,
                            index=cond_options.index(cond_val) if cond_val in cond_options else 0)
        datos_procesados["condicion_iva"] = cond
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Productos detectados**")
        productos = datos_procesados.get("productos", [])
        total = 0
        for i, p in enumerate(productos):
            sub = p.get("cantidad", 0) * p.get("precio_unitario", 0)
            total += sub
            st.markdown(
                f'<div class="producto-row">🥬 <b>{p.get("descripcion", "")}</b> — '
                f'{p.get("cantidad", "")} {p.get("unidad", "")} × '
                f'${p.get("precio_unitario", 0):,.2f} = <b>${sub:,.2f}</b></div>',
                unsafe_allow_html=True
            )
        st.markdown(f'<div class="total-box">TOTAL: ${total:,.2f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    obs = st.text_input("Observaciones", value=datos_procesados.get("observaciones") or "")
    datos_procesados["observaciones"] = obs

    st.markdown("")
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        guardar = st.button("💾 Guardar en Sheets")

    if guardar:
        if not sheets_ok:
            st.warning("Google Sheets no está configurado. Revisá los Secrets.")
        else:
            with st.spinner("Guardando..."):
                try:
                    ws = get_or_create_sheet(gc, sheet_name)
                    total_guardado, n_filas = guardar_en_sheets(ws, datos_procesados, nro_comprobante, fuente_actual)
                    st.markdown(
                        f'<div class="success-box">✅ Guardado correctamente — {n_filas} producto(s) — Total: ${total_guardado:,.2f}</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error al guardar: {e}</div>', unsafe_allow_html=True)
