# 🚀 Inicio Rápido - Web Scraper con Frontend

## ⚡ Opción 1: Script Automático (Recomendado)

### En Windows
```cmd
iniciar.bat
```

### En Linux/macOS
```bash
chmod +x iniciar.sh
./iniciar.sh
```

Esto iniciará automáticamente:
- ✅ API en `http://localhost:8000`
- ✅ Frontend en `http://localhost:8080`

---

## 📋 Opción 2: Inicio Manual

### Paso 1: Inicia la API
```bash
python -m uvicorn api:app --reload --host localhost --port 8000
```

### Paso 2: Inicia el Frontend

**Opción A** (Abrir archivo directamente):
- Abre `frontend/index.html` en tu navegador

**Opción B** (Con servidor Python):
```bash
cd frontend
python server.py
```
Accede a `http://localhost:8080`

---

## 🎯 Primeros Pasos

1. **Verifica la conexión**
   - Deberías ver "Conectado" ✅ en la esquina superior derecha

2. **Prueba con un ejemplo**
   - URL: `https://rpp.pe/`
   - Operación: "Extraer Índice"
   - Haz clic en "Extraer"

3. **Visualiza los resultados**
   - Aparecerán en el panel principal

---

## 📚 URLs Importantes

| Servicio | URL | Propósito |
|----------|-----|----------|
| API | http://localhost:8000 | Backend |
| API Docs | http://localhost:8000/docs | Documentación interactiva |
| Frontend | http://localhost:8080 | Interfaz web |

---

## 🔧 Troubleshooting

### Error: "Desconectado"
```bash
# Verifica que la API está ejecutándose
# Debería ver output como:
# Uvicorn running on http://127.0.0.1:8000
```

### Puerto en uso
```bash
# Si el puerto 8000 o 8080 está en uso, cambia en:
# - api.py: cambiar --port 8000 por otro
# - frontend/server.py: cambiar PORT = 8080 por otro
```

### Error CORS
- Verifica que `api.py` tiene configurado CORS
- Búsca: `CORSMiddleware` en el archivo

---

## 📖 Documentación Completa

- Guía del Frontend: [frontend/README.md](frontend/README.md)
- Documentación API: http://localhost:8000/docs (cuando esté ejecutándose)

---

## 🎨 Estructura del Proyecto

```
WebScraping/
├── api.py                    # API Backend (FastAPI)
├── scraper.py               # Lógica de scraping
├── deep_scraper.py          # Deep scraping
├── config.py                # Configuración
├── requirements.txt         # Dependencias Python
├── iniciar.bat              # Script Windows
├── iniciar.sh               # Script Linux/macOS
├── QUICK_START.md           # Este archivo
└── frontend/                # 🆕 Frontend Web
    ├── index.html           # Interfaz HTML
    ├── app.js               # Lógica JavaScript
    ├── styles.css           # Estilos
    ├── server.py            # Servidor Python
    └── README.md            # Documentación frontend
```

---

## 💡 Tips

✨ **Usa el pipeline completo** para extraer y procesar automáticamente
✨ **Revisa los logs** de la API para diagnosticar problemas
✨ **Personaliza los estilos** en `frontend/styles.css`
✨ **Cambia la URL de la API** en `frontend/app.js` si usas otro puerto

---

## ❓ ¿Más ayuda?

- Lee [frontend/README.md](frontend/README.md) para guía completa del frontend
- Accede a http://localhost:8000/docs para documentación de la API
- Revisa los logs en la terminal

**¡Listo! Ahora puedes comenzar a hacer web scraping con estilo! 🕷️**
