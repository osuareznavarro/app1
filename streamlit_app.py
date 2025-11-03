# app_feynman.py
import streamlit as st
from streamlit_drawable_canvas import st_canvas
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle
from PIL import Image
import io

st.set_page_config(page_title="Dibujador de Diagramas de Feynman", layout="wide")

st.title("🛠️ Dibujador interactivo de diagramas de Feynman (Streamlit)")

# --------- Configuración lateral ----------
st.sidebar.header("Herramientas y Partículas")

particle = st.sidebar.selectbox("Selecciona partícula / acción a dibujar:", [
    "vértice (vertex)",
    "fermion (→/←)",
    "antifermion (←/→)",
    "fotón (photon)",
    "gluón (gluon)",
    "línea neutra (línea simple)",
])

st.sidebar.markdown("**Instrucciones breves**")
st.sidebar.markdown("""
- Selecciona el **tipo de partícula** y luego dibuja con la herramienta correspondiente en el lienzo.
- Usa la **herramienta 'circle'** para marcar vértices/nodos.
- Usa la **herramienta 'line'** para dibujar propagadores (luego la app inferirá endpoints).
- Dibuja cada tipo en su **color** para ayudar a la detección automática.
- Cuando termines, pulsa **Reconstruir diagrama** para procesar los objetos, o **Exportar PNG** / **Generar TikZ**.
""")

# Colors assigned to particle types (hex)
color_map = {
    "vértice (vertex)": "#000000",       # negro (puntos)
    "fermion (→/←)": "#1f77b4",          # azul
    "antifermion (←/→)": "#ff7f0e",       # naranja
    "fotón (photon)": "#2ca02c",         # verde (se representará como onda)
    "gluón (gluon)": "#d62728",          # rojo (rizado aproximado)
    "línea neutra (línea simple)": "#9467bd" # morado
}

st.sidebar.markdown("**Colores (referencia)**")
for k, v in color_map.items():
    st.sidebar.write(f"<span style='color:{v}'>■</span> {k}", unsafe_allow_html=True)

# Canvas settings
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 400
stroke_width = st.sidebar.slider("Grosor del trazo", 1, 6, 3)

# Choose tool for drawing in canvas
tool = st.sidebar.selectbox("Herramienta del lienzo:", ["selection", "line", "rect", "circle", "freedraw", "eraser"])

# Set the stroke color according to selected particle for drawing
stroke_color = color_map[particle]

st.sidebar.markdown("---")
st.sidebar.markdown("Cuando cambies de tipo de partícula: selecciona el color en la paleta del lienzo para que los trazos tengan el color correcto (la app también establece el color inicial).")

# Create a drawable canvas
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",  # transparente
    stroke_width=stroke_width,
    stroke_color=stroke_color,
    background_color="#ffffff",
    update_streamlit=True,
    height=CANVAS_HEIGHT,
    width=CANVAS_WIDTH,
    drawing_mode=tool,
    key="canvas",
)

st.markdown("**Tips:** usa 'circle' para vértices (nodos) y 'line' para propagadores. Cambia el 'particle' en la barra lateral antes de dibujar un nuevo tipo para que el color se asocie correctamente.")

