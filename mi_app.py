import streamlit as st
import random
import os
from google import genai
from dotenv import load_dotenv

# ── Configuración ──────────────────────────────────────────────────────────────
load_dotenv()
client = genai.Client()  # toma GEMINI_API_KEY automáticamente del .env

st.set_page_config(page_title="App divertida con IA", layout="wide")


# ── Funciones auxiliares ────────────────────────────────────────────────────────
def build_markov(text):
    tokens = text.split()
    model = {}
    for i in range(len(tokens) - 1):
        key = tokens[i]
        model.setdefault(key, []).append(tokens[i + 1])
    return model


def generate_markov(model, length=30):
    if not model:
        return ""
    word = random.choice(list(model.keys()))
    words = [word]
    for _ in range(length - 1):
        nxt = model.get(word)
        if not nxt:
            break
        word = random.choice(nxt)
        words.append(word)
    return " ".join(words)


def rps_result(player, cpu):
    wins = {"Piedra": "Tijera", "Papel": "Piedra", "Tijera": "Papel"}
    if player == cpu:
        return "Empate"
    return "Ganas" if wins[player] == cpu else "Pierdes"


def pig_latin(s):
    def word_pl(w):
        vowels = "aeiouáéíóúAEIOUÁÉÍÓÚ"
        if w and w[0] in vowels:
            return w + "yay"
        return w[1:] + w[0] + "ay" if len(w) > 1 else w + "ay"
    return " ".join(word_pl(w) for w in s.split())


