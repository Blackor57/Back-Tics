# app/services/chart_generator.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Any, List
import uuid

# Configuración de estilo editorial y limpio
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
plt.rcParams['axes.edgecolor'] = '#E2E8F0'
plt.rcParams['axes.linewidth'] = 0.8


class ChartGenerator:
    """
    Generador de gráficos estadísticos con diseño moderno, paletas curadas y alta definición
    para inserción en informes ejecutivos Word y Excel.
    """

    @staticmethod
    def generar_grafico_categorias(categorias: List[Dict[str, Any]], output_dir: Path) -> Path:
        """
        Genera un gráfico de barras horizontales estilizado con porcentajes y cantidades.
        """
        nombres = [c.get("nombre", "General")[:28] for c in categorias[:8]]
        cantidades = [c.get("cantidad", 1) for c in categorias[:8]]
        porcentajes = [c.get("porcentaje", 0) for c in categorias[:8]]

        nombres.reverse()
        cantidades.reverse()
        porcentajes.reverse()

        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=160)
        fig.patch.set_facecolor('#FFFFFF')
        ax.set_facecolor('#FAFAFA')

        # Paleta de colores ejecutivos (Índigo degradado)
        paleta = ['#312E81', '#3730A3', '#4338CA', '#4F46E5', '#6366F1', '#818CF8', '#A5B4FC', '#C7D2FE']
        colores = [paleta[i % len(paleta)] for i in range(len(nombres))]

        barras = ax.barh(nombres, cantidades, color=colores, height=0.55, edgecolor='none')

        # Etiquetas con valor y porcentaje
        max_val = max(cantidades) if cantidades else 1
        for idx, barra in enumerate(barras):
            ancho = barra.get_width()
            pct_text = f"{int(ancho)} ({porcentajes[idx]}%)" if porcentajes[idx] else f"{int(ancho)}"
            ax.text(
                ancho + (max_val * 0.02),
                barra.get_y() + barra.get_height() / 2,
                pct_text,
                va='center', ha='left', fontsize=9, fontweight='bold', color='#1E293B'
            )

        ax.set_title("DISTRIBUCIÓN TEMÁTICA DE CONTENIDOS", fontsize=11, fontweight='bold', color='#0F172A', pad=14, loc='left')
        ax.set_xlabel("Frecuencia de Menciones", fontsize=9, color='#64748B', labelpad=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#CBD5E1')
        ax.spines['bottom'].set_color('#CBD5E1')
        ax.grid(axis='x', linestyle='--', alpha=0.6, color='#E2E8F0')
        ax.set_xlim(0, max_val * 1.25)
        plt.tight_layout()

        filename = output_dir / f"chart_cat_{uuid.uuid4().hex[:8]}.png"
        fig.savefig(filename, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return filename

    @staticmethod
    def generar_grafico_sentimientos(sentimientos: Dict[str, int], output_dir: Path) -> Path:
        """
        Genera un gráfico tipo Dona con el tono / sentimiento general detectado.
        """
        labels = []
        sizes = []
        colores_map = {
            "positivo": "#10B981",  # Verde esmeralda
            "neutro": "#64748B",    # Pizarra
            "negativo": "#F43F5E",  # Rosa/Rojo coral
            "critico": "#F59E0B"    # Ámbar
        }

        colores = []
        for k, v in sentimientos.items():
            if v > 0:
                labels.append(k.capitalize())
                sizes.append(v)
                colores.append(colores_map.get(k.lower(), "#3B82F6"))

        if not sizes:
            labels = ["Neutro"]
            sizes = [1]
            colores = ["#64748B"]

        fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=160)
        fig.patch.set_facecolor('#FFFFFF')

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            startangle=140,
            colors=colores,
            pctdistance=0.75,
            textprops={'fontsize': 9.5, 'color': '#0F172A', 'fontweight': '500'},
            wedgeprops={'edgecolor': 'white', 'linewidth': 2}
        )

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)

        # Efecto Dona profesional con métrica en el centro
        circulo_centro = plt.Circle((0, 0), 0.52, fc='#FFFFFF')
        fig.gca().add_artist(circulo_centro)
        ax.text(0, 0, f"TONO\n{sum(sizes)} items", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#475569')

        ax.set_title("EVALUACIÓN DEL TONO Y SENTIMIENTO", fontsize=11, fontweight='bold', color='#0F172A', pad=14, loc='center')
        plt.tight_layout()

        filename = output_dir / f"chart_sent_{uuid.uuid4().hex[:8]}.png"
        fig.savefig(filename, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return filename

    @staticmethod
    def generar_grafico_delta(delta: Dict[str, Any], output_dir: Path) -> Path:
        """
        Genera un gráfico de columnas para la comparativa temporal de novedades vs salidas.
        """
        nuevos = delta.get("total_nuevos", 0)
        salientes = delta.get("total_salientes", 0)
        mantenidos = delta.get("total_mantenidos", 0)

        categorias = ["Novedades (+)", "Salientes (-)", "Mantenidos (=)"]
        valores = [nuevos, salientes, mantenidos]
        colores = ["#10B981", "#F43F5E", "#0284C7"]

        fig, ax = plt.subplots(figsize=(6.8, 4.0), dpi=160)
        fig.patch.set_facecolor('#FFFFFF')
        ax.set_facecolor('#FAFAFA')

        barras = ax.bar(categorias, valores, color=colores, width=0.45, edgecolor='none')

        max_y = max(valores) if valores else 1
        for barra in barras:
            altura = barra.get_height()
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                altura + (max_y * 0.03),
                f'{int(altura)}',
                ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1E293B'
            )

        rotacion = delta.get("tasa_rotacion_pct", 0)
        ax.set_title(f"EVOLUCIÓN TEMPORAL (Tasa de Rotación: {rotacion}%)", fontsize=11, fontweight='bold', color='#0F172A', pad=14, loc='left')
        ax.set_ylabel("Cantidad de Elementos", fontsize=9, color='#64748B')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#CBD5E1')
        ax.spines['bottom'].set_color('#CBD5E1')
        ax.grid(axis='y', linestyle='--', alpha=0.6, color='#E2E8F0')
        ax.set_ylim(0, max_y * 1.25)
        plt.tight_layout()

        filename = output_dir / f"chart_delta_{uuid.uuid4().hex[:8]}.png"
        fig.savefig(filename, dpi=160, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return filename