# --------- Procesamiento de objetos dibujados ----------
def parse_canvas_objects(json_data):
    """
    Extrae nodos y aristas desde json_data de st_canvas.
    Retorna:
      - nodes: lista de dicts {'id', 'x','y', 'type'}
      - edges: lista de dicts {'x1','y1','x2','y2', 'type'}
    Detecta tipo por color de stroke.
    """
    if not json_data or "objects" not in json_data:
        return [], []

    objects = json_data["objects"]
    nodes = []
    edges = []

    # función auxiliar para mapear color a tipo
    def color_to_type(hexcolor):
        for k, v in color_map.items():
            if v.lower() == (hexcolor or "").lower():
                return k
        # si no coincide exactamente, intenta comparar por substring
        for k, v in color_map.items():
            if v.lower().lstrip("#") in (hexcolor or "").lower():
                return k
        return "desconocido"

    node_id = 0
    for obj in objects:
        typ = obj.get("type")
        stroke = obj.get("stroke", "").lower() if obj.get("stroke") else obj.get("strokeStyle", "").lower() if obj.get("strokeStyle") else ""
        if typ == "circle" or typ == "ellipse":
            # canvas: left, top, radiusX, radiusY
            left = obj.get("left", 0)
            top = obj.get("top", 0)
            rx = obj.get("radiusX", obj.get("rx", 10))
            ry = obj.get("radiusY", obj.get("ry", 10))
            cx = left + rx
            cy = top + ry
            nodes.append({
                "id": node_id,
                "x": cx,
                "y": cy,
                "type": color_to_type(stroke),
                "raw": obj
            })
            node_id += 1
        elif typ == "line" or typ == "path":
            # Fabric.js line: x1,y1,x2,y2 OR path objects can be approximated
            x1 = obj.get("x1")
            y1 = obj.get("y1")
            x2 = obj.get("x2")
            y2 = obj.get("y2")
            if x1 is None:
                # try path -> approximate by bounding box or first/last points
                left = obj.get("left", 0); top = obj.get("top", 0)
                points = obj.get("points") or []
                if points and isinstance(points, list) and len(points) >= 2:
                    p0 = points[0]; pN = points[-1]
                    x1, y1 = left + p0.get("x", 0), top + p0.get("y", 0)
                    x2, y2 = left + pN.get("x", 0), top + pN.get("y", 0)
                else:
                    # fallback: use left/top and width/height
                    w = obj.get("width", 0); h = obj.get("height", 0)
                    x1, y1, x2, y2 = left, top, left + w, top + h
            edges.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "type": color_to_type(stroke),
                "raw": obj
            })
        # ignoramos rect/freedraw/others en el parseado por ahora
    return nodes, edges

nodes, edges = parse_canvas_objects(canvas_result.json_data if canvas_result else None)

st.markdown("### Vista rápida del diagrama detectado")
st.write(f"Vértices detectados: {len(nodes)} — propagadores detectados: {len(edges)}")

if len(nodes) > 0:
    cols = st.columns(min(4, len(nodes)))
    for i, n in enumerate(nodes):
        cols[i % len(cols)].write(f"Node {n['id']}: ({int(n['x'])}, {int(n['y'])}) — {n['type']}")

if len(edges) > 0:
    cols2 = st.columns(min(4, len(edges)))
    for i, e in enumerate(edges):
        cols2[i % len(cols2)].write(f"Edge {i}: ({int(e['x1'])},{int(e['y1'])}) → ({int(e['x2'])},{int(e['y2'])}) — {e['type']}")

# --------- Función para dibujar con matplotlib (y exportar PNG) ----------
def render_diagram_matplotlib(nodes, edges, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, dpi=100):
    fig, ax = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)  # invertir y para que origen top-left como canvas
    ax.axis("off")

    # Dibujar edges
    for e in edges:
        x1, y1, x2, y2 = e["x1"], e["y1"], e["x2"], e["y2"]
        typ = e["type"]
        color = "#222222"
        style = "solid"
        arrow = False

        if "fermion" in typ:
            color = color_map["fermion (→/←)"]
            arrow = True
            style = "solid"
        elif "antifermion" in typ:
            color = color_map["antifermion (←/→)"]
            arrow = True
            style = "solid"
        elif "fotón" in typ or "photon" in typ:
            color = color_map["fotón (photon)"]
            style = "dashdot"
            arrow = False
        elif "gluón" in typ:
            color = color_map["gluón (gluon)"]
            style = "dashed"
            arrow = False
        elif "línea neutra" in typ:
            color = color_map["línea neutra (línea simple)"]
            style = "solid"
            arrow = False

        # Dibujar línea
        ax.plot([x1, x2], [y1, y2], linestyle=style, linewidth=2, color=color)

        # Si es fermion, añadir flecha
        if arrow:
            # posición de la flecha: 70% del camino
            sx, sy = x1 + 0.7*(x2-x1), y1 + 0.7*(y2-y1)
            dx, dy = (x2-x1)*0.001, (y2-y1)*0.001
            arr = FancyArrowPatch((sx, sy), (sx+dx, sy+dy),
                                 arrowstyle='-|>', mutation_scale=15, color=color, linewidth=0)
            ax.add_patch(arr)

    # Dibujar nodes
    for n in nodes:
        cx, cy = n["x"], n["y"]
        ax.add_patch(Circle((cx, cy), radius=8, color="k", zorder=5))
        # etiqueta con tipo abreviado
        short = n["type"].split()[0] if n["type"] != "desconocido" else "N"
        ax.text(cx+10, cy-10, short, fontsize=8)

    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, bbox_inches='tight', pad_inches=0.01)
    buf.seek(0)
    img = Image.open(buf)
    plt.close(fig)
    return img