def gemini(prompt: str) -> str:
    """Llama a Gemini y devuelve el texto de respuesta."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


# ── Texto de ejemplo para Markov ───────────────────────────────────────────────
SAMPLE_TEXT = (
    "En un lugar de la mancha, de cuyo nombre no quiero acordarme, vivía un ingeniero curioso. "
    "Le gustaba programar, crear proyectos pequeños y aprender cosas nuevas cada día. "
    "A veces hacía experimentos locos y otras veces escribía poesía con código."
)


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Menú")
    page = st.radio(
        "Selecciona una sección:",
        [
            "Generador de frases",
            "Transforma texto",
            "Juego R/P/T",
            "Tareas",
            "Imágenes",
            "💬 Chat con Gemini",
            "✨ Gemini en acción",
        ],
    )
    st.markdown("---")
    st.write("Ajustes rápidos:")
    seed = st.slider("Longitud de generación (frases)", 5, 80, 25)
    st.write("Diviértete y explora :)")

st.title("🎉 App divertida con Streamlit + Gemini")
st.write("Transforma texto, juega, sube imágenes, chatea con IA y más.")


# ── Sección 1: Generador de frases (Markov) ────────────────────────────────────
if page == "Generador de frases":
    st.header("Generador de frases estilo Markov (simple)")
    custom = st.text_area(
        "Escribe un texto para entrenar el generador (o usa el texto de ejemplo):",
        value=SAMPLE_TEXT,
        height=200,
    )
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("Generar frase"):
            model = build_markov(custom)
            frase = generate_markov(model, length=seed)
            st.success(frase)
    with col2:
        if st.button("Frase sorpresa"):
            model = build_markov(custom)
            frase = generate_markov(model, length=random.randint(6, seed))
            st.info(frase)


# ── Sección 2: Transforma texto ────────────────────────────────────────────────
elif page == "Transforma texto":
    st.header("Transformaciones divertidas de texto")
    t = st.text_area("Escribe algo:")
    ops = st.multiselect(
        "Operaciones:",
        ["MAYÚSCULAS", "minúsculas", "Revertir", "Pig Latin", "🤖 Reescribir con Gemini"],
        default=["MAYÚSCULAS"],
    )

    estilo = None
    if "🤖 Reescribir con Gemini" in ops:
        estilo = st.selectbox(
            "Estilo de reescritura:",
            ["formal", "poético", "humorístico", "como pirata", "muy simple (para niños)"],
        )

    if st.button("Aplicar"):
        out = t
        if "MAYÚSCULAS" in ops:
            out = out.upper()
        if "minúsculas" in ops:
            out = out.lower()
        if "Revertir" in ops:
            out = out[::-1]
        if "Pig Latin" in ops:
            out = pig_latin(out)
        if "🤖 Reescribir con Gemini" in ops and estilo:
            with st.spinner("Gemini reescribiendo..."):
                try:
                    prompt = f"Reescribe el siguiente texto en estilo {estilo}. Devuelve solo el texto reescrito, sin explicaciones:\n\n{out}"
                    out = gemini(prompt)
                except Exception as e:
                    st.error(f"Error con Gemini: {e}")
        st.code(out)


# ── Sección 3: Piedra / Papel / Tijera ────────────────────────────────────────
elif page == "Juego R/P/T":
    st.header("Piedra / Papel / Tijera")
    choice = st.radio("Elige tu jugada:", ["Piedra", "Papel", "Tijera"])
    if st.button("Jugar"):
        cpu = random.choice(["Piedra", "Papel", "Tijera"])
        resultado = rps_result(choice, cpu)
        emojis = {"Ganas": "🎉", "Pierdes": "😅", "Empate": "🤝"}
        st.write(f"Tú: **{choice}**  —  CPU: **{cpu}**")
        st.markdown(f"### {resultado} {emojis[resultado]}")


# ── Sección 4: Tareas ──────────────────────────────────────────────────────────
elif page == "Tareas":
    st.header("Lista de tareas rápida")

    if "todos" not in st.session_state:
        st.session_state["todos"] = []

    with st.form("add_form", clear_on_submit=True):
        nueva = st.text_input("Agregar tarea:")
        submitted = st.form_submit_button("Agregar")
        if submitted and nueva:
            st.session_state.todos.append(nueva)

    for i, tsk in enumerate(st.session_state.todos):
        cols = st.columns([0.85, 0.1, 0.05])
        cols[0].write(f"- {tsk}")
        if cols[1].button("❌", key=f"del_{i}"):
            st.session_state.todos.pop(i)
            st.rerun()

    # Botón para que Gemini sugiera prioridades
    if st.session_state.todos and st.button("🤖 Gemini: sugerí prioridades"):
        with st.spinner("Analizando tus tareas..."):
            try:
                lista = "\n".join(f"- {t}" for t in st.session_state.todos)
                prompt = (
                    f"Tengo estas tareas pendientes:\n{lista}\n\n"
                    "Ordenálas por prioridad (alta / media / baja) y justificá brevemente cada una. "
                    "Respondé en español."
                )
                sugerencia = gemini(prompt)
                st.info(sugerencia)
            except Exception as e:
                st.error(f"Error con Gemini: {e}")


# ── Sección 5: Imágenes ────────────────────────────────────────────────────────
elif page == "Imágenes":
    st.header("Sube una imagen y describila con Gemini")
    uploaded = st.file_uploader(
        "Selecciona una imagen", type=["png", "jpg", "jpeg", "gif"]
    )
    if uploaded is not None:
        bytes_data = uploaded.read()
        st.image(bytes_data, caption="Tu imagen", use_container_width=True)
        st.download_button("Descargar imagen", data=bytes_data, file_name=uploaded.name)

        # Descripción con Gemini Vision
        if st.button("🤖 Gemini: describí esta imagen"):
            with st.spinner("Analizando imagen..."):
                try:
                    import base64
                    b64 = base64.standard_b64encode(bytes_data).decode()
                    ext = uploaded.name.split(".")[-1].lower()
                    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

                    from google.genai import types as gtypes
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            gtypes.Part.from_bytes(data=bytes_data, mime_type=mime),
                            "Describí esta imagen en detalle. Respondé en español.",
                        ],
                    )
                    st.success(response.text)
                except Exception as e:
                    st.error(f"Error con Gemini Vision: {e}")


# ── Sección 6: Chat con Gemini ─────────────────────────────────────────────────
elif page == "💬 Chat con Gemini":
    st.header("💬 Chat con Gemini")

    if "historial" not in st.session_state:
        st.session_state.historial = []

    # Mostrar historial
    for mensaje in st.session_state.historial:
        if mensaje["role"] == "user":
            st.chat_message("user").write(mensaje["text"])
        else:
            st.chat_message("assistant").write(mensaje["text"])

    # Input
    pregunta = st.chat_input("Escribí tu mensaje...")
    if pregunta:
        st.session_state.historial.append({"role": "user", "text": pregunta})
        st.chat_message("user").write(pregunta)

        with st.spinner("Gemini está pensando..."):
            try:
                # Construimos el contexto completo de la conversación
                contexto = "\n".join(
                    f"{'Usuario' if m['role'] == 'user' else 'Asistente'}: {m['text']}"
                    for m in st.session_state.historial
                )
                respuesta = gemini(contexto)
                st.session_state.historial.append({"role": "assistant", "text": respuesta})
                st.chat_message("assistant").write(respuesta)
            except Exception as e:
                st.error(f"Error al conectar con Gemini: {e}")

    if st.button("🗑️ Limpiar historial"):
        st.session_state.historial = []
        st.rerun()


# ── Sección 7: Gemini en acción ────────────────────────────────────────────────
elif page == "✨ Gemini en acción":
    st.header("✨ Gemini en acción — ejemplos rápidos")
    st.write("Probá distintas capacidades de Gemini con un clic.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Resumidor")
        texto_resumir = st.text_area("Pegá un texto largo:", height=150)
        if st.button("Resumir"):
            if texto_resumir.strip():
                with st.spinner("Resumiendo..."):
                    try:
                        res = gemini(
                            f"Resumí el siguiente texto en 3 oraciones. Respondé en español:\n\n{texto_resumir}"
                        )
                        st.success(res)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Escribí algo primero.")

        st.subheader("💡 Generador de ideas")
        tema = st.text_input("Tema para generar ideas:")
        if st.button("Generar ideas"):
            if tema.strip():
                with st.spinner("Pensando..."):
                    try:
                        res = gemini(
                            f"Dame 5 ideas creativas sobre: {tema}. Respondé en español con una lista numerada."
                        )
                        st.info(res)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Escribí un tema primero.")

    with col2:
        st.subheader("🌍 Traductor")
        texto_traducir = st.text_area("Texto a traducir:", height=100)
        idioma_destino = st.selectbox(
            "Traducir al:",
            ["inglés", "portugués", "francés", "alemán", "japonés", "italiano"],
        )
        if st.button("Traducir"):
            if texto_traducir.strip():
                with st.spinner("Traduciendo..."):
                    try:
                        res = gemini(
                            f"Traducí el siguiente texto al {idioma_destino}. Devolvé solo la traducción:\n\n{texto_traducir}"
                        )
                        st.success(res)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Escribí algo primero.")

        st.subheader("🎭 Generador de chistes")
        tema_chiste = st.text_input("Tema del chiste (opcional):")
        if st.button("Contame un chiste"):
            with st.spinner("Preparando el chiste..."):
                try:
                    prompt = (
                        f"Contame un chiste corto y gracioso sobre {tema_chiste}. Respondé en español."
                        if tema_chiste.strip()
                        else "Contame un chiste corto y gracioso. Respondé en español."
                    )
                    res = gemini(prompt)
                    st.success(res)
                except Exception as e:
                    st.error(f"Error: {e}")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.write("Creado para una clase: ¡hazlo tuyo!")