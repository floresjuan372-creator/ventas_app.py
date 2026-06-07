import streamlit as st
import os
import json
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Space Mono', monospace !important; }

.stApp { background-color: #0f1117; color: #e8e8e8; }

.main-header {
    font-family: 'Space Mono', monospace;
    font-size: 2rem; font-weight: 700;
    color: #00e5a0; letter-spacing: -1px; margin-bottom: 0;
}
.sub-header { font-size: 1rem; color: #888; margin-bottom: 2rem; }

.card {
    background: #1a1d27; border: 1px solid #2a2d3a;
    border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
}
.tag {
    display: inline-block; background: #00e5a020; color: #00e5a0;
    border: 1px solid #00e5a040; border-radius: 20px;
    padding: 2px 12px; font-size: 0.75rem;
    font-family: 'Space Mono', monospace; margin-bottom: 1rem;
}
.producto-row {
    background: #12141e; border: 1px solid #2a2d3a;
    border-radius: 8px; padding: 0.75rem 1rem;
    margin-bottom: 0.5rem; font-size: 0.9rem;
}
.total-box {
    background: #00e5a015; border: 1px solid #00e5a040;
    border-radius: 10px; padding: 1rem 1.5rem;
    font-family: 'Space Mono', monospace; font-size: 1.1rem;
    color: #00e5a0; margin-top: 1rem;
}
.perfil-box {
    background: #1a1d27; border: 1px solid #00e5a030;
    border-radius: 10px; padding: 1rem;
    font-size: 0.82rem; color: #aaa; margin-top: 0.5rem;
}
.perfil-box b { color: #00e5a0; }

.chat-user {
    background: #1e2235; border-radius: 10px 10px 2px 10px;
    padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.9rem;
    border-left: 3px solid #00e5a0;
}
.chat-bot {
    background: #12141e; border-radius: 10px 10px 10px 2px;
    padding: 0.75rem 1rem; margin: 0.5rem 0; font-size: 0.9rem;
    border-left: 3px solid #444;
}
.alerta-fiscal {
    background: #ffb30015; border: 1px solid #ffb300;
    border-radius: 10px; padding: 1rem; color: #ffb300;
    font-size: 0.88rem; margin-bottom: 1rem;
}

.stButton > button {
    background: #00e5a0 !important; color: #0f1117 !important;
    font-family: 'Space Mono', monospace !important; font-weight: 700 !important;
    border: none !important; border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important; font-size: 0.85rem !important;
}
.stButton > button:hover { background: #00c484 !important; }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #1a1d27 !important; border: 1px solid #2a2d3a !important;
    color: #e8e8e8 !important; border-radius: 8px !important;
}
.stFileUploader > div {
    background: #1a1d27 !important; border: 1px dashed #2a2d3a !important;
    border-radius: 8px !important;
}
div[data-testid="stSidebar"] {
    background: #12141e !important; border-right: 1px solid #2a2d3a !important;
}
.success-box {
    background: #00e5a015; border: 1px solid #00e5a0;
    border-radius: 10px; padding: 1rem; color: #00e5a0;
    font-family: 'Space Mono', monospace; font-size: 0.85rem;
}
.error-box {
    background: #ff4b4b15; border: 1px solid #ff4b4b;
    border-radius: 10px; padding: 1rem; color: #ff4b4b; font-size: 0.85rem;
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
    except Exception:
        return None


def get_or_create_sheet(gc, sheet_name: str):
    headers = [
        "Fecha", "Hora", "Nro_Comprobante", "Tipo_Comprobante",
        "Vendedor_CUIT", "Vendedor_Nombre", "Categoria_Monotributo",
        "Cliente", "CUIT_DNI_Cliente", "Condicion_IVA_Cliente",
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
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row(headers)
    return ws


# ── Prompts ────────────────────────────────────────────────────────────────────
VENTAS_PROMPT = """Sos un asistente contable para monotributistas argentinos, especializado en registrar ventas de forma flexible y tolerante.
Tu tarea es extraer datos de ventas para emitir facturas válidas ante ARCA, incluso cuando el mensaje es informal, incompleto, abreviado o con errores de tipeo.

Analizá el mensaje y devolvé ÚNICAMENTE un JSON con esta estructura:

{
  "tipo_comprobante": "Factura C" | "Ticket" | "Remito" | "Otro",
  "cliente": "nombre o razón social, null si no se menciona",
  "cuit_dni": "número, null si no se menciona",
  "condicion_iva": "Consumidor Final" | "Responsable Inscripto" | "Monotributista" | "Exento" | "No especificado",
  "productos": [
    {
      "descripcion": "nombre del producto",
      "cantidad": número o null,
      "unidad": "kg" | "unidad" | "litro" | "docena" | "atado" | "bolsa" | "otro",
      "precio_unitario": número o null
    }
  ],
  "observaciones": "cualquier info extra relevante o null"
}

Reglas:
- Si no se menciona precio → null (NO inventes precios).
- Si no se menciona cantidad → asumí 1.
- Inferí unidad por contexto: frutas/verduras → "kg", huevos → "docena", etc.
- Si el precio total está dado pero no el unitario → calculá dividiendo.
- Interpretá abreviaciones: "tom" → tomate, "zana" → zanahoria, "kg" → kilogramo.
- Interpretá precios sin símbolo: "500" → 500, "1k" → 1000, "1.200" → 1200.
- Tipo de comprobante por defecto para monotributistas: siempre "Factura C".
- Si no se menciona cliente → "Consumidor Final".
- Tolerá errores ortográficos, lunfardo, mensajes a las apuradas.
- Respondé SOLO con el JSON, sin texto adicional, sin markdown, sin backticks.
"""

def fiscal_system_prompt(perfil: dict) -> str:
    nombre = perfil.get("nombre_negocio") or "el negocio"
    cuit = perfil.get("cuit") or "no informado"
    categoria = perfil.get("categoria") or "no informada"
    rubro = perfil.get("rubro") or "verdulería"
    return f"""Sos un asistente fiscal especializado en monotributistas argentinos.
Respondés preguntas de empleados y dueños de negocios sobre facturación, comprobantes y obligaciones ante ARCA (ex-AFIP).

Datos del negocio:
- Nombre: {nombre}
- CUIT: {cuit}
- Régimen: Monotributista
- Categoría monotributo: {categoria}
- Rubro: {rubro}

Reglas para responder:
- Usá lenguaje simple y directo, como si explicaras a alguien sin conocimientos contables.
- Sé concreto: decí exactamente qué tiene que hacer el empleado.
- Si la pregunta es sobre tipo de comprobante, recordá siempre que los monotributistas SOLO emiten Factura C (nunca A ni B).
- Si te preguntan algo que excede tu conocimiento o requiere un contador, decilo claramente.
- Respondé en español rioplatense (vos, che, etc.).
- Máximo 5 oraciones por respuesta, salvo que sea muy complejo.
- Al final de cada respuesta, si es relevante, agregá un emoji de alerta ⚠️ con una advertencia práctica corta.
"""


# ── Funciones de procesamiento ─────────────────────────────────────────────────
def procesar_venta(client, contenido, tipo: str) -> dict:
    try:
        if tipo == "texto":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[VENTAS_PROMPT, contenido],
            )
        elif tipo == "audio":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[VENTAS_PROMPT, "Primero transcribí el audio y luego extraé los datos.", contenido],
            )
        elif tipo == "imagen":
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[VENTAS_PROMPT, "Analizá esta imagen y extraé los datos de venta.", contenido],
            )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        st.error("Gemini no devolvió un JSON válido. Intentá de nuevo.")
        st.code(response.text)
        return None
    except Exception as e:
        st.error(f"Error al procesar con Gemini: {e}")
        return None


def consulta_fiscal(client, pregunta: str, historial: list, perfil: dict) -> str:
    try:
        system = fiscal_system_prompt(perfil)
        messages = [system]
        for m in historial:
            messages.append(f"{'Empleado' if m['role'] == 'user' else 'Asistente'}: {m['text']}")
        messages.append(f"Empleado: {pregunta}")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="\n\n".join(messages),
        )
        return response.text
    except Exception as e:
        return f"Error al consultar: {e}"


def guardar_en_sheets(ws, datos: dict, nro_comprobante: str, fuente: str, perfil: dict):
    ahora = datetime.now()
    fecha = ahora.strftime("%d/%m/%Y")
    hora = ahora.strftime("%H:%M")
    productos = datos.get("productos", [])
    total_venta = sum(
        (p.get("cantidad") or 1) * (p.get("precio_unitario") or 0)
        for p in productos
    )
    rows = []
    for p in productos:
        subtotal = (p.get("cantidad") or 1) * (p.get("precio_unitario") or 0)
        rows.append([
            fecha, hora, nro_comprobante,
            datos.get("tipo_comprobante", ""),
            perfil.get("cuit", ""),
            perfil.get("nombre_negocio", ""),
            perfil.get("categoria", ""),
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


# ── Session state ──────────────────────────────────────────────────────────────
if "perfil" not in st.session_state:
    st.session_state.perfil = {
        "nombre_negocio": "",
        "cuit": "",
        "categoria": "C",
        "rubro": "Verdulería",
    }
if "historial_fiscal" not in st.session_state:
    st.session_state.historial_fiscal = []


# ── Inicializar servicios ──────────────────────────────────────────────────────
client = init_gemini()
gc = init_sheets()
sheets_ok = gc is not None

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-family:Space Mono;color:#00e5a0;font-weight:700;font-size:1.1rem;">🏪 Mi Negocio</p>', unsafe_allow_html=True)

    nombre_neg = st.text_input("Nombre del negocio", value=st.session_state.perfil["nombre_negocio"], placeholder="Ej: Verdulería Don José")
    cuit_neg = st.text_input("Mi CUIT", value=st.session_state.perfil["cuit"], placeholder="20-12345678-9")
    categoria_neg = st.selectbox(
        "Categoría Monotributo",
        ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"],
        index=["A","B","C","D","E","F","G","H","I","J","K"].index(st.session_state.perfil["categoria"]) if st.session_state.perfil["categoria"] in ["A","B","C","D","E","F","G","H","I","J","K"] else 2
    )
    rubro_neg = st.text_input("Rubro", value=st.session_state.perfil["rubro"], placeholder="Ej: Verdulería")

    if st.button("💾 Guardar perfil"):
        st.session_state.perfil = {
            "nombre_negocio": nombre_neg,
            "cuit": cuit_neg,
            "categoria": categoria_neg,
            "rubro": rubro_neg,
        }
        st.success("Perfil guardado!")

    # Mostrar perfil activo
    if st.session_state.perfil["nombre_negocio"]:
        p = st.session_state.perfil
        st.markdown(f"""
        <div class="perfil-box">
            <b>{p['nombre_negocio']}</b><br>
            CUIT: {p['cuit'] or '—'}<br>
            Monotributista Cat. <b>{p['categoria']}</b><br>
            Rubro: {p['rubro']}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    sheet_name = st.text_input("Google Sheet", value="Ventas_Verduleria")
    nro_comprobante = st.text_input("Nro. Comprobante", value=f"C-{datetime.now().strftime('%Y%m%d%H%M')}")

    if sheets_ok:
        st.markdown('<p style="color:#00e5a0;font-size:0.82rem;">✅ Google Sheets conectado</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color:#ff4b4b;font-size:0.82rem;">❌ Google Sheets no configurado</p>', unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🛒 RegistroVentas IA</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Registrá ventas por texto, audio o foto · Consultá dudas fiscales · Todo guardado en tu planilla</p>', unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📝 Texto", "🎙️ Audio", "📷 Imagen", "🧾 Consultas Fiscales"])

datos_procesados = None
fuente_actual = ""

# ── Tab 1: Texto ───────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="tag">REGISTRAR VENTA POR TEXTO</div>', unsafe_allow_html=True)
    st.markdown("Escribí la venta como si mandaras un mensaje. No importa si es informal o incompleto:")
    st.markdown("""
    > *"2 tom 3 papa"* · *"tomate 500 zana 300"* · *"fac a juan 2kg tomate 500"*
    > *"Vendí 3kg tomate $500/kg, 1 lechuga $300, 2 docenas huevo $1200"*
    """)
    texto_input = st.text_area("Tu mensaje:", height=100, placeholder="Escribí acá...")
    if st.button("Procesar →", key="btn_texto"):
        if texto_input.strip():
            with st.spinner("Analizando..."):
                datos_procesados = procesar_venta(client, texto_input.strip(), "texto")
                fuente_actual = "texto"
        else:
            st.warning("Escribí algo primero.")

# ── Tab 2: Audio ───────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="tag">REGISTRAR VENTA POR AUDIO</div>', unsafe_allow_html=True)
    st.markdown("Subí un audio de WhatsApp (.ogg, .mp3, .wav, .m4a) contando la venta.")
    audio_file = st.file_uploader("Seleccioná el audio:", type=["ogg", "mp3", "wav", "m4a", "webm"])
    if audio_file:
        st.audio(audio_file)
        if st.button("Procesar →", key="btn_audio"):
            with st.spinner("Transcribiendo y analizando..."):
                audio_bytes = audio_file.read()
                ext = audio_file.name.split(".")[-1].lower()
                mime_map = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "webm": "audio/webm"}
                mime = mime_map.get(ext, "audio/ogg")
                audio_part = gtypes.Part.from_bytes(data=audio_bytes, mime_type=mime)
                datos_procesados = procesar_venta(client, audio_part, "audio")
                fuente_actual = "audio"

# ── Tab 3: Imagen ──────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="tag">REGISTRAR VENTA POR IMAGEN</div>', unsafe_allow_html=True)
    st.markdown("Subí una foto de un ticket, remito o pizarra de precios.")
    img_file = st.file_uploader("Seleccioná la imagen:", type=["jpg", "jpeg", "png", "webp"])
    if img_file:
        st.image(img_file, width=350)
        if st.button("Procesar →", key="btn_imagen"):
            with st.spinner("Analizando imagen..."):
                img_bytes = img_file.read()
                ext = img_file.name.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                img_part = gtypes.Part.from_bytes(data=img_bytes, mime_type=mime)
                datos_procesados = procesar_venta(client, img_part, "imagen")
                fuente_actual = "imagen"

# ── Tab 4: Consultas Fiscales ──────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="tag">ASISTENTE FISCAL</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="alerta-fiscal">
    ⚠️ <b>Recordá siempre:</b> Como monotributista solo podés emitir <b>Factura C</b>.
    Nunca Factura A ni B. Si un cliente te pide Factura A, explicale que no corresponde.
    </div>
    """, unsafe_allow_html=True)

    # Preguntas frecuentes rápidas
    st.markdown("**Preguntas frecuentes — tocá una para consultar:**")
    preguntas_rapidas = [
        "¿Qué hago si me piden Factura A?",
        "¿Cuándo debo emitir un remito?",
        "¿Tengo que facturar si el cliente no pide comprobante?",
        "¿Qué pasa si supero el límite de mi categoría?",
        "¿Cómo facturo a una empresa (persona jurídica)?",
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

    # Historial del chat
    for m in st.session_state.historial_fiscal:
        if m["role"] == "user":
            st.markdown(f'<div class="chat-user">🙋 {m["text"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bot">🤖 {m["text"]}</div>', unsafe_allow_html=True)

    # Input libre
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
if datos_procesados:
    st.markdown("---")
    st.markdown("### 📋 Datos extraídos — revisá y confirmá")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Comprobante**")
        tc_opts = ["Factura C", "Ticket", "Remito", "Otro"]
        tc_val = datos_procesados.get("tipo_comprobante", "Factura C")
        tc = st.selectbox("Tipo", tc_opts, index=tc_opts.index(tc_val) if tc_val in tc_opts else 0)
        datos_procesados["tipo_comprobante"] = tc

        if tc != "Factura C":
            st.markdown('<div class="alerta-fiscal">⚠️ Como monotributista, lo más común es emitir <b>Factura C</b>.</div>', unsafe_allow_html=True)

        cliente = st.text_input("Cliente", value=datos_procesados.get("cliente") or "Consumidor Final")
        datos_procesados["cliente"] = cliente

        cuit = st.text_input("CUIT / DNI del cliente", value=datos_procesados.get("cuit_dni") or "")
        datos_procesados["cuit_dni"] = cuit

        cond_opts = ["Consumidor Final", "Responsable Inscripto", "Monotributista", "Exento", "No especificado"]
        cond_val = datos_procesados.get("condicion_iva", "Consumidor Final")
        cond = st.selectbox("Condición IVA del cliente", cond_opts, index=cond_opts.index(cond_val) if cond_val in cond_opts else 0)
        datos_procesados["condicion_iva"] = cond
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Productos detectados**")
        productos = datos_procesados.get("productos", [])
        total = 0
        for p in productos:
            sub = (p.get("cantidad") or 1) * (p.get("precio_unitario") or 0)
            total += sub
            precio_str = f"${p.get('precio_unitario'):,.2f}" if p.get("precio_unitario") else "⚠️ precio a confirmar"
            st.markdown(
                f'<div class="producto-row">🥬 <b>{p.get("descripcion", "")}</b> — '
                f'{p.get("cantidad") or 1} {p.get("unidad", "")} × '
                f'{precio_str} = <b>${sub:,.2f}</b></div>',
                unsafe_allow_html=True
            )
        st.markdown(f'<div class="total-box">TOTAL: ${total:,.2f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    obs = st.text_input("Observaciones", value=datos_procesados.get("observaciones") or "")
    datos_procesados["observaciones"] = obs

    st.markdown("")
    if st.button("💾 Confirmar y guardar en Sheets"):
        if not sheets_ok:
            st.warning("Google Sheets no está configurado. Revisá los Secrets.")
        else:
            with st.spinner("Guardando..."):
                try:
                    ws = get_or_create_sheet(gc, sheet_name)
                    total_g, n_filas = guardar_en_sheets(
                        ws, datos_procesados, nro_comprobante, fuente_actual, st.session_state.perfil
                    )
                    st.markdown(
                        f'<div class="success-box">✅ Guardado — {n_filas} producto(s) — Total: ${total_g:,.2f}</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.markdown(f'<div class="error-box">❌ Error al guardar: {e}</div>', unsafe_allow_html=True)