# Buttons to generate outputs
col_gen, col_tikz, col_png = st.columns(3)
with col_gen:
    if st.button("🔁 Reconstruir diagrama (actualizar vista)"):
        st.success("Diagrama reconstruido a partir del lienzo. Revisa las listas arriba para confirmar nodos/aristas.")

with col_png:
    if st.button("📤 Exportar PNG"):
        if len(nodes) + len(edges) == 0:
            st.error("No hay objetos en el lienzo para exportar.")
        else:
            im = render_diagram_matplotlib(nodes, edges)
            bio = io.BytesIO()
            im.save(bio, format="PNG")
            st.image(im, caption="Diagrama exportado (previsualización)")
            st.download_button("Descargar PNG", data=bio.getvalue(), file_name="diagrama_feynman.png", mime="image/png")

# --------- Generador simple de TikZ (no usa tikz-feynman, genera tikz directo) ----------
def generate_tikz(nodes, edges, width=CANVAS_WIDTH, height=CANVAS_HEIGHT):
    """
    Genera un bloque de TikZ con nodos y aristas.
    Usa: \usetikzlibrary{decorations.pathmorphing,arrows.meta}
    """
    scale_x = 10  # factor para convertir pix -> cm (ajustable)
    scale_y = 10

    header = ("% TikZ generado automáticamente\n"
              "\\begin{tikzpicture}[scale=0.035, >=Stealth]\n"
              "\\tikzset{photon/.style={decorate, decoration={snake, amplitude=1.2mm}, line width=1pt}}\n"
              "\\tikzset{gluon/.style={decorate, decoration={coil, aspect=0.6, segment length=2pt}, line width=1pt}}\n")

    node_lines = []
    for n in nodes:
        x = n["x"]
        y = n["y"]
        # invertir Y para coordenadas tikz-friendly
        ty = height - y
        node_lines.append(f"\\node[draw, circle, inner sep=1pt] (n{n['id']}) at ({x:.1f},{ty:.1f}) {{{n['id']}}};")

    edge_lines = []
    for i, e in enumerate(edges):
        x1, y1, x2, y2 = e["x1"], e["y1"], e["x2"], e["y2"]
        ty1 = height - y1; ty2 = height - y2
        typ = e["type"]
        style = "->"  # default arrow
        extra = ""
        if "fotón" in typ or "photon" in typ:
            style = ""
            extra = "[photon]"
        elif "gluón" in typ:
            style = ""
            extra = "[gluon]"
        elif "fermion" in typ:
            style = "->"
        elif "antifermion" in typ:
            style = "<-"
        elif "línea neutra" in typ:
            style = ""

        edge_lines.append(f"\\draw{extra} ({x1:.1f},{ty1:.1f}) {style} -- ({x2:.1f},{ty2:.1f});")

    footer = "\\end{tikzpicture}\n"
    tikz_code = header + "\n".join(node_lines) + "\n" + "\n".join(edge_lines) + "\n" + footer
    return tikz_code

with col_tikz:
    if st.button("🧾 Generar código TikZ"):
        if len(nodes) + len(edges) == 0:
            st.error("No hay objetos para convertir a TikZ.")
        else:
            tikz = generate_tikz(nodes, edges)
            st.code(tikz, language="tex")
            st.download_button("Descargar código .tex", data=tikz.encode("utf-8"), file_name="diagrama_feynman.tex", mime="text/x-tex")

st.markdown("---")
st.markdown("💡 **Sugerencias de uso / mejoras**:")
st.markdown("""
- Si quieres que el lienzo genere flechas automáticas en la misma acción, dibuja las líneas siempre con el color del tipo correspondiente.
- Puedes ampliar el generador de TikZ para que use `tikz-feynman` o `feynmp` y añadir etiquetas de partículas, números de momento, etc.
- La detección de nodos/aristas se basa en los objetos devueltos por `streamlit-drawable-canvas`. Si necesitas arrastrar nodos luego de crear, considera integrar un frontend JS más avanzado (por ejemplo, una app con Konva.js o Fabric.js personalizada).
""")
