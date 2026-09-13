# tests/test_delta_engine.py
import unittest
from app.services.snapshot_service import SnapshotService


class TestDeltaEngine(unittest.TestCase):
    def test_calcular_delta_lista_entidades(self):
        """Verifica la detección diferencial en páginas tipo lista (novedades, salientes y rotación)."""
        data_anterior = [
            {"titulo": "Noticia A", "url": "https://sitio.com/a"},
            {"titulo": "Noticia B", "url": "https://sitio.com/b"},
            {"titulo": "Noticia C", "url": "https://sitio.com/c"}
        ]

        data_actual = [
            {"titulo": "Noticia B", "url": "https://sitio.com/b"},  # Mantenida
            {"titulo": "Noticia C", "url": "https://sitio.com/c"},  # Mantenida
            {"titulo": "Noticia D (Nueva)", "url": "https://sitio.com/d"},  # Novedad
            {"titulo": "Noticia E (Nueva)", "url": "https://sitio.com/e"}   # Novedad
        ]

        delta = SnapshotService.calcular_delta(data_anterior, data_actual)

        self.assertTrue(delta.get("es_lista"))
        self.assertEqual(delta.get("total_nuevos"), 2)
        self.assertEqual(delta.get("total_salientes"), 1)  # Noticia A salió
        self.assertEqual(delta.get("total_mantenidos"), 2) # B y C
        self.assertEqual(delta.get("total_actuales"), 4)

        urls_nuevas = {item["url"] for item in delta.get("nuevos_articulos", [])}
        self.assertEqual(urls_nuevas, {"https://sitio.com/d", "https://sitio.com/e"})

        urls_salientes = {item["url"] for item in delta.get("articulos_salientes", [])}
        self.assertEqual(urls_salientes, {"https://sitio.com/a"})

    def test_calcular_delta_sin_cambios(self):
        """Verifica que si no hay modificaciones, total_nuevos y total_salientes sean 0."""
        data = [
            {"titulo": "Item 1", "url": "https://sitio.com/1"},
            {"titulo": "Item 2", "url": "https://sitio.com/2"}
        ]
        delta = SnapshotService.calcular_delta(data, data)
        self.assertEqual(delta.get("total_nuevos"), 0)
        self.assertEqual(delta.get("total_salientes"), 0)
        self.assertEqual(delta.get("tasa_rotacion_pct"), 0.0)

    def test_calcular_delta_texto_continuo(self):
        """Verifica la detección diferencial en páginas de texto continuo (normas o comunicados)."""
        texto_anterior = (
            "COMUNICADO OFICIAL\n"
            "El ministerio informa que las actividades se desarrollarán con normalidad.\n"
            "Fecha: 01 de Septiembre de 2026."
        )

        texto_actual = (
            "COMUNICADO OFICIAL\n"
            "El ministerio informa que las actividades se desarrollarán con normalidad.\n"
            "ALERTA URGENTE: Se suspenden las actividades en la región sur por motivos de seguridad.\n"
            "Fecha: 01 de Septiembre de 2026."
        )

        delta = SnapshotService.calcular_delta(texto_anterior, texto_actual)

        self.assertFalse(delta.get("es_lista"))
        self.assertGreater(delta.get("variacion_caracteres"), 0)
        self.assertGreater(delta.get("total_nuevos"), 0)

    def test_ignorar_parametros_tracking_y_timestamps_en_urls(self):
        """
        Verifica que variaciones en parámetros volátiles de URLs (?utm_*, ?t=, ?timestamp=)
        no generen falsos positivos de novedades ni artículos salientes.
        """
        data_anterior = [
            {"titulo": "Noticia de Economía", "url": "https://rpp.pe/economia/noticia-1?utm_source=home&t=1725000000"},
            {"titulo": "Noticia de Deportes", "url": "https://rpp.pe/deportes/noticia-2?ref=portada"}
        ]
        data_actual = [
            # Misma noticia con parámetros de tracking y timestamp distintos
            {"titulo": "Noticia de Economía", "url": "https://rpp.pe/economia/noticia-1?utm_source=twitter&t=1725000999&fbclid=XYZ123"},
            {"titulo": "Noticia de Deportes", "url": "https://rpp.pe/deportes/noticia-2"}
        ]

        delta = SnapshotService.calcular_delta(data_anterior, data_actual)

        self.assertEqual(delta.get("total_nuevos"), 0, "No debe marcar falsos positivos de nuevos artículos")
        self.assertEqual(delta.get("total_salientes"), 0, "No debe marcar falsos positivos de artículos salientes")
        self.assertEqual(delta.get("total_mantenidos"), 2)

    def test_ignorar_banners_publicitarios(self):
        """Verifica que banners publicitarios insertados dinámicamente sean descartados del delta."""
        data_anterior = [
            {"titulo": "Reforma judicial aprobada", "url": "https://sitio.com/noticia-1"}
        ]
        data_actual = [
            {"titulo": "Reforma judicial aprobada", "url": "https://sitio.com/noticia-1"},
            {"titulo": "Publicidad: Contrata tu seguro vehicular aquí", "url": "https://googleads.g.doubleclick.net/ad1"},
            {"titulo": "Patrocinado por Empresa X", "url": "https://sitio.com/ad-2"}
        ]

        delta = SnapshotService.calcular_delta(data_anterior, data_actual)

        self.assertEqual(delta.get("total_nuevos"), 0, "Banners publicitarios no deben ser reportados como novedades")
        self.assertEqual(delta.get("total_mantenidos"), 1)

    def test_ignorar_fechas_carga_y_timestamps_dinamicos_texto_continuo(self):
        """
        Verifica que textos continuos cuyas únicas diferencias sean marcas de tiempo
        relativas ('hace X min') o fechas/horas de carga no generen falsos positivos.
        """
        texto_anterior = (
            "COMUNICADO INSTITUCIONAL\n"
            "El directorio convoca a la asamblea general de accionistas para el presente mes.\n"
            "Última actualización: hace 5 minutos\n"
            "Fecha de carga: 06/09/2026 22:00:00\n"
            "1,250 personas están leyendo esto ahora\n"
            "Todos los derechos reservados © 2026"
        )

        texto_actual = (
            "COMUNICADO INSTITUCIONAL\n"
            "El directorio convoca a la asamblea general de accionistas para el presente mes.\n"
            "Última actualización: hace 25 minutos\n"
            "Fecha de carga: 06/09/2026 22:20:00\n"
            "1,890 personas están leyendo esto ahora\n"
            "Todos los derechos reservados © 2026"
        )

        delta = SnapshotService.calcular_delta(texto_anterior, texto_actual)

        self.assertFalse(delta.get("es_lista"))
        self.assertEqual(delta.get("total_nuevos"), 0, "Variaciones de tiempo relativo y carga no deben generar falsos positivos")
        self.assertEqual(delta.get("total_salientes"), 0)
        self.assertEqual(delta.get("variacion_caracteres"), 0)


if __name__ == "__main__":
    unittest.main()
